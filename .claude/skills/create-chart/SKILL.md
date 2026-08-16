---
name: create-chart
description: Scaffolds a Recharts visualization component for analysis results, wired to the underlying table data and source query for traceability. Complements the general-purpose `dataviz` skill with this project's specific traceability rule.
---

# create-chart

Crea un componente de visualización con Recharts para un resultado de análisis.

## Cuándo usarla
Al mostrar un gráfico generado a partir de un `analysis_artifact` de tipo chart
(RF-041). Para lineamientos generales de diseño de gráficos/colores, usa primero la skill
`dataviz`; esta skill añade las reglas específicas de este proyecto.

## Qué debe garantizar
1. El gráfico se construye a partir de datos ya devueltos/validados por el backend
   (`create_chart` tool / `analysis_artifacts`) — el frontend no recalcula ni transforma
   datos "a ciegas" (`frontend/CLAUDE.md`).
2. El usuario puede ver la tabla de datos subyacente y la consulta SQL origen desde el
   propio gráfico (RF-042, trazabilidad visualización -> evidencia).
3. Sigue la guía de diseño de la skill `dataviz` (forma, color, accesibilidad) para
   mantener consistencia visual entre todos los gráficos del producto, y pasa por
   `frontend-design`/`ui-ux-pro-max`/`impeccable` como el resto de la UI del proyecto —
   ver "Herramientas de diseño obligatorias" en `frontend/CLAUDE.md`.
4. Responsive en desktop y tablet (RNF-030); estados de carga/vacío manejados
   explícitamente.

## Qué NO hace
No inventa tipos de gráfico fuera de lo que `create_chart` (backend) especificó — si el
tipo sugerido no está soportado en Recharts, se reporta en vez de forzar una aproximación
visualmente engañosa.
