# test_ai.py — Mocked provider integrations, mapping checks, segmentation, and audio cache.
from types import SimpleNamespace
from unittest.mock import MagicMock
import pytest
from app.schemas import TranslationResult
from app.services.ai import AI, validate_translation
from app.services.media import segment_words
from app.services.exports import timestamp


def test_transcription_provider_parsing_and_chunk_offsets(app, tmp_path, monkeypatch):
    """Parse timed SDK responses, preserve global offsets, and remove temporary chunks."""
    paths = [tmp_path / 'chunk-0.mp3', tmp_path / 'chunk-600.mp3']
    for path in paths:
        path.write_bytes(b'fixture')
    monkeypatch.setattr('app.services.ai.chunks', lambda *_: iter([(0, paths[0]), (600, paths[1])]))
    ai = AI(app.config)
    ai.client = MagicMock()
    ai.client.audio.transcriptions.create.return_value.model_dump.return_value = {
        'language': 'japanese', 'words': [{'word': 'こんにちは。', 'start': .1, 'end': 1.5}]}
    language, rows = ai.transcribe(tmp_path / 'source.mp4', tmp_path, 1200, 'auto', lambda *_: None)
    assert language == 'ja'
    assert [row['id'] for row in rows] == [1, 2]
    assert rows[1]['start'] == 600.1
    assert rows[1]['end'] == 601.5
    assert not any(path.exists() for path in paths)
    assert ai.client.audio.transcriptions.create.call_args.kwargs['timestamp_granularities'] == ['word', 'segment']


def test_word_segmentation_and_global_offsets():
    """Punctuation, pauses, and chunk offsets preserve sentence chronology."""
    rows = segment_words({'words': [{'word': 'Hello.', 'start': 0, 'end': .5}, {'word': '世界。', 'start': 2, 'end': 3}]}, 600)
    assert len(rows) == 2
    assert rows[1]['start'] == 602
    assert rows[1]['original_text'] == '世界。'


def test_segment_fallback_and_invalid_timing():
    """A provider's timed-segment fallback is accepted, invented timing is not."""
    assert segment_words({'segments': [{'text': 'أهلاً', 'start': 1, 'end': 2}]})[0]['original_text'] == 'أهلاً'
    with pytest.raises(ValueError):
        segment_words({'words': [{'word': 'Oops.', 'start': 2, 'end': 1}]})
    assert segment_words({'text': 'Untimed response'}) == []


@pytest.mark.parametrize('source,target,text', [('ja','en','Hello.'),('en','es','¡Mucha suerte!'),('ar','fr','Bienvenue.')])
def test_translation_mapping(source, target, text):
    """Validate multiple Unicode language pairs without spending credits."""
    result = TranslationResult(source_language=source, target_language=target, segments=[{'id': 1, 'translated_text': text}])
    assert validate_translation(result, source, target, [{'id': 1}]) == {'1': text}
    with pytest.raises(ValueError):
        validate_translation(result, source, target, [{'id': 1}, {'id': 2}])
    with pytest.raises(ValueError):
        validate_translation(result, source, 'uk', [{'id': 1}])


def test_structured_translation_uses_provider_response(app):
    """Normal integration consumes the parsed response instead of fixtures."""
    ai = AI(app.config)
    ai.client = MagicMock()
    ai.client.responses.parse.return_value = SimpleNamespace(output_parsed=TranslationResult(source_language='en', target_language='es', segments=[{'id': 1, 'translated_text': 'Hola.'}]))
    assert ai.translate('en', 'es', [{'id': 1, 'original_text': 'Hello.'}], lambda *_: None) == {'1': 'Hola.'}
    assert ai.client.responses.parse.call_args.kwargs['text_format'] is TranslationResult


def test_speech_cache_and_text_changes(app):
    """Identical speech is reused; changed text and voice generate new files."""
    ai = AI(app.config)
    ai.client = MagicMock()
    stream = ai.client.audio.speech.with_streaming_response.create.return_value.__enter__.return_value
    stream.stream_to_file.side_effect = lambda path: path.write_bytes(b'mocked audio')
    first = ai.speech('a' * 32, 'en', 'coral', '1', 'Hello.')
    assert ai.speech('a' * 32, 'en', 'coral', '1', 'Hello.') == first
    assert ai.client.audio.speech.with_streaming_response.create.call_count == 1
    assert ai.speech('a' * 32, 'en', 'coral', '1', 'Goodbye.') != first
    assert ai.speech('a' * 32, 'en', 'alloy', '1', 'Hello.') != first


def test_srt_rounding():
    """Millisecond rounding must carry into the next minute."""
    assert timestamp(59.9999) == '00:01:00,000'
