# ADR-0011: Embeddings locales para el RAG documental

## Estado
Aceptado — 2026-08-16

## Contexto
La Fase 6 (SRS 3.7, RF-061/RF-062) necesita embeddings para indexar fragmentos de
documentos en pgvector y para embeber cada consulta de búsqueda. El proveedor de LLM del
proyecto (Kimi/Moonshot, ADR-0009) no garantiza un endpoint de embeddings estable en su
API OpenAI-compatible, así que "reusar la key existente" no es una opción confiable.

## Decisión
Generar los embeddings **localmente en el worker** con `fastembed` (ONNX, CPU), modelo
`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (384 dimensiones,
multilingüe — el contenido del producto es principalmente español).

El nombre del modelo es configurable (`EMBEDDING_MODEL`), pero la dimensión del vector
está fija en el schema (`vector(384)`): cambiar a un modelo de otra dimensión requiere
migración + re-indexar todos los documentos, y se documentaría como una decisión nueva.

## Justificación
- **Bastan para este caso** (discutido explícitamente con el usuario antes de decidir):
  la calidad de retrieval de los modelos multilingües chicos está a pocos puntos de las
  APIs pagas en benchmarks públicos de retrieval, y la búsqueda es híbrida — los términos
  exactos que el embedding pierda los recupera la parte léxica (full-text de Postgres).
  A la escala del proyecto (miles de fragmentos, no millones) la diferencia es marginal.
- Sin costo por token, sin API key nueva que gestionar (ADR-0004), y los tests de
  integración corren offline y deterministas.
- CPU alcanza: el modelo embebe cientos de fragmentos por segundo; GPU (el usuario
  ofreció su RTX 3050) requeriría passthrough CUDA en Docker/WSL2 — complejidad de setup
  real a cambio de una ganancia irrelevante a esta escala. Descartado a propósito.

## Consecuencias
- Primera ejecución del worker descarga el modelo ONNX (~500MB) a un cache local — el
  contenedor necesita red la primera vez; después es offline.
- La ingesta corre en el worker (ARQ), nunca en el request de subida — un PDF grande no
  bloquea la API (RF-061 exige estado PROCESSING/READY/FAILED visible).
- Si el corpus creciera órdenes de magnitud o el dominio exigiera recall de frontera,
  cambiar a una API de embeddings es una edición de configuración + re-indexado, no una
  reescritura (la interfaz de embedding es un módulo propio del dominio documents).
