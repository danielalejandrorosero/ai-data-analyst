# AI Data Analyst — Frontend

React + TypeScript + Vite, gestionado con **pnpm**. Consume el backend real (`../backend`)
bajo `/api`. Ver también el [`README.md`](../README.md) de la raíz del monorepo y
[`CLAUDE.md`](./CLAUDE.md) para las convenciones de este directorio.

## Requisitos

- Node.js 22+
- pnpm
- El backend corriendo (`http://localhost:8000` por defecto — ver el README de la raíz)

## Comandos

```bash
cp .env.example .env.local
pnpm install
pnpm dev       # dev server en http://localhost:5173
pnpm test      # Vitest + Testing Library
pnpm lint      # oxlint
pnpm build     # type-check (tsc -b) + build de producción a dist/
pnpm preview   # sirve el build de producción localmente
```

`VITE_API_BASE_URL` (en `.env.local`) apunta al backend — por defecto
`http://localhost:8000/api`.

## Estado

Login y registro (`/login`, `/register`) funcionales contra el backend real, incluyendo
manejo de errores de validación (422), toggle de mostrar/ocultar contraseña, y un footer
de estado (`TraceStrip`) que refleja `/health/ready` en vivo — no es decorativo. El resto
de las pantallas (datasets, análisis, gráficos) se agregan fase por fase, siguiendo el
mismo roadmap que el backend (`docs/SRS.md` sección 13 en la raíz del repo).

## Estructura

- `src/api/` — cliente HTTP + hooks de TanStack Query (única vía para llamar al backend)
- `src/components/` — componentes compartidos entre features
- `src/features/*` — pantallas y lógica específica de cada área (auth, datasets, ...)
- `src/lib/` — utilidades y estado compartido (Zustand, hooks genéricos)
