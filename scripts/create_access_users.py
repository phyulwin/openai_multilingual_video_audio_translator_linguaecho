# create_access_users.py — Provision individual high-entropy access tokens offline.
import argparse
import hashlib
import json
import secrets
from pathlib import Path


def main():
    """Write only credential hashes to the backend manifest; display tokens once."""
    parser = argparse.ArgumentParser(description='Create a distinct token for each invited user.')
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('users', nargs='+')
    args = parser.parse_args()
    if len(set(args.users)) != len(args.users):
        parser.error('User identifiers must be unique.')
    manifest, credentials = {}, []
    for user in args.users:
        token = secrets.token_urlsafe(32)
        manifest[hashlib.sha256(token.encode()).hexdigest()] = user
        credentials.append((user, token))
    try:
        # Exclusive creation prevents silently replacing a deployed access list.
        with args.output.open('x', encoding='utf-8') as output:
            json.dump(manifest, output)
        for user, token in credentials:
            print(f'{user}: {token}')
        print('Store tokens privately and distribute individually; never commit or bundle them.')
    except OSError as exc:
        raise SystemExit(f'Could not create the access manifest: {exc}') from exc


if __name__ == '__main__':
    # No account creation, networking, cloud changes, or paid calls occur here.
    main()
