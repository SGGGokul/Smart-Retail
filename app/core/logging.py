import logging
import sys


def setup_logging(debug: bool = False) -> None:
    """Configure application-wide structured logging format."""
    log_level = logging.DEBUG if debug else logging.INFO

    log_format = (
        "%(asctime)s | %(levelname)-7s | %(name)s:%(lineno)d | %(message)s"
    )

    logging.basicConfig(
        level=log_level,
        format=log_format,
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True,
    )

    # Silence overly verbose external loggers
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)
