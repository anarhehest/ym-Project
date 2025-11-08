import json
import random
import threading
import time
from typing import Optional, Generator

import yandex_music as ym
import yandex_music.exceptions as ym_exceptions

from lib.ring import RingBuffer
from lib.logger import logger


class Stream(ym.Client):
    CHUNK = 2048
    RATE = 44100
    BITRATE = 320
    FILL_INTERVAL = 0.04
    SEND_INTERVAL = 0.01
    WAIT_INTERVAL = 1.00
    NOTE_INTERVAL = 0.05
    KEEP_INTERVAL = 60.0
    TRACK_META_DESIRED_SECONDS = 2
    MAX_BUFFER_SECONDS = 0.1
    MAX_BUFFER_SIZE = int(MAX_BUFFER_SECONDS * RATE * 2)

    def __init__(self, token: str = None) -> None:
        super().__init__(token=token)
        self.init()
        self.track_list = self.users_likes_tracks()

        self._base_index = 0
        self._buffer = RingBuffer(self.MAX_BUFFER_SIZE)

        self._track_meta = {}
        self._track_meta_start = 0
        self._track_meta_threshold = 0
        self._track_done_event = threading.Event()

        self._cond = threading.Condition()
        self._stop_event = threading.Event()
        self._producer_thread: Optional[threading.Thread] = None

    def _data_generator(self) -> Generator[bytes, None, None]:
        next_track_time = 0.0
        while not self._stop_event.is_set():
            now = time.time()
            if now < next_track_time:
                to_wait = min(self.WAIT_INTERVAL, next_track_time - now)
                time.sleep(to_wait)
                continue

            entry = random.choice(self.track_list)

            try:
                track = entry.fetch_track()
            except ym_exceptions.YandexMusicError:
                logger.exception('Error fetching track; retrying in %.1f seconds...', self.WAIT_INTERVAL)
                time.sleep(self.WAIT_INTERVAL)
                continue

            duration_ms = track.duration_ms
            bitrate = self.BITRATE
            self._track_meta = {
                'id': track['id'],
                'album_id': track['albums'][0]['id'],
                'title': track['title'],
                'artists': [x.name for x in track['artists']],
                'cover_uri': track['cover_uri'],
                'duration_ms': duration_ms,
                'bitrate_kbps': bitrate,
            }

            try:
                data = track.download_bytes(bitrate_in_kbps=bitrate)
            except ym_exceptions.YandexMusicError:
                logger.exception('Failed to fetch track bytes; skipping')
                continue

            next_track_time = time.time() + (duration_ms / 1000.0)
            if next_track_time < time.time():
                next_track_time = time.time()

            yield data

    def producer(self) -> None:
        logger.debug('needle thread started')
        data_gen = self._data_generator()
        for data in data_gen:
            if self._stop_event.is_set():
                break
            pos = 0
            data_len = len(data)
            logger.debug("needle: new track data_len=%d", data_len)

            first_chunk = True
            while pos < data_len and not self._stop_event.is_set():
                end = min(pos + self.CHUNK, data_len)
                chunk = data[pos:end]
                pos = end

                with self._cond:
                    overflow = self._buffer.write(chunk)
                    if overflow:
                        self._base_index += overflow
                        logger.debug('buffer overflowed: dropped %d bytes, base_index=%d', overflow, self._base_index)

                    if first_chunk:
                        self._track_meta_start = self._base_index + len(self._buffer)
                        bitrate = self._track_meta.get('bitrate_kbps', 128)
                        self._track_meta_threshold = int((bitrate * 1000 / 8) * self.TRACK_META_DESIRED_SECONDS)
                        logger.debug('track_meta_start=%d threshold=%d (bitrate=%d)',
                                     self._track_meta_start, self._track_meta_threshold, bitrate)

                        self._cond.notify_all()
                        first_chunk = False

                time.sleep(self.FILL_INTERVAL)

        logger.debug('needle thread exiting')
        return

    def stream_generator(self) -> Generator[bytes, None, None]:
        with self._cond:
            client_abs_offset = self._base_index + len(self._buffer)
        logger.debug("stream_generator start client_abs_offset=%d", client_abs_offset)

        while not self._stop_event.is_set():
            to_send: Optional[bytes] = None
            with self._cond:
                buf_len = len(self._buffer)
                rel = client_abs_offset - self._base_index

                if rel < 0 or rel > buf_len:
                    client_abs_offset = self._base_index + buf_len
                    rel = client_abs_offset - self._base_index

                available = buf_len - rel
                if available <= 0:
                    self._cond.wait(timeout=self.SEND_INTERVAL)
                    logger.debug("stream_generator: no bytes available")
                    continue

                take = min(available, self.CHUNK)
                to_send = self._buffer.read_at(rel, take)
                client_abs_offset += len(to_send)

            if to_send:
                yield to_send

        logger.debug("stream_generator exiting")
        return

    def meta_sse_generator(self) -> Generator[str, None, None]:
        last_sent = None
        since_keepalive = 0
        while not self._stop_event.is_set():
            with self._cond:
                self._cond.wait(timeout=self.WAIT_INTERVAL)
                current_meta = dict(self._track_meta) if self._track_meta else None
                current_start = self._track_meta_start
                current_threshold = self._track_meta_threshold
                server_pos = self._base_index + len(self._buffer)

            if not current_meta or current_start is None or current_threshold is None:
                since_keepalive += self.WAIT_INTERVAL
                if since_keepalive >= self.KEEP_INTERVAL:
                    yield ": keep-alive\n\n"
                    since_keepalive = 0
                continue

            if server_pos >= (current_start + current_threshold):
                if current_meta != last_sent:
                    payload = json.dumps(current_meta)
                    logger.info("meta_sse_generator: sending meta %s (server_pos=%d start=%d threshold=%d)",
                                current_meta, server_pos, current_start, current_threshold)
                    yield f'data: {payload}\n\n'
                    last_sent = current_meta

        logger.debug("meta_sse_generator exiting")
        return

    def start(self) -> None:
        if self._producer_thread and self._producer_thread.is_alive():
            return
        self._base_index = 0
        self._track_meta = {}
        self._track_meta_start = 0
        self._track_meta_threshold = 0

        self._track_done_event.clear()
        self._stop_event.clear()

        self._producer_thread = threading.Thread(target=self.producer, daemon=True)
        self._producer_thread.start()
        logger.debug("started producer thread")

    def stop(self) -> None:
        self._stop_event.set()
        with self._cond:
            self._cond.notify_all()

        if self._producer_thread.is_alive():
            with self._cond:
                self._cond.notify_all()

            self._producer_thread.join(timeout=self.WAIT_INTERVAL)

        if self._producer_thread.is_alive():
            logger.warning("producer thread is still alive")
        else:
            self._producer_thread = None
            logger.debug("producer thread stopped")