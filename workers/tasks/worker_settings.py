from app.core.config import settings
from arq.connections import RedisSettings
from arq.cron import cron

from tasks.analysis import run_analysis_job
from tasks.documents import process_document_job
from tasks.retention import purge_old_data_job


class WorkerSettings:
    """Configuración del worker ARQ (Fase 4 - RF-020 a RF-025).

    `run_analysis_job` reemplaza al placeholder `noop` de Fase 0. El
    timeout de job de ARQ se deja generoso (job_timeout) porque el propio
    `run_analysis` ya impone su timeout interno (agent_sql_timeout_seconds
    * 4) y deja el Analysis en TIMED_OUT antes de llegar a este límite -
    este es solo un backstop para que ARQ no lo deje colgado si algo falla
    de forma completamente inesperada.

    `purge_old_data_job` (RF-053) corre como cron job diario a las 3am -
    horario de baja actividad esperada, no es un valor critico. Es el
    unico job de esta lista que no se encola desde la API: ARQ lo dispara
    solo via `cron_jobs`.
    """

    functions = [run_analysis_job, process_document_job]
    cron_jobs = [cron(purge_old_data_job, hour=3, minute=0)]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    job_timeout = settings.agent_sql_timeout_seconds * 8
    # RNF-004 ("al menos 20 analisis simultaneos"): arq.Worker.max_jobs
    # default es 10 y nunca se pisaba aca - confirmado con una corrida real
    # de 20 analisis (backend/tests/integration/test_concurrent_analyses.py)
    # que el worker los procesaba en dos tandas de ~10 (logs de arq
    # mostrando `delayed=Ns` en la segunda tanda), no en paralelo real.
    # 25 deja margen sobre el minimo pedido por el RNF.
    max_jobs = 25
    # RF-025: sin esto, Job.abort() (POST /analyses/{id}/cancel) solo
    # afecta jobs que todavia estan en cola - para un job YA corriendo no
    # hace nada en absoluto (arq simplemente no lo mira). Confirmado
    # empiricamente contra Docker real: sin este flag, cancelar un analisis
    # en curso no interrumpe nada, el job termina normal.
    allow_abort_jobs = True
