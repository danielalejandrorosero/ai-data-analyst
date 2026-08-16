---
name: phase-dod-check
description: Verifies the Definition of Done (SRS section 13.1) against the current roadmap phase before it's marked complete. Use before closing out a Fase (0-8) from docs/SRS.md.
---

# phase-dod-check

Verifica la Definición de Terminado (DoD, sección 13.1 del SRS) para la fase del roadmap
que se está cerrando.

## Cuándo usarla
Antes de dar por cerrada cualquier fase del roadmap (`docs/SRS.md`, sección 13).

## Paso 0 — obligatorio, primero: auditoría de completitud funcional

Antes de cualquier otro ítem del checklist, armar una tabla explícita cruzando **cada**
RF/RNF y caso de uso (CU) que la sección 3/4/2.2 del SRS asocia a esa fase contra el estado
real: hecho / diferido explícitamente (con motivo) / **faltante sin haberlo dicho antes**.
No alcanza con "los tests pasan" — un RF puede no tener ningún test que lo cubra porque
directamente no se implementó, y eso no se nota si no se lista cada RF uno por uno. Esto
es lo que falló en la práctica una vez: se cerraron dos fases sin esta tabla explícita y
recién se detectaron los diferimientos (RF-010/CU-03, RF-013, RF-014) cuando el usuario
preguntó directamente. No repetir ese patrón — esta tabla se muestra siempre, se pida o no.

Si algo quedó afuera, distinguir explícitamente:
- **Diferido y ya acordado con el usuario** (ej. en una respuesta anterior del propio
  usuario, o en un anuncio de alcance que el usuario no objetó) → listar igual, con la
  referencia a cuándo se acordó.
- **Diferido pero nunca comunicado** → esto es lo que hay que evitar. Si aparece, avisar
  ahora, no asumir que está bien callarlo.

También revisar desviaciones deliberadas del texto literal de un criterio de aceptación
(ej. usar 404 en vez de 403 por una razón de seguridad concreta) — no son un problema, pero
deben quedar visibles y, si son ambiguas, preguntarse con `AskUserQuestion` en vez de
decidirse en silencio.

## Checklist (DoD del SRS, tal cual)
1. Código formateado y lint sin errores críticos.
2. Pruebas automatizadas pasando.
3. Cada requisito de la fase está implementado y asociado a al menos un test.
4. Logs y métricas disponibles para lo implementado en esta fase.
5. No existen secretos en el repositorio (correr el mismo tipo de escaneo usado en Fase 0).
6. Docker Compose levanta el entorno desde cero incluyendo lo nuevo de esta fase.
7. README actualizado si la fase agrega instalación/arquitectura/troubleshooting relevante.
8. Criterios de aceptación de la fase verificados manual o automáticamente.

## Qué NO hace
No decide por su cuenta que una fase está completa — reporta el estado de cada ítem del
checklist (empezando por la tabla del Paso 0) para que el usuario confirme el cierre.
