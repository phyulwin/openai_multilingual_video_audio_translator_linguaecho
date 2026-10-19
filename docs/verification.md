# Verification record — October 18, 2026

## Verified locally

- Python 3.13 virtual environment; Node 20.19; FFmpeg/FFprobe 9.0.2; local Waitress server.
- Frontend TypeScript check and Vite production build passed.
- Backend Pytest: 31 tests passed, covering actual WAV upload/FFprobe/FFmpeg extraction, MP4 demo delivery, HTTP byte ranges, safe deletion, size/content validation, language validation, exports, corrections, cache invalidation, SDK response parsing, chunk offsets, mocked translation/TTS, background work, additional targets, cancellation, failure state, and quota messaging.
- Vitest suite: 20 tests passed, including React interactions and playback ordering, video pausing/resumption, both bilingual orders, translation/original-only, gaps, trailing audio, seek, skip, replay, pause/resume, stale promises/callbacks, mode switching, and autoplay failure.
- Playwright Chromium: both browser workflows passed. Real fixture media played original speech, paused video during translated audio, resumed video, switched modes, used audio-only display, replayed/bookmarked sentences, downloaded SRT, reopened the library, uploaded/previewed video, and persisted project metadata.
- Desktop 1440px and mobile 390px screenshots were generated and visually inspected; the mobile document had no horizontal overflow.
- Browser workflow recorded no uncaught JavaScript exceptions.
- GET / and GET /api/health returned HTTP 200; range requests and speech endpoints were exercised.
- npm dependency audit reported zero known vulnerabilities in the installed dependency tree.

## Live AI check and limits

A real eight-second Japanese fixture clip was uploaded as ordinary media and submitted to the configured OpenAI transcription API. The provider returned HTTP 429 with code `insufficient_quota`; the job correctly entered an error state without fabricated output. The temporary live-check project was removed afterward.

Consequently, successful live transcription, live translation, and live speech generation were **not** verified. The integration contracts and mocked end-to-end pipeline were verified. The UI now reports unavailable quota explicitly. No live linguistic quality scores or production-readiness claim are made.

The browser tests use local fixtures and never spend API credits. No exhaustive two-hour/200-MB load test, all-language quality evaluation, or cross-browser/Safari test has been performed. Background-tab timing remains an acknowledged browser limitation.

## Reproduce

### Follow-up configuration fix and successful live verification

The root `.env` now overrides inherited environment values; `.env.example` is never loaded. An inherited key differed from the user's configured key, and older Windows server instances were sharing the same port. Startup now reserves the port exclusively before constructing workers, preventing duplicate servers from accepting requests with stale configuration.

After stopping the stale instances and restarting with the user's `.env` key, a real eight-second Japanese fixture completed the live transcription → English translation → speech pipeline: three timed sentences, three translations, and three generated speech files, with HTTP 200 for a generated audio download. This supersedes the earlier quota-blocked live result above; it is a small integration check, not an all-language quality or load test. The temporary check project was deleted after verification.

Use the commands in README. Keep the local backend running for Playwright; backend unit tests create isolated temporary storage. The labeled demo remains fully usable without API quota.
