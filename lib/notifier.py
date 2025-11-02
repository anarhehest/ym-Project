import threading
import time
from typing import Optional

from lib.logger import logger

class Notifier:
    def __init__(self, cond: threading.Condition, min_interval: float = 0.05):
        self.cond = cond
        self.min_interval = float(min_interval)
        self._lock = threading.Lock()
        self._last = 0.0
        self._timer: Optional[threading.Timer] = None
        self._pending = False

    def _do_notify(self):
        with self._lock:
            self._timer = None
            self._pending = False
            self._last = time.monotonic()
        logger.debug("Notifier: performing notify_all")
        with self.cond:
            self.cond.notify_all()

    def request(self):
        now = time.monotonic()
        notify_now = False
        with self._lock:
            elapsed = now - self._last
            if elapsed >= self.min_interval:
                # notify immediately
                self._last = now
                if self._timer:
                    try:
                        self._timer.cancel()
                    except Exception:
                        logger.exception("Notifier: cancel timer failed")
                    self._timer = None
                    self._pending = False
                notify_now = True
            else:
                # schedule delayed notify if not already pending
                if not self._pending:
                    delay = self.min_interval - elapsed
                    t = threading.Timer(delay, self._do_notify)
                    t.daemon = True
                    t.start()
                    self._timer = t
                    self._pending = True
                    logger.debug("Notifier: scheduled delayed notify in %.3fs", delay)
        if notify_now:
            logger.debug("Notifier: notify_all immediate")
            with self.cond:
                self.cond.notify_all()

    def cancel(self):
        with self._lock:
            if self._timer:
                try:
                    self._timer.cancel()
                except Exception:
                    logger.exception("Notifier: cancel timer failed")
                self._timer = None
            self._pending = False

