import logging
import sys
import os
from logging.handlers import RotatingFileHandler

LOG_NAME = os.getenv('LOG_NAME', 'Project')
LOG_FILE = os.getenv('LOG_FILE', '/var/log/radio/radio.log')
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LOG_MAX_BYTES = int(os.getenv('LOG_MAX_BYTES', 10 * 1024 * 1024))
LOG_BACKUP_COUNT = int(os.getenv('LOG_BACKUP_COUNT', 3))

logger = logging.getLogger(LOG_NAME)

if not logger.handlers:
    logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
    fmt = logging.Formatter('%(asctime)s %(levelname)s [%(threadName)s] %(name)s: %(message)s')

    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(sh)

    fh = RotatingFileHandler(LOG_FILE, maxBytes=LOG_MAX_BYTES, backupCount=LOG_BACKUP_COUNT)
    fh.setFormatter(fmt)
    logger.addHandler(fh)
