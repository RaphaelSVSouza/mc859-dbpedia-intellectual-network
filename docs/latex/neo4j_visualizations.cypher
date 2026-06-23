// ================================================================
// 1. VISÃO GLOBAL REPRESENTATIVA
// ================================================================
// Seleciona os 20 vértices de maior grau e até 40 relações incidentes
// por vértice. O resultado tem no máximo 800 relações e permanece
// abaixo do limite visual padrão de 1.000 nós do Neo4j Browser.

MATCH (n:Resource)-[incident]-()
WITH n, count(incident) AS degree
ORDER BY degree DESC
LIMIT 20
CALL {
    WITH n
    MATCH (n)-[r]-(m:Resource)
    WITH r, m
    ORDER BY m.label
    LIMIT 40
    RETURN r, m
}
RETURN n, r, m;


// ================================================================
// 2. FUNIL DO BASELINE: VAKLUSH TOLEV
// ================================================================
// Mostra as tradições que apontam para Tolev e até 25 recursos que
// alimentam cada tradição pela relação RELIGION. As setas preservam
// a orientação armazenada no banco.

MATCH p=(tradition:Resource)-[:INFLUENCED]->
        (tolev:Resource {label: 'Vaklush Tolev'})
CALL {
    WITH tradition
    OPTIONAL MATCH q=(person:Resource)-[:RELIGION]->(tradition)
    WITH q, person
    ORDER BY person.label
    LIMIT 25
    RETURN q
}
RETURN p, q;


// ================================================================
// 3. SEGMENTO DE PESSOAS: INFLUÊNCIA E ORIENTAÇÃO
// ================================================================
// Recorte de um salto ao redor de figuras presentes no núcleo da
// Figura 3. A visualização exibe a direção original das relações;
// a projeção GDS usada no experimento de pessoas é que as inverte.

MATCH p=(a:Resource)-[r]-(b:Resource)
WHERE type(r) IN ['INFLUENCED', 'DOCTORALSTUDENT', 'ACADEMICSTUDENT']
  AND (
    a.label IN [
      'Immanuel Kant', 'Plato', 'Aristotle', 'David Hume',
      'Leo Strauss', 'Karl Marx', 'Bertrand Russell',
      'Friedrich Nietzsche'
    ]
    OR
    b.label IN [
      'Immanuel Kant', 'Plato', 'Aristotle', 'David Hume',
      'Leo Strauss', 'Karl Marx', 'Bertrand Russell',
      'Friedrich Nietzsche'
    ]
  )
RETURN DISTINCT p
LIMIT 500;


// ================================================================
// 4. SEGMENTO INSTITUCIONAL: UNIVERSIDADES E EX-ALUNOS
// ================================================================
// Para cada universidade, seleciona até 25 ex-alunos com maior grau
// no grafo completo. O resultado tem no máximo 250 relações.

UNWIND [
  'Harvard University',
  'University of Michigan',
  'Princeton University',
  'Yale University',
  'Columbia University',
  'University of Chicago',
  'University of Cambridge',
  'University of California, Berkeley',
  'Stanford University',
  'Massachusetts Institute of Technology'
] AS universityName
MATCH (uni:Resource {label: universityName})
CALL {
    WITH uni
    MATCH p=(person:Resource)-[:ALMAMATER]->(uni)
    MATCH (person)-[incident]-()
    WITH p, count(incident) AS personDegree
    ORDER BY personDegree DESC
    LIMIT 25
    RETURN p
}
RETURN p;
