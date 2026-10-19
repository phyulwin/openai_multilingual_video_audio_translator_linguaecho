# config.py — Server-only configuration and provider capability allowlists.
import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / '.env')
SUPPORTED = 'af ar hy az be bs bg ca zh hr cs da nl en et fi fr gl de el he hi hu is id it ja kn kk ko lv lt mk ms mr mi ne no fa pl pt ro ru sr sk sl es sw sv tl ta th tr uk ur vi cy'.split()
VOICES = 'alloy ash ballad coral echo fable nova onyx sage shimmer verse marin cedar'.split()


def configuration(overrides=None):
    """Resolve configurable storage paths without putting credentials in responses."""
    db = os.getenv('DATABASE_URL', 'sqlite:///data/linguaecho.sqlite3')
    if not db.startswith('sqlite:///'):
        raise ValueError('DATABASE_URL must start with sqlite:///')
    settings = dict(
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
    for key in ('DATABASE', 'UPLOADS', 'AUDIO'):
        settings[key] = Path(settings[key]).resolve()
    settings['DATABASE'].parent.mkdir(parents=True, exist_ok=True)
    for key in ('UPLOADS', 'AUDIO'):
        settings[key].mkdir(parents=True, exist_ok=True)
    return settings
