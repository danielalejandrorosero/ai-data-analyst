---
name: update-adr
description: Creates a new, correctly numbered ADR in docs/adr/ when a technical decision not fixed by the SRS needs to be made during development. Keeps the SRS/architecture/ADR separation intact.
---

# update-adr

Crea un nuevo Architecture Decision Record cuando surge una decisión técnica durante el
desarrollo que el SRS no fija explícitamente.

## Cuándo usarla
Cuando el trabajo actual requiere decidir algo que `docs/SRS.md` deja abierto (como ya
pasó con auth, secretos, multi-tenant, tooling — ver `docs/adr/0001` a `0005`), o cuando se
reconsidera una decisión previa.

## Qué debe garantizar
1. Numeración secuencial correcta (`docs/adr/000N-titulo-corto.md`), sin reutilizar ni
   saltar números.
2. Estructura: Estado, Contexto, Decisión, Justificación, Consecuencias — igual que los
   ADR existentes.
3. **No** modifica `docs/SRS.md` para registrar la decisión — el SRS solo cambia si cambia
   un requisito funcional/no funcional real.
4. Si la decisión afecta cómo se construye el sistema de forma duradera, referencia el ADR
   desde `docs/architecture.md`.

## Qué NO hace
No crea un ADR para decisiones triviales o fácilmente reversibles (nombre de una variable,
detalle de implementación interno sin impacto arquitectónico) — eso no necesita registro.
