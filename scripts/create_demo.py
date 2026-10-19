# create_demo.py — Generate explicit offline fixtures without calling an AI API.
import json
import subprocess
import sys
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from app.config import configuration
from app.services.media import run


def create():
    """Use installed Windows voices and original artwork for a reproducible sample."""
    folder = ROOT / 'fixtures'
    folder.mkdir(exist_ok=True)
    originals = ['こんにちは。今日はいい天気ですね。', 'この場所はとても特別なんです。', '私たちはいつもここで話をします。', '季節が変わっても、変わらないものがあります。', 'きっと、どこかでまた会えますよ。', 'それまで、元気でいてくださいね。']
    translations = ['Hello. It is a beautiful day today.', 'This place is very special to me.', 'We always talk here.', 'Even when the seasons change, some things never change.', 'I am sure we will meet again someday.', 'Until then, please take care.']
    # Serialize speech input to avoid interpolating user content into executable code.
    (folder / 'script.json').write_text(json.dumps({'originals': originals, 'translations': translations}, ensure_ascii=False), encoding='utf-8')
    script = ROOT / 'scripts/demo-voices.ps1'
    subprocess.run(['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(script), '-FixtureDirectory', str(folder)], check=True)
    config = configuration()
    segments, cursor, audio_data = [], 0.0, bytearray()
    params = None
    for index, text in enumerate(originals, 1):
        with wave.open(str(folder / f'ja-{index}.wav'), 'rb') as audio:
            if params is None:
                params = audio.getparams()
            silence = bytes(int(params.framerate * .5) * params.sampwidth * params.nchannels)
            audio_data.extend(silence)
            cursor += .5
            start = cursor
            audio_data.extend(audio.readframes(audio.getnframes()))
            cursor += audio.getnframes() / audio.getframerate()
        segments.append({'id': index, 'start': start, 'end': cursor, 'original_text': text, 'favorite': False})
    audio_data.extend(bytes(params.framerate * params.sampwidth * params.nchannels))
    cursor += 1
    with wave.open(str(folder / 'original.wav'), 'wb') as output:
        output.setparams(params)
        output.writeframes(audio_data)
    # Encode a standard browser-compatible video with the generated local speech.
    run([config['FFMPEG'], '-y', '-v', 'error', '-loop', '1', '-i', str(ROOT / 'frontend/public/hero.png'),
         '-i', str(folder / 'original.wav'), '-vf', 'scale=1280:426,pad=1280:720:0:147:color=0x2d4c39',
         '-c:v', 'libx264', '-preset', 'ultrafast', '-tune', 'stillimage', '-pix_fmt', 'yuv420p', '-c:a', 'aac',
         '-shortest', '-movflags', '+faststart', str(folder / 'demo.mp4')], 180)
    project = {'name': 'A little place in the world · Demo', 'filename': 'demo.mp4', 'kind': 'video',
               'duration': cursor, 'source_language': 'ja', 'segments': segments,
               'translations': {'en': {'texts': {str(i + 1): t for i, t in enumerate(translations)}, 'audio': {}, 'voice': 'coral'}},
               'favorite': False, 'demo': True, 'status': 'ready', 'progress': 100,
               'message': 'Offline demo ready — scripted text and local synthetic voices, not live AI.'}
    (folder / 'demo.json').write_text(json.dumps(project, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Offline demo created: {len(segments)} sentences, {cursor:.1f} seconds.')


if __name__ == '__main__':
    try:
        create()
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        raise SystemExit(f'Demo generation failed: {exc}') from exc
