---
name: accessibility-review
description: Reviews a frontend component or page against keyboard navigation, ARIA, contrast, and RNF-030/RNF-031 (responsive desktop/tablet, visually distinct execution states). Use before considering UI work done.
---

# accessibility-review

Revisión de accesibilidad y de los requisitos de UX explícitos del SRS
(RNF-030, RNF-031) para un componente o página ya construida.

## Cuándo usarla
Antes de dar por terminada una página o componente de UI no trivial, especialmente
pantallas de análisis (donde conviven texto, SQL, tools y errores).

## Qué revisa
1. **Navegación por teclado**: todo elemento interactivo es alcanzable y operable sin
   mouse, con foco visible.
2. **ARIA/semántica**: roles y labels correctos, sin `div`/`span` haciendo de botón sin
   semántica.
3. **Contraste**: texto y elementos interactivos cumplen contraste mínimo legible sobre
   el sistema de color de Tailwind del proyecto.
4. **RNF-030**: la pantalla funciona correctamente en desktop y tablet, sin elementos
   críticos fuera de viewport.
5. **RNF-031**: la UI distingue visualmente (no solo por texto) entre respuesta final,
   tool ejecutada, SQL generado y error — nunca mezclados en el mismo bloque visual.

## Qué NO hace
No reemplaza un audit automatizado completo (axe, Lighthouse) — es una revisión dirigida
a lo que el SRS exige explícitamente más los básicos de accesibilidad.
