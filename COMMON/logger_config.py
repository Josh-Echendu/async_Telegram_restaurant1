import atexit
import logging
import os
import queue
import sys

from logging.handlers import QueueHandler, QueueListener, RotatingFileHandler

# Prevent configuring twice
_logger_initialized = False
_listener = None


def setup_logging():
    global _logger_initialized, _listener

    if _logger_initialized:
        return logging.getLogger()

    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    service_name = os.getenv("SERVICE_NAME", "APP")
    log_dir = os.getenv("LOG_DIR", "logs")

    os.makedirs(log_dir, exist_ok=True)

    log_queue = queue.Queue(-1)

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | "
        f"{service_name} | %(name)s | %(message)s"
    )

    ##################################################
    # Console
    ##################################################

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    ##################################################
    # File
    ##################################################

    file_handler = RotatingFileHandler(
        filename=f"{log_dir}/{service_name.lower()}.log",
        maxBytes=20 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )

    file_handler.setFormatter(formatter)

    ##################################################
    # Queue
    ##################################################

    queue_handler = QueueHandler(log_queue)

    root = logging.getLogger()
    root.setLevel(log_level)
    root.addHandler(queue_handler)

    _listener = QueueListener(
        log_queue,
        console_handler,
        file_handler,
    )

    _listener.start()

    atexit.register(_listener.stop)

    _logger_initialized = True

    return root


setup_logging()

logger = logging.getLogger()