---
name: create-component
description: Scaffolds a new React/TypeScript component following this project's Tailwind + typed-props conventions. Use when adding a new reusable UI component to frontend/src/components or frontend/src/features/*.
---

# create-component

Crea un componente React/TypeScript nuevo siguiendo `frontend/CLAUDE.md` y
`.claude/rules/frontend.md`.

## Cuándo usarla
Al agregar un componente reutilizable (no una página completa — para eso usa `create-page`).

## Qué debe garantizar
0. Dirección visual vía `frontend-design`/`ui-ux-pro-max` para cualquier decisión estética
   nueva, e `impeccable` sobre el resultado antes de darlo por terminado — ver
   "Herramientas de diseño obligatorias" en `frontend/CLAUDE.md`.
1. Props tipadas explícitamente (interface/type), sin `any`.
2. Estilos con Tailwind CSS, reutilizando tokens/clases ya existentes en el proyecto en
   vez de valores mágicos sueltos (ver `ui-consistency-review`).
3. Si el componente consume datos remotos, lo hace vía un hook de `src/api/` (TanStack
   Query) — nunca fetch directo dentro del componente.
4. Accesible por defecto: roles/aria correctos, foco manejable por teclado, contraste
   suficiente — ver `accessibility-review` para el checklist completo.
5. Ubicación correcta: `src/components/` si es genérico y reutilizable entre features,
   `src/features/<feature>/` si es específico de una feature.
6. Esqueleto de test (Vitest + React Testing Library) que cubra el render básico y, si
   aplica, la interacción principal.

## Qué NO hace
No decide arquitectura de estado nueva (Zustand) sin que exista una necesidad real — ver
`frontend/CLAUDE.md`.
