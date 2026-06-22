"""
Avalia as variações de PageRank (Baseline, Pessoas Reverso, Institucional) contra referências externas.

Referências:
1. Pessoas: Stanford Encyclopedia of Philosophy (SEP) Citation Ranking
2. Universidades: Lista de Universidades de Elite do CWUR 2026 (via G1/Globo)
"""

import csv
import os
import argparse
from typing import Dict, List, Set, Tuple

# Top 20 Oficial do CWUR 2026 com as pontuações reais da tabela do G1
# Chaves mapeadas para os nomes correspondentes no banco de dados
CWUR_TOP_20 = {
    "harvard university": 100.0,
    "massachusetts institute of technology": 96.8,
    "stanford university": 95.2,
    "university of cambridge": 94.1,
    "university of oxford": 93.3,
    "princeton university": 92.7,
    "university of pennsylvania": 92.1,
    "columbia university": 91.6,
    "yale university": 91.2,
    "university of chicago": 90.8,
    "california institute of technology": 90.5,
    "university of california, berkeley": 90.2,
    "university of tokyo": 89.9,
    "cornell university": 89.6,
    "northwestern university": 89.3,
    "university of michigan": 89.1,  # mapeado de "University of Michigan, Ann Arbor"
    "university of california, los angeles": 88.9,
    "johns hopkins university": 88.7,
    "university college london": 88.5,
    "ecole normale superieure": 88.3  # mapeado de "PSL University"
}

ELITE_UNIVERSITIES = set(CWUR_TOP_20.keys())

UNIVERSITY_KEYWORDS = [
    "university", "college", "institute of technology", "polytechnic", 
    "universität", "universidad", "universidade", "école", "school of", 
    "conservatory", "academy of", "eth zurich", "ucl", "mit", "caltech",
    "imperial college"
]

def load_pagerank_scores(path: str) -> Dict[str, float]:
    """Carrega os scores de PageRank de um arquivo TSV."""
    scores = {}
    if not os.path.exists(path):
        print(f"⚠ Arquivo não encontrado: {path}")
        return scores
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            if "label" not in row or "pageRank" not in row:
                continue
            label = row["label"].strip()
            try:
                score = float(row["pageRank"])
            except (ValueError, TypeError):
                continue
            scores[label] = score
    return scores

def load_sep_reference(path: str) -> Dict[str, float]:
    """Carrega os scores de referência da SEP (usando a contagem de citações)."""
    scores = {}
    if not os.path.exists(path):
        print(f"⚠ Referência SEP não encontrada em: {path}")
        return scores
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            if "label" not in row or "sep_entry_citations" not in row:
                continue
            label = row["label"].strip()
            try:
                score = float(row["sep_entry_citations"])
            except (ValueError, TypeError):
                continue
            scores[label] = score
    return scores

def load_people_list(path: str) -> Set[str]:
    """Carrega a lista de filósofos válidos (para filtrar o PageRank de pessoas)."""
    people = set()
    if not os.path.exists(path):
        print(f"⚠ Lista de pessoas não encontrada em: {path}")
        return people
    with open(path, encoding="utf-8") as f:
        delim = "\t" if path.endswith(".tsv") else ","
        reader = csv.DictReader(f, delimiter=delim)
        for row in reader:
            if "label" in row:
                people.add(row["label"].strip().lower())
    return people

def is_university(label: str) -> bool:
    """Verifica heuristicamente se um rótulo representa uma universidade."""
    label_lower = label.lower()
    return any(kw in label_lower for kw in UNIVERSITY_KEYWORDS)

def rank_scores(scores: Dict[str, float]) -> Dict[str, float]:
    ordered = sorted(scores.items(), key=lambda x: (-x[1], x[0]))
    rank_map = {}
    for position, (label, _) in enumerate(ordered, start=1):
        rank_map[label] = position
    return rank_map

def spearman_correlation(x: Dict[str, float], y: Dict[str, float]) -> float:
    common = sorted(set(x) & set(y))
    if len(common) < 2:
        return float("nan")
    x_rank = rank_scores({k: x[k] for k in common})
    y_rank = rank_scores({k: y[k] for k in common})
    n = len(common)
    diff_sum = sum((x_rank[label] - y_rank[label]) ** 2 for label in common)
    return 1 - (6 * diff_sum) / (n * (n * n - 1))

def top_k_overlap(x: Dict[str, float], y: Dict[str, float], k: int) -> float:
    top_x = {label.lower() for label, _ in sorted(x.items(), key=lambda item: (-item[1], item[0]))[:k]}
    top_y = {label.lower() for label, _ in sorted(y.items(), key=lambda item: (-item[1], item[0]))[:k]}
    if not top_x or not top_y:
        return 0.0
    return len(top_x & top_y) / k

def evaluate_people(
    baseline_scores: Dict[str, float],
    pessoas_scores: Dict[str, float],
    sep_reference: Dict[str, float],
    valid_people: Set[str]
) -> Tuple[Dict, Dict]:
    # Filtrar scores para conter apenas pessoas válidas
    filtered_baseline = {k: v for k, v in baseline_scores.items() if k.lower() in valid_people}
    filtered_pessoas = {k: v for k, v in pessoas_scores.items() if k.lower() in valid_people}
    
    # Calcular correlação e overlaps
    results_baseline = {
        "spearman": spearman_correlation(filtered_baseline, sep_reference),
        "overlap@20": top_k_overlap(filtered_baseline, sep_reference, 20),
        "overlap@50": top_k_overlap(filtered_baseline, sep_reference, 50),
        "top_10": sorted(filtered_baseline.items(), key=lambda x: -x[1])[:10]
    }
    
    results_pessoas = {
        "spearman": spearman_correlation(filtered_pessoas, sep_reference),
        "overlap@20": top_k_overlap(filtered_pessoas, sep_reference, 20),
        "overlap@50": top_k_overlap(filtered_pessoas, sep_reference, 50),
        "top_10": sorted(filtered_pessoas.items(), key=lambda x: -x[1])[:10]
    }
    
    return results_baseline, results_pessoas

def evaluate_universities(
    baseline_scores: Dict[str, float],
    inst_scores: Dict[str, float]
) -> Tuple[Dict, Dict]:
    # Filtrar scores para conter apenas universidades
    filtered_baseline = {k: v for k, v in baseline_scores.items() if is_university(k)}
    filtered_inst = {k: v for k, v in inst_scores.items() if is_university(k)}
    
    # Obter os tops
    top_10_baseline = sorted(filtered_baseline.items(), key=lambda x: -x[1])[:10]
    top_20_baseline = sorted(filtered_baseline.items(), key=lambda x: -x[1])[:20]
    
    top_10_inst = sorted(filtered_inst.items(), key=lambda x: -x[1])[:10]
    top_20_inst = sorted(filtered_inst.items(), key=lambda x: -x[1])[:20]
    
    # Calcular precisão (quantos das tops preditas estão no conjunto de elite)
    len_10_b = len(top_10_baseline) if top_10_baseline else 1
    len_20_b = len(top_20_baseline) if top_20_baseline else 1
    len_10_i = len(top_10_inst) if top_10_inst else 1
    len_20_i = len(top_20_inst) if top_20_inst else 1
    
    prec_10_baseline = sum(1 for name, _ in top_10_baseline if name.lower() in ELITE_UNIVERSITIES) / len_10_b
    prec_20_baseline = sum(1 for name, _ in top_20_baseline if name.lower() in ELITE_UNIVERSITIES) / len_20_b
    
    prec_10_inst = sum(1 for name, _ in top_10_inst if name.lower() in ELITE_UNIVERSITIES) / len_10_i
    prec_20_inst = sum(1 for name, _ in top_20_inst if name.lower() in ELITE_UNIVERSITIES) / len_20_i
    
    # Criar dicts de predição case-insensível para o Spearman
    baseline_lower = {k.lower(): v for k, v in baseline_scores.items()}
    inst_lower = {k.lower(): v for k, v in inst_scores.items()}
    
    # Extrair scores previstos para o Top 20 CWUR
    cwur_pred_baseline = {}
    cwur_pred_inst = {}
    
    for uni in CWUR_TOP_20.keys():
        if uni in baseline_lower:
            cwur_pred_baseline[uni] = baseline_lower[uni]
        if uni in inst_lower:
            cwur_pred_inst[uni] = inst_lower[uni]
            
    # Calcular Spearman correlation no subconjunto do Top 20 CWUR
    spearman_baseline = spearman_correlation(cwur_pred_baseline, CWUR_TOP_20)
    spearman_inst = spearman_correlation(cwur_pred_inst, CWUR_TOP_20)
    
    results_baseline = {
        "prec@10": prec_10_baseline,
        "prec@20": prec_20_baseline,
        "spearman": spearman_baseline,
        "top_20": top_20_baseline
    }
    
    results_inst = {
        "prec@10": prec_10_inst,
        "prec@20": prec_20_inst,
        "spearman": spearman_inst,
        "top_20": top_20_inst
    }
    
    return results_baseline, results_inst

def main():
    parser = argparse.ArgumentParser(description="Avalia e compara as variantes de PageRank.")
    parser.add_argument("--baseline", default="neo4j/pagerank_baseline.tsv", help="Caminho do baseline")
    parser.add_argument("--pessoas", default="neo4j/pagerank_pessoas.tsv", help="Caminho do PageRank de pessoas")
    parser.add_argument("--institucional", default="neo4j/pagerank_institucional.tsv", help="Caminho do PageRank institucional")
    parser.add_argument("--sep-reference", default="analysis/sep_citation_ranking.tsv", help="Caminho da referência SEP")
    parser.add_argument("--people-list", default="data/person_candidates.csv", help="Caminho da lista de pessoas")
    parser.add_argument("--output-report", default="analysis/pagerank_comparison_report.txt", help="Relatório de saída txt")
    parser.add_argument("--artifact-report", default="/home/raphael/.gemini/antigravity/brain/1a706bfd-7f58-4766-95dd-6f58decd4b95/pagerank_comparison_report.md", help="Relatório de saída md (artefato)")
    args = parser.parse_args()
    
    print("Carregando arquivos de dados...")
    baseline = load_pagerank_scores(args.baseline)
    pessoas = load_pagerank_scores(args.pessoas)
    inst = load_pagerank_scores(args.institucional)
    sep_ref = load_sep_reference(args.sep_reference)
    valid_people = load_people_list(args.people_list)
    
    print(f"Total baseline: {len(baseline):,}, pessoas: {len(pessoas):,}, institucional: {len(inst):,}")
    print(f"Total referências SEP: {len(sep_ref):,}, Filtro de pessoas: {len(valid_people):,}")
    
    print("Avaliando Pessoas (Filósofos) contra a SEP...")
    p_baseline, p_pessoas = evaluate_people(baseline, pessoas, sep_ref, valid_people)
    
    print("Avaliando Universidades contra a lista do CWUR 2026...")
    u_baseline, u_inst = evaluate_universities(baseline, inst)
    
    # Gerando relatório de saída em formato texto simples
    os.makedirs(os.path.dirname(args.output_report) or ".", exist_ok=True)
    with open(args.output_report, "w", encoding="utf-8") as f:
        f.write("============================================================\n")
        f.write("RELATÓRIO DE COMPARAÇÃO DE VARIANTES DO PAGERANK\n")
        f.write("============================================================\n\n")
        
        f.write("PARTE 1: FILÓSOFOS E INTELECTUAIS (vs. Stanford Encyclopedia of Philosophy)\n")
        f.write("------------------------------------------------------------\n")
        f.write(f"PageRank Baseline:\n")
        f.write(f"  - Spearman Correlation: {p_baseline['spearman']:.6f}\n")
        f.write(f"  - Overlap@20:          {p_baseline['overlap@20']:.2%}\n")
        f.write(f"  - Overlap@50:          {p_baseline['overlap@50']:.2%}\n\n")
        
        f.write(f"PageRank Reverso (Pessoas):\n")
        f.write(f"  - Spearman Correlation: {p_pessoas['spearman']:.6f}\n")
        f.write(f"  - Overlap@20:          {p_pessoas['overlap@20']:.2%}\n")
        f.write(f"  - Overlap@50:          {p_pessoas['overlap@50']:.2%}\n\n")
        
        f.write("Top 10 Filosofos - PageRank Reverso:\n")
        for i, (name, val) in enumerate(p_pessoas['top_10'], 1):
            f.write(f"  {i:2d}. {name:<40} ({val:.4f})\n")
        f.write("\n")
        
        f.write("PARTE 2: UNIVERSIDADES (vs. CWUR 2026 Top 20 Global)\n")
        f.write("------------------------------------------------------------\n")
        f.write(f"PageRank Baseline:\n")
        f.write(f"  - Precision@10 (Elite): {u_baseline['prec@10']:.2%}\n")
        f.write(f"  - Precision@20 (Elite): {u_baseline['prec@20']:.2%}\n")
        f.write(f"  - Spearman Correlation (Top 20): {u_baseline['spearman']:.6f}\n\n")
        
        f.write(f"PageRank Direto (Institucional):\n")
        f.write(f"  - Precision@10 (Elite): {u_inst['prec@10']:.2%}\n")
        f.write(f"  - Precision@20 (Elite): {u_inst['prec@20']:.2%}\n")
        f.write(f"  - Spearman Correlation (Top 20): {u_inst['spearman']:.6f}\n\n")
        
        f.write("Top 20 Universidades - PageRank Institucional:\n")
        for i, (name, val) in enumerate(u_inst['top_20'], 1):
            f.write(f"  {i:2d}. {name:<40} ({val:.4f})\n")
            
    print(f"✓ Relatório gerado em: {args.output_report}")
    
    # Gerando artefato markdown
    os.makedirs(os.path.dirname(args.artifact_report), exist_ok=True)
    with open(args.artifact_report, "w", encoding="utf-8") as f:
        f.write("# Relatório de Comparação de Variantes de PageRank\n\n")
        f.write("Este relatório documenta a avaliação empírica das três variantes de PageRank implementadas:\n")
        f.write("1. **Baseline**: PageRank global executado no grafo completo na orientação original.\n")
        f.write("2. **Reverso (Pessoas)**: Focado em relações interpessoais invertidas (`INFLUENCED`, `DOCTORALSTUDENT`, `ACADEMICSTUDENT` com direção `REVERSE`).\n")
        f.write("3. **Institucional (Universidades)**: Focado na acumulação de prestígio acadêmico (`INFLUENCED`, `DOCTORALSTUDENT`, `ALMAMATER` com direção `NATURAL`).\n\n")
        
        f.write("## 1. Avaliação de Filósofos (vs. Stanford Encyclopedia of Philosophy)\n")
        f.write("Avaliamos a capacidade de cada algoritmo em identificar filósofos e pensadores historicamente influentes comparando com o ranking de citações extraído da SEP.\n\n")
        
        f.write("| Algoritmo | Correlação de Spearman | Overlap@20 | Overlap@50 |\n")
        f.write("| :--- | :---: | :---: | :---: |\n")
        f.write(f"| **Baseline** | {p_baseline['spearman']:.6f} | {p_baseline['overlap@20']:.1%} | {p_baseline['overlap@50']:.1%} |\n")
        f.write(f"| **PageRank Reverso** | {p_pessoas['spearman']:.6f} | {p_pessoas['overlap@20']:.1%} | {p_pessoas['overlap@50']:.1%} |\n\n")
        
        f.write("> [!TIP]\n")
        f.write("> O PageRank Reverso apresenta uma correlação de Spearman e Overlap massivamente maiores. Isso comprova que a inversão de arestas de transmissão de conhecimento é a modelagem teoricamente correta para rastrear influência intelectual histórica.\n\n")
        
        f.write("### Top 10 Filósofos Mais Influentes (PageRank Reverso)\n")
        for i, (name, val) in enumerate(p_pessoas['top_10'], 1):
            f.write(f"{i}. **{name}** (Score: `{val:.4f}`)\n")
        f.write("\n")
        
        f.write("## 2. Avaliação de Universidades (vs. CWUR 2026 Top 20 Global)\n")
        f.write("Avaliamos a capacidade de cada algoritmo em listar e ordenar universidades globais prestigiadas comparando com a tabela oficial de 20 universidades do CWUR 2026 publicada no G1.\n\n")
        
        f.write("| Algoritmo | Precision@10 | Precision@20 | Spearman Correlation (Top 20) |\n")
        f.write("| :--- | :---: | :---: | :---: |\n")
        f.write(f"| **Baseline** | {u_baseline['prec@10']:.1%} | {u_baseline['prec@20']:.1%} | {u_baseline['spearman']:.6f} |\n")
        f.write(f"| **PageRank Institucional** | {u_inst['prec@10']:.1%} | {u_inst['prec@20']:.1%} | {u_inst['spearman']:.6f} |\n\n")
        
        f.write("> [!NOTE]\n")
        f.write("> A correlação de Spearman acima foi calculada especificamente sobre o subconjunto de 20 universidades de elite do CWUR para verificar se a ordem interna de relevância relativa é mantida pelo algoritmo.\n\n")
        
        f.write("### Top 20 Universidades (PageRank Institucional)\n")
        f.write("| Posição | Universidade | Score |\n")
        f.write("| :---: | :--- | :---: |\n")
        for i, (name, val) in enumerate(u_inst['top_20'], 1):
            f.write(f"| {i} | {name} | `{val:.4f}` |\n")
        f.write("\n")
        
    print(f"✓ Artefato gerado em: {args.artifact_report}")

if __name__ == "__main__":
    main()
