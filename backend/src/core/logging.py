import logging

from core.config import settings as settings_log

_LOG_FORMAT = '%(asctime)s %(levelname)-8s %(name)s: %(message)s'
_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'


def setup_logging() -> None:
    # Configure the stdlib root logger once, at startup.
    # Every module calls `logging.getLogger(__name__)` and inherits this config.
    # `force=True` wipes any handlers FastAPI/uvicorn installed before us, so
    # we don't end up with duplicate log lines.
    level = getattr(logging, settings_log.log_level.upper(), logging.INFO)

    logging.basicConfig(
        level=level,
        format=_LOG_FORMAT,
        datefmt=_DATE_FORMAT,
        force=True,
    )

    # Uvicorn ships its own loggers (`uvicorn`, `uvicorn.error`, `uvicorn.access`).
    # Let them inherit the root config above instead of their own formatter.
    for name in ('uvicorn', 'uvicorn.error', 'uvicorn.access'):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers.clear()
        uvicorn_logger.propagate = True
