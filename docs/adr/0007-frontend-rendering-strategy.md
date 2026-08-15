# ADR-0007: Vite SPA en vez de Next.js

## Estado
Aceptado — 2026-08-15

## Contexto
El SRS (sección 5.1) ya fija React + TypeScript + Vite, pero durante Fase 0 se evaluó
explícitamente si convenía usar Next.js en su lugar, dado que es el framework más popular
del ecosistema React y encaja de forma nativa con Vercel (destino de despliegue planeado
para el frontend, ver `docs/deployment.md`).

## Decisión
Mantener **Vite + React Router** como SPA cliente-puro, tal como especifica el SRS. No usar
Next.js.

## Justificación
- La app es un dashboard autenticado (login requerido para casi todo), sin necesidad de SEO
  ni contenido público indexable — el motivo principal para elegir Next.js (SSR/SSG para
  SEO) no aplica.
- El SRS exige un único backend Python unificado para evitar microservicios prematuros
  (sección 5, sección 18). Las API routes de Next.js introducirían una segunda superficie
  de backend en Node.js, duplicando o fragmentando lógica que debe vivir solo en FastAPI.
- El flujo central del producto (progreso de análisis vía SSE, RF-021 a RF-025) es más
  simple de implementar en un componente cliente puro que negociando el split
  server-component/client-component de Next.js App Router.
- Vercel despliega SPAs de Vite igual de bien que apps Next.js — no se pierde nada del lado
  de despliegue por quedarse con Vite.
- Cambiar a Next.js sin un motivo técnico real habría sido justo el tipo de "tecnología
  porque es popular" que el SRS pide evitar explícitamente.

## Consecuencias
- El router de la app es **React Router** (no hay file-based routing automático de Next —
  las rutas se declaran explícitamente).
- Si en el futuro aparece una necesidad real de SSR (por ejemplo, una landing pública de
  marketing separada de la app autenticada), se evalúa como un ADR nuevo y posiblemente
  como una app aparte, no como reemplazo de este frontend.
