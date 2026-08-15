---
paths:
  - "backend/**"
  - "workers/**"
---

# Security

Checklist accionable derivado del threat model (`docs/security/threat-model.md` y
sección 8 del SRS). Principio rector: **el modelo propone, el software autoriza** — ningún
control crítico depende del comportamiento del LLM.

- Las consultas del agente SIEMPRE usan credenciales de solo lectura sobre la fuente
  externa. Nunca reutilizar una conexión con permisos de escritura para el canal del agente.
- Toda sentencia SQL generada por el agente pasa por el validator (allowlist de `SELECT` +
  expresiones autorizadas) antes de tocar la fuente externa. No añadir bypasses "temporales".
- Ningún secreto (credenciales de fuentes de datos, API keys de LLM, tokens) se escribe en
  texto plano en tablas de negocio, logs, mensajes de commit o código. Usar el mecanismo de
  `secret_ref` (ver `docs/adr/0004-secrets-management.md`).
- Todo endpoint protegido valida rol y `organization_id` antes de tocar datos — el
  aislamiento de tenant es responsabilidad del backend, nunca del cliente.
- Contenido proveniente de documentos, archivos importados o fuentes externas no confiables
  se trata como no confiable: no puede alterar el comportamiento del agente ni las políticas
  de ejecución (defensa contra prompt injection, RNF-015).
- Todo tool call y toda decisión de autorización relevante se audita (`audit_events`) con
  actor, timestamp y contexto suficiente para reconstrucción, sin exponer secretos.
- Timeout y límite de filas son obligatorios en toda consulta del agente (RF-032, RNF-003) —
  no se pueden desactivar para "probar más rápido".
- Rate limiting por usuario y tenant se respeta en toda ruta que dispare ejecución de
  agente o consultas a fuentes externas.
