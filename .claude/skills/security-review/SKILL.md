---
name: security-review
description: Project-specific security review against this repo's threat model (SQL injection via LLM, prompt injection, cross-tenant access, secret leakage) — complements the generic security-review skill.
---

# security-review (proyecto)

Revisión de seguridad especializada en el threat model de AI Data Analyst
(`docs/security/threat-model.md`, SRS sección 8.1). Complementa — no reemplaza — la skill
genérica `security-review` (revisión OWASP general): esta versión conoce los controles
específicos de este proyecto.

## Cuándo usarla
Antes de mergear cambios en auth, SQL validator, agent tools, manejo de secretos o
cualquier código que toque `organization_id`/tenant scoping.

## Qué revisa
1. **SQL injection vía LLM**: toda ejecución de SQL generado por el agente pasa por el
   validator (allowlist + DB read-only). Ninguna ruta nueva lo bypassa.
2. **Prompt injection**: contenido no confiable (documentos, datos importados) no puede
   alterar qué tools se autorizan ni los límites de ejecución.
3. **Cross-tenant access**: todo query/endpoint nuevo filtra por `organization_id` en la
   capa de servicio, no solo en el router.
4. **Secret leakage**: no hay secretos en texto plano en modelos, logs, mensajes de error
   o mensajes de commit.
5. **DoS por consultas pesadas**: timeout y límite de filas presentes en toda ejecución de
   SQL del agente.
6. **Carga maliciosa de archivo**: imports de CSV/Excel validan tamaño, MIME y contenido
   antes de procesar.

## Qué NO hace
No reemplaza un pentest ni un scanner automatizado de dependencias (eso es CI, sección
11.1 del SRS) — es una revisión de código dirigida al threat model del dominio.
