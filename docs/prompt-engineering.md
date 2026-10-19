# Prompt engineering and evaluation

## Real-world problem

Conversational translation must preserve intent and fluency while retaining an exact mapping to timed sentences. Omissions or reordered output break synchronized playback even when a translation sounds natural.

## Persona pattern

Both templates assign a professional multilingual translator specializing in spoken media. Version 2 also specifies language-learning use, tone, stable terminology, and names. Spoken transcript instructions are treated as untrusted dialogue to translate, never as commands to execute.

## Few-shot pattern

Version 2 includes English–Spanish, Japanese–English, English–French, and Arabic–English examples. “Break a leg!” demonstrates idiomatic meaning rather than literal injury; the Japanese workplace greeting demonstrates contextual politeness. A two-sentence software example preserves the technical sense of “branch” and each sentence ID. Arabic exercises non-Latin input.

## Iterative refinement

`backend/app/prompts/translation-v1.txt` is the baseline persona and natural-translation request. Active `translation-v2.txt` adds exact codes, no-omission rules, ordering, immutable-source ownership, four examples, adjacent context, and a private final verification instruction. This is a documented design iteration, not a claim that v2 won a live benchmark.

Requests contain up to 40 sentences and the preceding two sentences as context. The model does not return source text or timing; the server joins translations to immutable source records by ID.

## Structured JSON

The SDK uses `responses.parse(text_format=TranslationResult)`. Pydantic rejects extra fields; additional validation checks exact language codes, ordered ID equality, count, and nonempty text. Invalid mappings get one application retry; transient provider failures have bounded SDK retries. Refusals and persistent malformed output become visible job errors.

Illustrative input:

```json
{"source_language":"en","target_language":"es","context":[],"segments":[{"id":1,"text":"Break a leg!"}]}
```

Illustrative expected output, not a recorded live result:

```json
{"source_language":"en","target_language":"es","segments":[{"id":1,"translated_text":"¡Mucha suerte!"}]}
```

## Evaluation methodology

Automated tests never spend API credits. Multiple language pairs, Unicode, malformed mappings, immutable source text, exports, and mocked provider integration are tested. The manual review set is in `docs/prompt-evaluations.json`.

For future live comparison, run both templates on the same inputs and record model/version/date/cost. Blind-review meaning, naturalness, terminology, and omissions on 1–5 scales; require 100% ID coverage before scoring quality. No quantitative live quality score is fabricated.

## Limitations

Translation is probabilistic and may misresolve ambiguous dialogue. Syntax validation does not establish linguistic quality. Batch context is limited; Whisper timing is approximate; ten-minute boundaries may split an utterance. No speaker diarization or cloned voices are used. Corrections require speech regeneration. Supported speech quality varies by language.

## Official documentation

Implementation contracts were checked against [timestamped transcription](https://developers.openai.com/api/docs/guides/speech-to-text), [structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs), and [text-to-speech](https://developers.openai.com/api/docs/guides/text-to-speech) on October 18, 2026. Whisper-1 supplies supported timing; translation and speech model names remain configurable.
