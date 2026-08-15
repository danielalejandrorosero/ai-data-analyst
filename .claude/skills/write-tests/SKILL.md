---
name: write-tests
description: Generates test skeletons at the correct level (unit/integration/frontend/e2e/eval) for a given RF/RNF, following the testing strategy in the SRS.
---

# write-tests

Genera el esqueleto de test correcto para un requisito o cambio, según la tabla de
estrategia de pruebas del SRS (sección 10).

## Cuándo usarla
Al implementar cualquier RF/RNF, o cuando `.claude/rules/testing.md` señale que un
componente crítico (auth, SQL validator, agent tools, API crítica — RNF-021) quedó sin
cobertura.

## Qué debe garantizar
1. Identifica el nivel correcto: unitario (Pytest), integración (Pytest + DB/Redis real),
   frontend (Vitest + RTL), e2e (Playwright) o evaluación de agente (dataset de preguntas).
2. Para componentes críticos de seguridad (RBAC, tenant isolation, SQL read-only), incluye
   siempre un caso negativo, no solo el camino feliz.
3. No deja el requisito "implementado" sin al menos un test asociado (DoD, sección 13.1
   del SRS).

## Qué NO hace
No reemplaza la evaluación específica del agente (sección 10.1 del SRS) por tests unitarios
genéricos — esa evaluación necesita su propio dataset de preguntas de referencia.
