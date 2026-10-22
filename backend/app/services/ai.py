# ai.py — Timestamp-aware transcription, validated translations, and cached speech.
import hashlib
import json
from pathlib import Path
import langcodes
from openai import OpenAI
from ..schemas import TranslationResult
from .media import chunks, segment_words


def validate_translation(result, source, target, segments):
    """Reject omissions, reordering, extra IDs, or language substitutions."""
    if result.source_language != source or result.target_language != target:
        raise ValueError('Translation returned incorrect language identifiers.')
    if [s.id for s in result.segments] != [s['id'] for s in segments]:
        raise ValueError('Translation did not preserve every sentence ID in order.')
    if any(not s.translated_text.strip() for s in result.segments):
        raise ValueError('Translation returned an empty sentence.')
    return {str(s.id): s.translated_text for s in result.segments}


class AI:
    """Wrap external services with bounded retries and explicit capability checks."""
    def __init__(self, config):
        self.config = config
        self.client = OpenAI(api_key=config['API_KEY'] or 'unconfigured', timeout=30 if config['PRODUCTION'] else 90, max_retries=0 if config['PRODUCTION'] else 2)

    def transcribe(self, path, folder, duration, source, checkpoint):
        """Preserve global offsets across timestamp-capable Whisper chunks."""
        if self.config['TRANSCRIPTION_MODEL'] != 'whisper-1':
            raise ValueError('Sentence timing currently requires OPENAI_TRANSCRIPTION_MODEL=whisper-1.')
        segments, detected = [], source
        for offset, audio in chunks(path, folder, duration, self.config):
            checkpoint(f'Transcribing audio at {offset // 60} minutes', 10 + int(30 * offset / duration))
            try:
                with audio.open('rb') as stream:
                    response = self.client.audio.transcriptions.create(
                        model=self.config['TRANSCRIPTION_MODEL'], file=stream, response_format='verbose_json',
                        timestamp_granularities=['word', 'segment'],
                        **({'language': source} if source != 'auto' else {})).model_dump()
                if source == 'auto' and detected == 'auto':
                    if not response.get('language'):
                        raise ValueError('Transcription did not identify a source language; select it manually.')
                    detected = langcodes.find(response['language']).language
                segments.extend(segment_words(response, offset))
            finally:
                audio.unlink(missing_ok=True)
        if not segments:
            raise ValueError('No timed speech was detected in this media.')
        for index, segment in enumerate(segments):
            segment['id'] = index + 1
            segment['end'] = min(segment['end'], duration)
            if segment['start'] >= segment['end'] or (index and segment['start'] < segments[index - 1]['end']):
                raise ValueError('Transcription timing exceeds the media bounds.')
        return detected, segments

    def translate(self, source, target, segments, checkpoint):
        """Translate bounded batches using persona, examples, and schema validation."""
        prompt = (Path(__file__).parents[1] / 'prompts/translation-v2.txt').read_text(encoding='utf-8')
        output = {}
        for offset in range(0, len(segments), 40):
            batch = segments[offset:offset + 40]
            checkpoint('Translating sentences', 45 + int(15 * offset / len(segments)))
            payload = {'source_language': source, 'target_language': target,
                       'context': [s['original_text'] for s in segments[max(0, offset - 2):offset]],
                       'segments': [{'id': s['id'], 'text': s['original_text']} for s in batch]}
            for attempt in range(2):
                try:
                    response = self.client.responses.parse(model=self.config['TRANSLATION_MODEL'],
                        input=[{'role': 'system', 'content': prompt}, {'role': 'user', 'content': json.dumps(payload, ensure_ascii=False)}],
                        text_format=TranslationResult)
                    if response.output_parsed is None:
                        raise ValueError('Translation was refused or did not return structured output.')
                    output.update(validate_translation(response.output_parsed, source, target, batch))
                    break
                except (ValueError, TypeError):
                    if attempt:
                        raise
        return output

    def speech(self, pid, target, voice, sid, text):
        """Cache by model, language, voice, segment, and exact corrected text."""
        digest = hashlib.sha256(f'{self.config["TTS_MODEL"]}|{text}'.encode()).hexdigest()[:24]
        relative = Path(pid) / target / voice / f'{sid}-{digest}.mp3'
        path = self.config['AUDIO'] / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            temporary = path.with_suffix('.tmp')
            try:
                with self.client.audio.speech.with_streaming_response.create(
                    model=self.config['TTS_MODEL'], voice=voice, input=text, response_format='mp3') as response:
                    response.stream_to_file(temporary)
                temporary.replace(path)
            finally:
                temporary.unlink(missing_ok=True)
        return relative.as_posix()
