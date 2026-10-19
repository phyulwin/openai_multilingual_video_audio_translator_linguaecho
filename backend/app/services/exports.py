# exports.py — Unicode exports always use original-media timestamps.
import json


def timestamp(seconds):
    """Round to SRT milliseconds with correct carry into minutes and hours."""
    milliseconds = round(seconds * 1000)
    hours, milliseconds = divmod(milliseconds, 3600000)
    minutes, milliseconds = divmod(milliseconds, 60000)
    seconds, milliseconds = divmod(milliseconds, 1000)
    return f'{hours:02}:{minutes:02}:{seconds:02},{milliseconds:03}'


def export(project, target, kind, language):
    """Build plain text, original-timeline subtitles, or bilingual JSON."""
    if kind not in ('txt', 'srt', 'json') or language not in ('original', 'translated', 'bilingual'):
        raise ValueError('Choose txt, srt, or json and original, translated, or bilingual.')
    translation = project['translations'].get(target, {}).get('texts', {})
    if language != 'original' and not translation:
        raise ValueError('Generate a translation for this language first.')
    rows = [{**s, 'translated_text': translation.get(str(s['id']), '')} for s in project['segments']]
    if kind == 'json':
        return json.dumps({'source_language': project['source_language'], 'target_language': target, 'segments': rows}, ensure_ascii=False, indent=2)
    blocks = []
    for i, row in enumerate(rows):
        text = row['original_text'] if language == 'original' else row['translated_text']
        if language == 'bilingual':
            text = row['original_text'] + '\n' + row['translated_text']
        if kind == 'srt':
            # Prevent edited text from injecting additional subtitle cues.
            text = '\n'.join(line for line in text.splitlines() if line.strip()).replace('-->', '→')
            text = f'{i + 1}\n{timestamp(row["start"])} --> {timestamp(row["end"])}\n{text}\n'
        blocks.append(text)
    return '\n'.join(blocks)
