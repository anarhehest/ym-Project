import os
import signal
import sys

from dotenv import load_dotenv
from flask import Flask, Response, stream_with_context, render_template

load_dotenv()

from lib.logger import logger
from lib.stream import Stream

app = Flask(__name__)
app.logger = logger

ym_stream = None


@app.route('/stream')
def stream():
    logger.info('Client connected to /stream')
    return Response(stream_with_context(ym_stream.stream_generator()), mimetype='audio/mpeg')


@app.route('/stream/meta')
def stream_meta():
    logger.info('Client connected to /stream/meta')
    headers = {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no"
    }
    return Response(stream_with_context(ym_stream.meta_sse_generator()), headers=headers)


@app.route('/')
def index():
    return Response(render_template('index.html'), mimetype='text/html')


def shutdown_handler(sig: int = None, frame: int = None):
    logger.info('Shutdown initiated')
    ym_stream.stop()
    if sig is not None:
        sys.exit(0)


if __name__ == '__main__':
    ym_stream = Stream(token=os.getenv('YM_TOKEN'), )
    ym_stream.start()

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    app.run(host='0.0.0.0', port=9000, debug=False, threaded=True, use_reloader=False)
