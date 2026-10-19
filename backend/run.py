# run.py — Local Waitress entry point; never exposes the service publicly.
import logging
import os
from waitress import serve
from app import create_app

if __name__ == '__main__':
    # Keep background-worker exceptions visible in the local server log.
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    try:
        serve(create_app(), host='127.0.0.1', port=int(os.getenv('PORT', '5000')), threads=6)
    except KeyboardInterrupt:
        logging.info('LinguaEcho stopped.')
