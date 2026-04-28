"""
Converte rede_intelectual_final.nt em rede_intelectual.gexf
sem alterar nada — apenas serializa as triplas que já estão no formato correto.

Uso:
    python nt_to_gexf.py rede_intelectual_final.nt rede_intelectual.gexf
"""
import sys
from xml.sax.saxutils import escape

def short(uri: str) -> str:
    """Remove < > e o prefixo dbpedia.org/resource/, troca _ por espaço."""
    u = uri[1:-1] if uri.startswith("<") else uri
    pfx_res = "http://dbpedia.org/resource/"
    if u.startswith(pfx_res):
        return u[len(pfx_res):].replace("_", " ")
    return u

def short_pred(uri: str) -> str:
    """Para predicados: remove o namespace dbpedia.org/ontology/."""
    u = uri[1:-1] if uri.startswith("<") else uri
    pfx_ont = "http://dbpedia.org/ontology/"
    if u.startswith(pfx_ont):
        return u[len(pfx_ont):]
    return u


def main(nt_path: str, gexf_path: str) -> None:
    print(f"Lendo {nt_path}...")

    edges = []          # lista de (sid, tid, label)
    node_ids = {}       # uri -> int id

    def get_id(uri: str) -> int:
        nid = node_ids.get(uri)
        if nid is None:
            nid = len(node_ids)
            node_ids[uri] = nid
        return nid

    with open(nt_path, encoding="utf-8") as f:
        for line in f:
            if not line or line[0] != "<":
                continue
            sp1 = line.find("> <")
            if sp1 < 0:
                continue
            s = line[:sp1+1]
            rest = line[sp1+2:]
            sp2 = rest.find("> <")
            if sp2 < 0:
                continue
            p = rest[:sp2+1]
            o_part = rest[sp2+2:]
            end = o_part.rfind("> .")
            if end < 0:
                continue
            o = o_part[:end+1]
            edges.append((get_id(s), get_id(o), short_pred(p)))

    V = len(node_ids)
    E = len(edges)
    print(f"  {V:,} nós, {E:,} arestas")

    # ordena URIs por id pra escrita determinística
    id_to_uri = [None] * V
    for uri, nid in node_ids.items():
        id_to_uri[nid] = uri

    # contagem de predicados (sanity check)
    from collections import Counter
    pred_counts = Counter(lab for _, _, lab in edges)
    print("  predicados encontrados:")
    for p, c in pred_counts.most_common():
        print(f"    {c:>8,}  {p}")

    print(f"\nEscrevendo {gexf_path}...")
    with open(gexf_path, "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write('<gexf xmlns="http://gexf.net/1.3" version="1.3">\n')
        f.write('  <meta lastmodifieddate="2026-04-26">\n')
        f.write('    <creator>MC859 - Rede Intelectual DBpedia</creator>\n')
        f.write('    <description>Subgrafo direcionado da DBpedia (mappingbased-objects, lang=en) '
                'com predicados temáticos. Arestas reorientadas e deduplicadas.</description>\n')
        f.write('  </meta>\n')
        f.write('  <graph mode="static" defaultedgetype="directed">\n')
        f.write(f'    <nodes count="{V}">\n')
        for nid, uri in enumerate(id_to_uri):
            f.write(f'      <node id="{nid}" label="{escape(short(uri))}"/>\n')
        f.write('    </nodes>\n')
        f.write(f'    <edges count="{E}">\n')
        for eid, (s, t, lab) in enumerate(edges):
            f.write(f'      <edge id="{eid}" source="{s}" target="{t}" label="{escape(lab)}"/>\n')
        f.write('    </edges>\n')
        f.write('  </graph>\n')
        f.write('</gexf>\n')

    import os
    sz = os.path.getsize(gexf_path) / (1024**2)
    print(f"Pronto: {gexf_path} ({sz:.1f} MB)")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__); sys.exit(1)
    main(sys.argv[1], sys.argv[2])