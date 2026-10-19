# LinguaEcho

**Multilingual Video & Audio Player — More Voices, A Wider World.**

A complete local application for learning from uploaded video and audio: timed transcription, sentence translation, generated speech, and an interactive bilingual player that pauses the video while the translated voice speaks.

![Hero](frontend\public\hero_live_web.png)

## Features and problem statement

A student watching a Korean interview can upload the video, translate the speech into Spanish or English, and listen to each original Korean sentence followed by its AI-generated translation. This helps users understand foreign-language content while preserving the original speaker's voice and context.

Understanding foreign-language media should not require losing the original speaker or constantly rewinding. LinguaEcho connects each original sentence to its translation and lets the listener control their order.

- Real drag/drop uploads, progress, cancellation, FFprobe validation, preview, and a configurable 200 MB limit.
- Searchable source/target selection across 57 speech-supported languages; automatic detection and additional saved targets.
- Original→Translation, Translation→Original, Translation Only, and Original Only; optional audio-only display.
- Play/pause/resume, seek, skip, replay, speed, volume, mute, fullscreen, keyboard controls, synchronized transcript highlighting.
- Transcript search, original/translated/both clipboard actions, bookmarks, translation corrections, and speech regeneration.
- Original/translated/bilingual TXT, original/translated SRT, and bilingual JSON downloads.
- Persistent project library with search, rename, favorites, reopen, and safe deletion.
- Background processing, status, cooperative cancellation, resumable stages, bounded retries, and cached speech.
- Clearly labeled offline demo with real local fixture media; no paid AI calls.

## Stack and architecture

React 19, TypeScript, Vite, Tailwind CSS 4, custom CSS, Lucide, and HTML5 media; Python 3.11+, Flask, Pydantic, SQLite, FFmpeg/FFprobe, OpenAI Python SDK, and Waitress. Tests use Pytest, Vitest, React Testing Library, and Playwright.

The browser owns two mutually exclusive audio channels; the server extracts audio and runs transcription → structured translation → speech in one bounded background worker. Credentials remain server-side. See [architecture and API](docs/architecture.md).

## Run this prepared Windows workspace

Dependencies, FFmpeg, demo assets, and a production frontend build have been prepared. From the repository root:

```powershell
# Start the local API and compiled frontend.
.venv\Scripts\python backend/run.py
```

Open **http://127.0.0.1:5000** and choose **Explore the demo**. If LinguaEcho already occupies port 5000, use the existing instance.

## Fresh installation

Install Python 3.11+, Node 20.19+ or Node 22.12+, and FFmpeg with FFprobe. From the repository root:

```powershell
# Install isolated backend dependencies.
python -m venv .venv
.venv\Scripts\python -m pip install -r backend/requirements-lock.txt

# Install locked frontend dependencies and create a production build.
npm --prefix frontend ci --legacy-peer-deps
npm --prefix frontend run build

# Create configuration without overwriting an existing .env.
if (!(Test-Path .env)) { Copy-Item .env.example .env }
```

Linux/macOS use `python3` and `.venv/bin/python`; frontend commands are the same. The committed demo media works on all platforms. Its regeneration script uses Windows System.Speech voices.

### FFmpeg

Install both `ffmpeg` and `ffprobe`: Windows can use `winget install --id Gyan.FFmpeg --exact --source winget`, macOS `brew install ffmpeg`, and Debian/Ubuntu `sudo apt install ffmpeg`. Confirm both executables with `-version` in a new terminal.

Alternatively, set their absolute executable paths in `.env`. This prepared workspace has an ignored local `.tools/` installation and corresponding paths in its local `.env`; those machine-specific paths are not committed.

### OpenAI and environment

Set `OPENAI_API_KEY` in the server `.env` or environment, with API billing/quota and model access enabled. Values explicitly present in the root `.env` override inherited environment variables; `.env.example` is only a template and is never loaded. Restart the backend after changes. Never put secrets in frontend code. A configured key does not establish available quota.

| Variable | Default / purpose |
|---|---|
| OPENAI_API_KEY | Required only for live processing |
| OPENAI_TRANSCRIPTION_MODEL | whisper-1, required for supported timestamp output |
| OPENAI_TRANSLATION_MODEL | gpt-4.1-mini, structured translation |
| OPENAI_TTS_MODEL | gpt-4o-mini-tts |
| OPENAI_TTS_VOICE | coral |
| MAX_UPLOAD_MB | 200, includes multipart request overhead |
| MAX_DURATION_SECONDS | 7200 |
| DATABASE_URL | sqlite:///data/linguaecho.sqlite3 |
| UPLOAD_DIRECTORY | data/uploads |
| GENERATED_AUDIO_DIRECTORY | data/audio |
| FFMPEG_BINARY / FFPROBE_BINARY | Executable names or absolute paths |
| PORT | 5000 |

The implementation follows [OpenAI timestamped transcription](https://developers.openai.com/api/docs/guides/speech-to-text), [structured output](https://developers.openai.com/api/docs/guides/structured-outputs), and [speech generation](https://developers.openai.com/api/docs/guides/text-to-speech). These are explicit compatible model defaults, not a claim they are the newest models. Changing to a transcription model without supported timestamps is rejected instead of inventing alignment.

## Development startup

```powershell
# Terminal 1: local Waitress backend and production frontend.
.venv\Scripts\python backend/run.py

# Terminal 2, optional: Vite with hot reload and a same-origin API proxy.
npm --prefix frontend run dev
```

Development URL: **http://127.0.0.1:5173**. Vite proxies `/api` to port 5000. Production assets are served by Waitress, not Flask's development server. Changing the backend port requires updating the development proxy/origin allowlist if used.

## Usage

1. Upload MP4, MOV, WEBM, MKV, MP3, WAV, or M4A containing an audio stream.
2. Choose Auto Detect or a source language, choose a target, and click **Translate my media**.
3. Select **Original → Translation** and play: video pauses during AI speech and resumes afterward.
4. Try Translation Only, Original Only, or Audio only; Space toggles playback and arrow keys skip sentences outside form fields.
5. Search, replay, copy, or bookmark transcript rows. Save a correction, then click **Generate translation & voice** to refresh invalidated speech.
6. Select another target for an additional saved translation; change voice in Settings and generate its speech.
7. Download TXT, SRT, or JSON and reopen projects from My Library.

Original transcriptions are immutable once generated; upload a fresh project to retranscribe with a different source choice. The offline demo has fixed Japanese/English text and locally synthesized fixture voices; its text cannot be edited or sent through live processing.

## Tests

```powershell
# Real local media and mocked OpenAI integrations.
.venv\Scripts\python -m pytest backend/tests -q

# Type checking, production build, UI and playback checks.
npm --prefix frontend run typecheck
npm --prefix frontend run build
npm --prefix frontend test

# Browser tests require the backend running at port 5000.
Push-Location frontend
npx playwright install chromium
npm run test:e2e
Pop-Location
```

Automated tests never spend API credits. Browser tests create and delete their own fixture projects; a failed test may leave its project for inspection. See [verification results](docs/verification.md).

## Prompt engineering

Professional translator persona, multilingual few-shot examples, exact structured JSON validation, and two documented prompt versions. See [prompt engineering](docs/prompt-engineering.md) and [evaluation cases](docs/prompt-evaluations.json).

## Troubleshooting

- **Quota/rate limit:** check API billing and project limits; retry after fixing access. Completed stages remain saved.
- **Missing FFmpeg:** configure both binaries and restart; Settings shows tool availability.
- **Upload rejected:** check real content, an audio track, allowed extension, size, and duration.
- **Unplayable browser codec:** FFmpeg support does not guarantee HTML5 playback; convert to MP4/H.264/AAC, WebM, or a common audio format.
- **Missing translated speech:** generate the current language and voice; saved corrections invalidate old speech. Original Only remains available.
- **Autoplay denied:** click Play to establish a browser gesture.
- **Cancellation takes time:** the current provider call or extraction must finish or time out.
- **Missing demo:** restore `fixtures/` or run `.venv\Scripts\python scripts/create_demo.py` on Windows with Haruka and Zira voices.
- **Port occupied:** reuse or stop only the existing LinguaEcho instance.

## Limitations and future improvements

Local single-user MVP, not a production-readiness certification. No authentication, YouTube import, public hosting, voice cloning, speaker diarization, or distributed queue. The service binds to loopback and rejects foreign origins. One server process is required because the worker registry is in memory.

Browser timing is approximate and background tabs can throttle scheduling. Sentence splitting uses punctuation, pauses, and duration limits; chunk boundaries and mixed-language recordings may need review. No live linguistic quality score is claimed. Storage grows until projects are deleted; no storage quota is enforced.

Next steps: stronger alignment, waveform editing, browser codec transcoding, background-safe audio scheduling, durable jobs, storage quotas, authenticated deployment, and multilingual human evaluation.

Runtime data, credentials, databases, dependencies, and user speech are ignored by Git. Intentional offline fixtures are included. [Artwork provenance](docs/artwork.md) documents the original banner in `frontend/public/hero.png`. No publication, deployment, or GitHub push was performed.


## Credits - Sample Videos

[IMPORTANT❗Download sample videos here to test LinguaEcho today.](https://livecsupomona-my.sharepoint.com/:f:/g/personal/klwin_cpp_edu/IgC-3ijNO-gQSqtt-b_8CIsoAaBlDyofRAcKC0RqZ2xfPkI?e=tuUlr4)

File: 박진섭 감독 첫 인터뷰.webm [Korean Spoken Language]

[Page URL](https://commons.wikimedia.org/wiki/File:%EB%B0%95%EC%A7%84%EC%84%AD_%EA%B0%90%EB%8F%85_%EC%B2%AB_%EC%9D%B8%ED%84%B0%EB%B7%B0.webm) | [File URL](https://upload.wikimedia.org/wikipedia/commons/3/3e/%EB%B0%95%EC%A7%84%EC%84%AD_%EA%B0%90%EB%8F%85_%EC%B2%AB_%EC%9D%B8%ED%84%B0%EB%B7%B0.webm?utm_source=commons.wikimedia.org&utm_campaign=index&utm_content=original
)

Attribution: FC SEOUL, CC BY 3.0 <https://creativecommons.org/licenses/by/3.0>, via Wikimedia Commons

File:【募集・採用】一般大から入隊した海上自衛隊幹部候補生に聞いてみた.webm [Japanese Spoken Language]

[Page URL](https://commons.wikimedia.org/wiki/File:%E3%80%90%E5%8B%9F%E9%9B%86%E3%83%BB%E6%8E%A1%E7%94%A8%E3%80%91%E4%B8%80%E8%88%AC%E5%A4%A7%E3%81%8B%E3%82%89%E5%85%A5%E9%9A%8A%E3%81%97%E3%81%9F%E6%B5%B7%E4%B8%8A%E8%87%AA%E8%A1%9B%E9%9A%8A%E5%B9%B9%E9%83%A8%E5%80%99%E8%A3%9C%E7%94%9F%E3%81%AB%E8%81%9E%E3%81%84%E3%81%A6%E3%81%BF%E3%81%9F%E2%91%A0.webm) | [File URL](https://upload.wikimedia.org/wikipedia/commons/7/7e/%E3%80%90%E5%8B%9F%E9%9B%86%E3%83%BB%E6%8E%A1%E7%94%A8%E3%80%91%E4%B8%80%E8%88%AC%E5%A4%A7%E3%81%8B%E3%82%89%E5%85%A5%E9%9A%8A%E3%81%97%E3%81%9F%E6%B5%B7%E4%B8%8A%E8%87%AA%E8%A1%9B%E9%9A%8A%E5%B9%B9%E9%83%A8%E5%80%99%E8%A3%9C%E7%94%9F%E3%81%AB%E8%81%9E%E3%81%84%E3%81%A6%E3%81%BF%E3%81%9F%E2%91%A0.webm?utm_source=commons.wikimedia.org&utm_campaign=index&utm_content=original)

Attribution: 防衛省 海上自衛隊 公式チャンネル, CC BY 3.0 <https://creativecommons.org/licenses/by/3.0>, via Wikimedia Commons

File:【巴黎奥运会】徐卓一：会尽最大的努力向刘翔靠近.webm [Chinese - Mandarin Spoken Language]

[Page URL](https://commons.wikimedia.org/wiki/File:%E3%80%90%E5%B7%B4%E9%BB%8E%E5%A5%A5%E8%BF%90%E4%BC%9A%E3%80%91%E5%BE%90%E5%8D%93%E4%B8%80%EF%BC%9A%E4%BC%9A%E5%B0%BD%E6%9C%80%E5%A4%A7%E7%9A%84%E5%8A%AA%E5%8A%9B%E5%90%91%E5%88%98%E7%BF%94%E9%9D%A0%E8%BF%91.webm) | [File URL](https://upload.wikimedia.org/wikipedia/commons/7/7c/%E3%80%90%E5%B7%B4%E9%BB%8E%E5%A5%A5%E8%BF%90%E4%BC%9A%E3%80%91%E5%BE%90%E5%8D%93%E4%B8%80%EF%BC%9A%E4%BC%9A%E5%B0%BD%E6%9C%80%E5%A4%A7%E7%9A%84%E5%8A%AA%E5%8A%9B%E5%90%91%E5%88%98%E7%BF%94%E9%9D%A0%E8%BF%91.webm?utm_source=commons.wikimedia.org&utm_campaign=index&utm_content=original)

Attribution: 中国新闻社, CC BY 3.0 <https://creativecommons.org/licenses/by/3.0>, via Wikimedia Commons

---
