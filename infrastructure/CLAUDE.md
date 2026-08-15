# infrastructure/ — CLAUDE.md

Docker Compose, Prometheus, Grafana, reverse proxy.

## Reglas específicas
- `docker-compose.yml` debe levantar el stack completo desde cero solo con `.env`
  (RNF-020) — sin pasos manuales fuera de Docker.
- Cambios a dashboards de Grafana o reglas de Prometheus se versionan aquí, no se hacen
  solo desde la UI.
- El reverse proxy fuerza HTTPS en despliegues públicos (RNF-011) — no delegarlo a la
  aplicación.
- Nada de Kubernetes ni orquestadores adicionales en el MVP (fuera de alcance explícito,
  sección 12 del SRS).
