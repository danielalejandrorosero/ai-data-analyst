---
name: create-query-hook
description: Scaffolds a typed TanStack Query hook (useQuery/useMutation) for a given backend /api endpoint, including error handling and cache invalidation. Use whenever the frontend needs to consume a new or existing API endpoint.
---

# create-query-hook

Crea un hook de TanStack Query en `src/api/` para consumir un endpoint de `/api`.

## Cuándo usarla
Antes de que cualquier componente o página consuma un endpoint nuevo del backend.

## Qué debe garantizar
1. Tipos de request/response alineados con los schemas Pydantic del backend (manual o vía
   OpenAPI exportado en `docs/api/`) — no `any` ni tipos inventados.
2. `useQuery` para lecturas, `useMutation` para escrituras, con invalidación de cache
   explícita hacia las queries afectadas.
3. Manejo de error consistente con cómo la UI distingue error/carga/resultado (RNF-031) —
   no swallow silencioso de errores.
4. Si el endpoint requiere autenticación, el hook asume que el token/sesión ya está
   gestionado por la capa de auth compartida, no lo reimplementa.
5. Un solo hook por responsabilidad — no mezclar múltiples endpoints no relacionados en
   un mismo hook.

## Qué NO hace
No reemplaza al backend como fuente de validación: la validación de negocio vive en
`backend/`, el hook solo tipa y consume el contrato ya validado allí.
