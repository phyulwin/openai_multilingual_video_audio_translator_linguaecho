# cloud_run.py — One process with threaded HTTP service for bounded request-owned jobs.
import logging
import os
from waitress import serve
from app import create_app


if __name__ == '__main__':
    # Cloud Run terminates TLS; no background job depends on idle CPU allocation.
    logging.basicConfig(level=logging.INFO)
    try:
        serve(create_app(), host='0.0.0.0', port=int(os.environ.get('PORT', '8080')),
              threads=8, max_request_body_size=25 * 1024 * 1024,
              channel_timeout=600, connection_limit=32, trusted_proxy='*',
              trusted_proxy_headers={'x-forwarded-proto'})
    except KeyboardInterrupt:
        logging.info('Service stopped; temporary work is not durable.')
