# Testing

Mapa de estrategia de pruebas (SRS sección 10) a nivel de todo el repositorio.

| Nivel | Herramienta | Para qué |
|---|---|---|
| Unitarias | Pytest | Reglas de dominio, SQL validator, servicios, agent tools |
| Integración | Pytest + DB/Redis reales | FastAPI + PostgreSQL + Redis end-to-end de un flujo |
| Frontend | Vitest + React Testing Library | Componentes y flujos de UI |
| E2E | Playwright | Login, conexión de dataset, análisis, visualización |
| Carga | k6/Locust | Latencias y concurrencia (RNF-001, RNF-004) |
| Seguridad | Tests negativos | Intentos de superar RBAC, SQL controls, límites |
| Evaluación IA | Dataset de preguntas de referencia | Exactitud SQL, faithfulness, utilidad (sección 10.1) |

## Componentes considerados críticos (RNF-021)

Auth, SQL validator, agent tools y API crítica **deben** tener test antes de considerarse
terminados (DoD, sección 13.1 del SRS). Un PR que toque estos componentes sin test asociado
no está completo.

## Reglas

- Todo componente crítico incluye al menos un caso negativo (acceso no autorizado, SQL
  destructivo, cruce de tenant), no solo el camino feliz.
- Los tests de integración usan una base de datos de prueba real (o Testcontainers), no
  mocks del ORM — evita divergencias entre lo que pasa el test y lo que pasa en producción.
- Los tests E2E cubren como mínimo el flujo principal: login -> conectar/cargar dataset ->
  preguntar -> ver resultado (criterio de aceptación del producto, sección 15 del SRS).
