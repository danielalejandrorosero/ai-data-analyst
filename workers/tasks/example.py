async def noop(ctx: dict) -> None:
    """Placeholder — ARQ exige al menos una function registrada en
    WorkerSettings para poder arrancar el worker (AssertionError si la
    lista esta vacia). Se reemplaza por jobs reales (import_dataset,
    agent_run) en Fase 1 en adelante; no es logica de negocio.
    """
    return None
