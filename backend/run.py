# run.py — Local Waitress entry point; never exposes the service publicly.
import logging
import os
import socket
from waitress import serve
from app import create_app


def create_listener(port):
    """Reserve the loopback port exclusively so stale servers cannot share requests."""
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        if os.name == 'nt':
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        else:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(('127.0.0.1', port))
        listener.listen(128)
        return listener
    except OSError:
        listener.close()
        raise


if __name__ == '__main__':
    # Keep background-worker exceptions visible in the local server log.
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    try:
        # Bind before constructing workers; duplicate launches must not alter jobs.
        with create_listener(int(os.getenv('PORT', '5000'))) as listener:
            serve(create_app(), sockets=[listener], threads=6)
    except KeyboardInterrupt:
        logging.info('LinguaEcho stopped.')
    except OSError as exc:
        raise SystemExit('Cannot open the local server port; stop the existing LinguaEcho server before restarting.') from exc
