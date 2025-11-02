import json
import os
import random
import signal
import sys
import threading
import time
from typing import Optional

import yandex_music as ym
import yandex_music.exceptions as ym_exceptions
from dotenv import load_dotenv
from flask import Flask, Response, stream_with_context, render_template, request

from lib.ring import RingBuffer
from lib.notifier import Notifier
from lib.logger import logger

app = Flask(__name__)
app.logger = logger

CHUNK = 2048
RATE = 44100
FILL_INTERVAL = 0.04
SEND_INTERVAL = 0.01
WAIT_INTERVAL = 1.00
NOTE_INTERVAL = 0.05
KEEP_INTERVAL = 60.0
TRACK_META_DESIRED_SECONDS = 2
MAX_BUFFER_SECONDS = 0.1
MAX_BUFFER_SIZE = int(MAX_BUFFER_SECONDS * RATE * 2)

buffer = RingBuffer(MAX_BUFFER_SIZE)
buffer_cond = threading.Condition()
notifier = Notifier(buffer_cond, min_interval=NOTE_INTERVAL)
base_index = 0
track_meta = {}
track_meta_start = 0
track_meta_threshold = 0
track_done_event = threading.Event()
stop_event = threading.Event()


def fetch_random_track(track_list, wait_interval=WAIT_INTERVAL):
    global buffer_cond, notifier, stop_event, track_meta
    next_track_time = 0.0
    while not stop_event.is_set():
        now = time.time()
        if now < next_track_time:
            to_wait = min(wait_interval, next_track_time - now)
            time.sleep(to_wait)
            continue

        try:
            entry = random.choice(track_list)
            if hasattr(entry, 'fetch_track'):
                track = entry.fetch_track()
                duration_ms = track.duration_ms
                bitrate = 320
            elif hasattr(entry, 'download_bytes'):
                track = entry
                duration_ms = 30_000    # fallback as YM has limitations
                bitrate = 128           # for not authenticated users
            else:
                raise TypeError('Unknown entry type')
        except ym_exceptions.YandexMusicError:
            logger.exception('Error fetching track; retrying in %.1f seconds...', wait_interval)
            time.sleep(wait_interval)
            continue

        track_meta = {
            'id': track['id'],
            'album_id': track['albums'][0]['id'],
            'title': track['title'],
            'artists': [x.name for x in track['artists']],
            'cover_uri': track['cover_uri'],
            'duration_ms': duration_ms,
            'bitrate_kbps': bitrate,
        }

        next_track_time = time.time() + (duration_ms / 1000.0)
        if next_track_time < time.time():
            next_track_time = time.time()

        try:
            data = track.download_bytes(bitrate_in_kbps=bitrate)
        except ym_exceptions.YandexMusicError:
            logger.exception('Failed to fetch track bytes; skipping')
            continue

        yield data


def needle(track_list, chunk_size=CHUNK, fill_interval=FILL_INTERVAL):
    global buffer, buffer_cond, base_index, notifier, stop_event
    global track_meta, track_meta_start, track_meta_threshold
    logger.info('needle thread started')
    data_gen = fetch_random_track(track_list)
    for data in data_gen:
        if stop_event.is_set():
            break
        pos = 0
        data_len = len(data)
        logger.debug("needle: new track data_len=%d", data_len)

        first_chunk = True
        while pos < data_len and not stop_event.is_set():
            end = min(pos + chunk_size, data_len)
            chunk = data[pos:end]
            pos = end

            with buffer_cond:
                overflow = buffer.write(chunk)
                if overflow:
                    base_index += overflow
                    logger.debug('buffer overflowed: dropped %d bytes, base_index=%d', overflow, base_index)

                if first_chunk:
                    track_meta_start = base_index + len(buffer)
                    bitrate = track_meta.get('bitrate_kbps', 128)
                    track_meta_threshold = int((bitrate * 1000 / 8) * TRACK_META_DESIRED_SECONDS)
                    logger.debug('track_meta_start=%d threshold=%d (bitrate=%d)',
                                 track_meta_start, track_meta_threshold, bitrate)

                    notifier.request()
                    buffer_cond.notify_all()
                    first_chunk = False

            time.sleep(fill_interval)
    logger.info('needle thread exiting')


def stream_generator(chunk_size=CHUNK, send_interval=SEND_INTERVAL):
    global buffer, buffer_cond, base_index, stop_event
    with buffer_cond:
        client_abs_offset = base_index + len(buffer)
    logger.debug("stream_generator start client_abs_offset=%d", client_abs_offset)

    while not stop_event.is_set():
        to_send: Optional[bytes] = None
        with buffer_cond:
            buf_len = len(buffer)
            rel = client_abs_offset - base_index

            if rel < 0 or rel > buf_len:
                client_abs_offset = base_index + buf_len
                rel = client_abs_offset - base_index

            available = buf_len - rel
            if available > 0:
                take = min(available, chunk_size)
                to_send = buffer.read_at(rel, take)
                client_abs_offset += len(to_send)
            else:
                buffer_cond.wait(timeout=send_interval)

        if to_send:
            yield to_send
        else:
            continue

    logger.debug("stream_generator exiting")
    return


def meta_sse_generator(wait_interval=WAIT_INTERVAL, keepalive_interval=KEEP_INTERVAL):
    global base_index, buffer, stop_event
    global track_meta, track_meta_start, track_meta_threshold
    last_sent = None
    since_keepalive = 0
    while not stop_event.is_set():
        with buffer_cond:
            buffer_cond.wait(timeout=wait_interval)
            current_meta = dict(track_meta) if track_meta else None
            current_start = track_meta_start
            current_threshold = track_meta_threshold
            server_pos = base_index + len(buffer)

        if not current_meta or current_start is None or current_threshold is None:
            since_keepalive += wait_interval
            if since_keepalive >= keepalive_interval:
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


@app.route('/stream')
def stream():
    logger.info('Client connected to /stream')
    return Response(stream_with_context(stream_generator()), mimetype='audio/mpeg')


@app.route('/stream/meta')
def meta():
    logger.info('Client connected to /stream/meta')
    headers = {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no"
    }
    return Response(stream_with_context(meta_sse_generator()), headers=headers)


@app.route('/')
def index():
    return Response(render_template('index.html'), mimetype='text/html')


def shutdown(signum=None, frame=None, wait_interval=WAIT_INTERVAL):
    global buffer_cond, notifier, stop_event
    logger.info('Shutdown initiated')
    stop_event.set()
    notifier.cancel()
    with buffer_cond:
        buffer_cond.notify_all()
        buffer_cond.wait(wait_interval)
    try:
        shutdown_func = request.environ.get('werkzeug.server.shutdown')
        if callable(shutdown_func):
            shutdown_func()
            logger.info('Werkzeug shutdown called')
        else:
            logger.warning('werkzeug.server.shutdown not available in environ')
    except RuntimeError:
        logger.exception('werkzeug.server.shutdown failed')
    logger.info('Exiting process')
    if signum is not None:
        sys.exit(0)


if __name__ == '__main__':
    load_dotenv()

    logger.info('Starting application')

    ym_client = ym.Client(os.getenv('YM_TOKEN'),)
    try:
        ym_client.init()
    except ym_exceptions.YandexMusicError:
        logger.exception('Error initializing yandex_music client')

    try:
        tracks = ym_client.users_likes_tracks()
    except ym_exceptions.YandexMusicError:
        logger.exception('Failed to obtain tracks; falling back to билборды')
        tracks = ym_client.artists_tracks(11518857, page_size=100)

    worker = threading.Thread(target=needle, args=(tracks,), daemon=True)
    worker.start()
    logger.info('Background worker started')

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    app.run(host='0.0.0.0', port=9000, debug=False, threaded=True, use_reloader=False)
