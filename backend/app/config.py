# config.py — Server-only configuration and provider capability allowlists.
import os
import json
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
# Explicit local settings take precedence over keys inherited from the launcher.
if os.getenv('APP_ENV') != 'production':
    load_dotenv(ROOT / '.env', override=True)
SUPPORTED = 'af ar hy az be bs bg ca zh hr cs da nl en et fi fr gl de el he hi hu is id it ja kn kk ko lv lt mk ms mr mi ne no fa pl pt ro ru sr sk sl es sw sv tl ta th tr uk ur vi cy'.split()
VOICES = 'alloy ash ballad coral echo fable nova onyx sage shimmer verse marin cedar'.split()


def url_origin(value):
    """Normalize origins for an exact production CORS allowlist."""
    from urllib.parse import urlsplit
    parsed = urlsplit(value)
    return f'{parsed.scheme}://{parsed.netloc}' if not parsed.username and not parsed.password else ''


def configuration(overrides=None):
    """Resolve configurable storage paths without putting credentials in responses."""
    db = os.getenv('DATABASE_URL', 'sqlite:///data/linguaecho.sqlite3')
    if not db.startswith('sqlite:///'):
        raise ValueError('DATABASE_URL must start with sqlite:///')
    production = os.getenv('APP_ENV') == 'production'
    settings = dict(
        PRODUCTION=production,
        ALLOWED_ORIGINS=os.getenv('ALLOWED_ORIGINS', '').split(','),
        ACCESS_USERS=json.loads(os.getenv('ACCESS_USERS', '{}')),
        REQUEST_JOBS=production,
        JOB_SECONDS=240,
        TEMP_TTL_SECONDS=3600,
        MAX_PROJECTS=10,
        MAX_TEMP_BYTES=384 * 1024 * 1024,
        DATABASE=ROOT / db.removeprefix('sqlite:///'),
        UPLOADS=ROOT / os.getenv('UPLOAD_DIRECTORY', 'data/uploads'),
        AUDIO=ROOT / os.getenv('GENERATED_AUDIO_DIRECTORY', 'data/audio'),
        MAX_CONTENT_LENGTH=int(os.getenv('MAX_UPLOAD_MB', '200')) * 1024 * 1024,
        MAX_DURATION=float(os.getenv('MAX_DURATION_SECONDS', '7200')),
        FFMPEG=os.getenv('FFMPEG_BINARY', 'ffmpeg'),
        FFPROBE=os.getenv('FFPROBE_BINARY', 'ffprobe'),
        API_KEY=os.getenv('OPENAI_API_KEY', ''),
        TRANSCRIPTION_MODEL=os.getenv('OPENAI_TRANSCRIPTION_MODEL', 'whisper-1'),
        TRANSLATION_MODEL=os.getenv('OPENAI_TRANSLATION_MODEL', 'gpt-4.1-mini'),
        TTS_MODEL=os.getenv('OPENAI_TTS_MODEL', 'gpt-4o-mini-tts'),
        VOICE=os.getenv('OPENAI_TTS_VOICE', 'coral'),
    )
    settings.update(overrides or {})
    if settings['PRODUCTION']:
        # Fail closed: production never inherits local credentials or durable paths.
        users = settings['ACCESS_USERS']
        if not isinstance(users, dict) or not users or any(
                len(k) != 64 or any(c not in '0123456789abcdef' for c in k)
                or not isinstance(v, str) or not v for k, v in users.items()):
            raise ValueError('ACCESS_USERS must map SHA-256 access-token hashes to individual user IDs.')
        if len(set(settings['ACCESS_USERS'].values())) != len(settings['ACCESS_USERS']):
            raise ValueError('Each access token must identify a distinct user.')
        if not settings['ALLOWED_ORIGINS'] or any(not o.startswith('https://') or url_origin(o) != o for o in settings['ALLOWED_ORIGINS']):
            raise ValueError('ALLOWED_ORIGINS must contain exact HTTPS origins without paths.')
        settings.update(DATABASE=Path('/tmp/linguaecho/projects.sqlite3'),
                        UPLOADS=Path('/tmp/linguaecho/uploads'), AUDIO=Path('/tmp/linguaecho/audio'),
                        MAX_CONTENT_LENGTH=25 * 1024 * 1024, MAX_DURATION=300)
    for key in ('DATABASE', 'UPLOADS', 'AUDIO'):
        settings[key] = Path(settings[key]).resolve()
    settings['DATABASE'].parent.mkdir(parents=True, exist_ok=True)
    for key in ('UPLOADS', 'AUDIO'):
        settings[key].mkdir(parents=True, exist_ok=True)
    return settings
