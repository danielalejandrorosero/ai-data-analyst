---
paths:
  - "backend/**/*.py"
---

# Backend conventions

Convenciones de código para `backend/` (FastAPI + Pydantic v2 + SQLAlchemy 2), gestionado
con **uv**. Complementa `backend/CLAUDE.md`, no lo repite.

- Routers son delgados: reciben el request, delegan a la capa de servicio de dominio
  (`app/domain/*`), devuelven el schema de respuesta. Sin lógica de negocio en el router.
- Los schemas de request/response (Pydantic v2) viven separados de los modelos SQLAlchemy —
  no se expone el modelo ORM directamente como contrato de API.
- Configuración y secretos se leen vía `app/core/config` (variables de entorno), nunca
  hardcodeados ni leídos ad-hoc con `os.environ` disperso en el código.
- Errores de dominio se traducen a códigos HTTP explícitos y consistentes (403 para
  autorización, 404 para recursos no encontrados dentro del tenant correcto, etc.) — no
  se devuelven stack traces ni detalles internos al cliente.
- Cambios de dependencias van vía `uv add`/`uv remove` y el lockfile (`uv.lock`) se
  commitea siempre junto con el cambio.
