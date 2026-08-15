---
name: ui-consistency-review
description: Reviews Tailwind usage, spacing, and component reuse across the frontend for visual consistency — catches ad-hoc styles and duplicated UI patterns. Use periodically or before a UI-heavy PR is merged.
---

# ui-consistency-review

Revisión de consistencia visual entre componentes/páginas ya construidas.

## Cuándo usarla
Antes de mergear un PR que agrega o modifica varias pantallas, o cuando se sospecha que
hay estilos duplicados/inconsistentes acumulándose.

## Qué revisa
1. **Valores mágicos**: colores, espaciados o tamaños de fuente escritos a mano en vez de
   usar las clases/tokens de Tailwind ya establecidos en el proyecto.
2. **Duplicación de patrones**: dos o más componentes resolviendo el mismo problema visual
   (ej. dos variantes de "card" ligeramente distintas) que deberían unificarse en
   `src/components/`.
3. **Consistencia de estados**: loading/error/empty se ven y comportan igual entre
   pantallas distintas, no cada una inventa su propio patrón.
4. **Densidad de información**: pantallas de datos (tablas, resultados de análisis) siguen
   un mismo criterio de espaciado y jerarquía visual.

## Qué NO hace
No es una revisión de accesibilidad (eso es `accessibility-review`) ni de lógica de datos
— es puramente sobre coherencia visual del sistema de diseño ya definido con Tailwind.
