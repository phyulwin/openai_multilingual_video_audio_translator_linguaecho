# media.py — Bounded FFprobe validation and FFmpeg audio extraction.
import json
import math
import subprocess
from pathlib import Path

EXTENSIONS = {'.mp4', '.mov', '.webm', '.mkv', '.mp3', '.wav', '.m4a'}


def run(command, timeout=120):
    """Run fixed argument arrays without a shell or user-supplied switches."""
    try:
        return subprocess.run(command, capture_output=True, check=True, timeout=timeout)
    except FileNotFoundError as exc:
        raise ValueError('FFmpeg and FFprobe must be installed and configured.') from exc
    except subprocess.TimeoutExpired as exc:
        raise ValueError('Media processing timed out.') from exc
    except subprocess.CalledProcessError as exc:
        raise ValueError('Media could not be decoded; upload a valid audio or video file.') from exc


def probe(path, config):
    """Validate the actual streams and bounded duration, not just extensions."""
    result = run([config['FFPROBE'], '-v', 'error', '-format_whitelist', 'mov,matroska,webm,mp3,wav', '-protocol_whitelist', 'file,pipe',
                  '-show_format', '-show_streams', '-of', 'json', str(path)], 30)
    metadata = json.loads(result.stdout)
    streams = metadata.get('streams', [])
    if not any(s.get('codec_type') == 'audio' for s in streams):
        raise ValueError('The file has no decodable audio track.')
    duration = float(metadata.get('format', {}).get('duration', 0))
    if not math.isfinite(duration) or duration <= 0 or duration > config['MAX_DURATION']:
        raise ValueError(f'Media duration must be between 0 and {config["MAX_DURATION"] / 60:g} minutes.')
    return {'duration': duration, 'kind': 'video' if any(s.get('codec_type') == 'video' for s in streams) else 'audio'}


def chunks(path, folder, duration, config):
    """Extract ten-minute mono chunks below the transcription upload limit."""
    for offset in range(0, math.ceil(duration), 600):
        destination = Path(folder) / f'chunk-{offset}.mp3'
        run([config['FFMPEG'], '-nostdin', '-y', '-v', 'error', '-format_whitelist', 'mov,matroska,webm,mp3,wav', '-protocol_whitelist', 'file,pipe',
             '-ss', str(offset), '-i', str(path), '-t', str(min(600, duration - offset)),
             '-map', '0:a:0', '-vn', '-ac', '1', '-ar', '16000', '-b:a', '64k', str(destination)], 180)
        if destination.stat().st_size >= 24 * 1024 * 1024:
            raise ValueError('Extracted audio exceeds the provider upload limit.')
        yield offset, destination


def segment_words(response, offset=0):
    """Group real timed words by punctuation, pauses, and a 15-second ceiling."""
    words = response.get('words') or []
    result, group = [], []
    for word in words:
        if not word.get('word', '').strip():
            continue
        if group and (word['start'] - group[-1]['end'] > 1.2 or word['end'] - group[0]['start'] > 15):
            result.append(group)
            group = []
        group.append(word)
        if word['word'].rstrip().endswith(('.', '!', '?', '。', '！', '？', '؟', '।')):
            result.append(group)
            group = []
    if group:
        result.append(group)
    if not result:
        # Timed segment fallback preserves provider text without fabricated alignment.
        result = [[{'word': s['text'], 'start': s['start'], 'end': s['end']}]
                  for s in response.get('segments', []) if s.get('text', '').strip()]
    output = []
    for group in result:
        start, end = float(group[0]['start']) + offset, float(group[-1]['end']) + offset
        if not math.isfinite(start + end) or start < 0 or end <= start or (output and start < output[-1]['end']):
            raise ValueError('Transcription returned invalid or overlapping timestamps.')
        text = ''.join(w['word'] if w['word'].startswith(' ') else (' ' if i else '') + w['word'] for i, w in enumerate(group)).strip()
        output.append({'start': start, 'end': end, 'original_text': text, 'favorite': False})
    return output
