"""Named job-worker modes. Celery is opt-in and off by default."""

WORKER_THREAD = "thread"
WORKER_INLINE = "inline"
WORKER_OFF = "off"
WORKER_CELERY = "celery"

SUPPORTED_WORKERS = frozenset(
    {WORKER_THREAD, WORKER_INLINE, WORKER_OFF, WORKER_CELERY}
)


def normalize_worker(raw: str | None) -> str:
    value = (raw or WORKER_THREAD).strip().lower()
    return value if value in SUPPORTED_WORKERS else WORKER_THREAD
