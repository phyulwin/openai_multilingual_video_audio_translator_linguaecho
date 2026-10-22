# LinguaEcho deployment runbook

## Release decision

This configuration supports a small, invited-user, temporary processing service. It does **not** provide a durable cloud library, guaranteed background completion, or automatic recovery after an instance disappears. Approve these limitations and potential charges before running the cloud commands below. The Pages workflow is **manual only**, so committing or pushing does not publish the website.

The UI and bilingual playback engine remain in place: original/translation order, reverse order, translation-only, original-only, sentence replay, speed, bookmarks, favorites, language/voice selection, edits, exports, and fixture demo. Their server-held state exists only for the temporary workspace lifetime in production. Local development retains its existing disk-backed SQLite and threaded processing behavior.

## Architecture and operating limits

| Component | Production behavior |
| --- | --- |
| React/Vite | GitHub Pages under `/openai_multilingual_video_audio_translator_linguaecho/` |
| API | Flask + Waitress, one process, eight HTTP threads, port supplied by Cloud Run |
| Access | Individually provisioned 256-bit access tokens, SHA-256 hash allowlist on backend |
| OpenAI | Backend-only environment secret; existing transcription, translation, and TTS models |
| Media and SQLite | `/tmp/linguaecho` in a bounded 512 MiB in-memory volume |
| Upload | 25 MiB **whole multipart request** limit; choose files slightly below 25 MiB |
| Duration | Five minutes; original local two-hour limit remains local only |
| Work | One active AI attempt; competing requests receive a retryable error, no production queue |
| Attempt | Cooperative 240-second deadline checked between stages; completed stages retained temporarily |
| Provider | 30-second SDK timeout, no automatic SDK retries in production |
| FFmpeg | One encoding thread; subprocess timeout up to 180 seconds |
| HTTP | 600-second Cloud Run timeout; concurrency 8, one vCPU, 2 GiB RAM |
| Scale | Service and revision maximum 1, minimum 0, request-based billing |
| Admission | One upload at a time; ten total projects; 384 MiB soft media capacity check |
| Abuse controls | Per user: 600 requests/minute, 120 writes/hour, eight processing starts/hour; per instance: 100 processing starts/day |
| Expiry | One hour from creation, cleaned on subsequent authenticated requests; active jobs excluded |

The 25 MiB upload limit leaves space below Cloud Run's 32 MiB HTTP/1 request ceiling; large existing media must be shortened or compressed before cloud upload. [Cloud Run quotas](https://docs.cloud.google.com/run/quotas).

Storage counts against RAM; the volume cap prevents unlimited media growth, but FFmpeg, request buffers, SQLite, and Python also need memory. The soft check is not a byte reservation: an in-flight write can cross it, and the hard volume limit can reject a write. [In-memory volume configuration](https://docs.cloud.google.com/run/docs/configuring/instances/in-memory-volume-mounts).

### Reliability and SQLite

Production processing runs **inside the process HTTP request** instead of submitting to the local thread pool and returning immediately. Other HTTP threads handle progress, cancellation, and playback. CPU therefore remains allocated while that request is active, without purchasing always-on background execution. Provider/FFmpeg failures are reported; completed transcription, translation, and speech remain reusable on the same instance. Retries are explicit to avoid silently repeating billable work. [Billing behavior](https://docs.cloud.google.com/run/docs/configuring/billing-settings).

The deadline is cooperative, not an exact wall-clock kill: an already-running subprocess or provider request must return first. A browser disconnect or Cloud Run timeout does not reliably stop Python work; cancellation is checked between stages. Keep the processing tab open and use Cancel, then wait for the current operation to finish. Large/many-sentence clips can require several attempts even within five minutes. [Request timeout behavior](https://docs.cloud.google.com/run/docs/configuring/request-timeout).

An instance may terminate, restart, or be replaced even with minimum instances enabled. Shutdown grace is short; this implementation cannot promise to finish OpenAI work during shutdown. SQLite, original uploads, and generated audio then disappear together. An in-flight provider call may still be billed even if its result is lost. [Container lifecycle contract](https://docs.cloud.google.com/run/docs/container-contract).

SQLite is server-local, uses serialized in-process mutations, and is not shared across instances. A one-instance limit reduces routing problems but is **not a persistence or single-instance guarantee during replacements/deployments**; do not split traffic or scale this design horizontally. Session affinity is best effort and cannot solve this; the frontend does not depend on third-party cookies. During replacement, a request may see an empty library or 404 and require re-upload. [Session affinity limitations](https://docs.cloud.google.com/run/docs/configuring/session-affinity).

Expiry cleanup is deliberately request-driven because idle CPU is not guaranteed: an idle instance can retain expired files until the next authenticated request or instance destruction. Expired inactive projects are removed from both directories and SQLite; explicit deletion removes them immediately. Failed uploads, failed demo copies, transcription chunks, and temporary speech downloads are cleaned on handled failures. Process death can leave files until the instance disappears or project expiry runs. This is not a guaranteed minute-exact erasure service.

Cloud Tasks or a separate Cloud Run Job would not fix this without a shared input/result store: another instance cannot read this instance's temporary upload. Guaranteed completion and restart recovery require relaxing the no-persistent-storage constraint or implementing a browser-owned resumable protocol; neither is silently substituted here.

### Browser-local persistence evaluation

Current `localStorage` saves only the last-opened **project ID**. It does not contain the SQLite database, transcript, original upload, generated audio, bookmarks, or translations. Reload restoration works only while the backend still has that project.

IndexedDB is the appropriate candidate for saving project JSON plus original and generated media as Blobs on each device. It would need versioned schemas, user-namespaced keys, transactional snapshots, quota/error handling, blob URL playback, explicit deletion and backup/import, and restoration to a fresh backend before additional AI edits. Saving just API URLs cannot preserve media after Cloud Run removes it. This change evaluates that design but does **not** claim to implement an offline library or an import feature. Existing TXT/SRT/JSON exports preserve text; JSON exports are not a full media backup. [IndexedDB concepts](https://developer.mozilla.org/en-US/docs/Web/API/IndexedDB_API).

Browser storage can be evicted or cleared, is device/profile/origin-specific, and private browsing is temporary. `navigator.storage.persist()` can request improved retention but cannot guarantee backup. Two people sharing a browser profile do not automatically get private local databases. GitHub project sites under `phyulwin.github.io` also share an origin; only host trusted code on that origin, and use separate browser profiles for separate users. [Storage persistence](https://developer.mozilla.org/en-US/docs/Web/API/StorageManager/persist), [Web Storage](https://developer.mozilla.org/en-US/docs/Web/API/Web_Storage_API).

## 1. Local verification before approval

Run these from the repository root in PowerShell; Docker Desktop must be running in Linux-container mode for the image check.

```powershell
# Verify backend behavior without making live OpenAI calls.
.venv/Scripts/python.exe -m pytest backend/tests -q

# Install the locked frontend dependencies and verify playback and compilation.
Push-Location frontend
npm ci
npm test
npm run build
Pop-Location

# Build the deployment image locally; this does not publish or deploy it.
docker build --platform linux/amd64 -t linguaecho-api:review .
```

For an offline container smoke test, use a dummy OpenAI key and a test-only SHA-256 allowlist, bind only to loopback, and mount a temporary volume:

```powershell
# Use dummy credentials only for this local startup/FFmpeg check.
$testUsers = '{"' + ('a' * 64) + '":"smoke-test"}'
docker run --rm --name linguaecho-review -p 127.0.0.1:8080:8080 `
  --memory=2g --cpus=1 --tmpfs /tmp/linguaecho:rw,size=536870912,mode=1777 `
  -e ALLOWED_ORIGINS=https://phyulwin.github.io -e "ACCESS_USERS=$testUsers" `
  -e OPENAI_API_KEY=not-a-real-key linguaecho-api:review

# In a second terminal, check HTTPS ingress handling and installed decoder tools.
Invoke-RestMethod http://127.0.0.1:8080/api/health -Headers @{'X-Forwarded-Proto'='https'}
docker stop linguaecho-review
```

Do not treat `ai_configured: true` as provider authentication: it only means a nonempty key is configured. Cloud Run terminates real HTTPS; the public application must never be exposed directly with its trusted proxy header configuration outside that environment.

## 2. Configure an existing GCP project after approval

Use an existing billing-enabled GCP project you control; replace `YOUR_EXISTING_PROJECT_ID` below. Installing tools and enabling billing are operator decisions; nothing here creates a GitHub repository. Required operator permissions include Cloud Run Admin, Artifact Registry administration/write, Service Account administration/user, Service Usage Admin, and Secret Manager administration. Organization policies may prohibit public Cloud Run ingress; resolve that with your administrator rather than removing application authentication.

```powershell
# Authenticate and select your approved existing GCP project.
$gcpProject = 'YOUR_EXISTING_PROJECT_ID'
$region = 'us-central1'
gcloud auth login
gcloud config set project $gcpProject
gcloud services enable run.googleapis.com artifactregistry.googleapis.com secretmanager.googleapis.com iam.googleapis.com

# Create only application infrastructure, not a user-media storage service.
gcloud artifacts repositories create linguaecho-images --repository-format=docker --location=$region
gcloud iam service-accounts create linguaecho-runtime --display-name='LinguaEcho runtime'
$runtimeAccount = "linguaecho-runtime@$gcpProject.iam.gserviceaccount.com"
```

If these named resources already exist, reuse them and skip their create commands. Stop on any failed command and resolve the failure before continuing. Artifact Registry retains the application image; Secret Manager retains credentials. Neither stores users' uploads/transcripts/audio. This runbook builds locally to avoid Cloud Build source-staging buckets; no Cloud Storage, Cloud SQL, Firestore, or Firebase service is configured.

## 3. Provision secrets and individual access

Generate tokens for actual invited users; replace the sample identifiers and distribute each printed token privately to its assigned user. Do not give everyone the same token. The helper writes hashes only and refuses to overwrite an existing manifest. Store the displayed tokens in your password manager, not in GitHub, screenshots, logs, or frontend variables.

```powershell
# Create an access manifest outside the repository and upload only its hashes.
$accessManifest = Join-Path $env:TEMP 'linguaecho-access-users.json'
.venv/Scripts/python.exe scripts/create_access_users.py --output $accessManifest alice bob
gcloud secrets create linguaecho-access-users --replication-policy=automatic --data-file=$accessManifest

# Prompt without putting the OpenAI key in shell history or a repository file.
$keyFile = Join-Path $env:TEMP 'linguaecho-openai-key.txt'
$secureKey = Read-Host 'OpenAI project API key' -AsSecureString
try {
  $credential = [System.Net.NetworkCredential]::new('', $secureKey)
  [System.IO.File]::WriteAllText($keyFile, $credential.Password, [System.Text.UTF8Encoding]::new($false))
  gcloud secrets create linguaecho-openai-key --replication-policy=automatic --data-file=$keyFile
} finally {
  Remove-Item -LiteralPath $keyFile -ErrorAction SilentlyContinue
  Remove-Variable credential,secureKey -ErrorAction SilentlyContinue
}

# Grant only these two secret reads to the runtime identity.
gcloud secrets add-iam-policy-binding linguaecho-openai-key --member="serviceAccount:$runtimeAccount" --role=roles/secretmanager.secretAccessor
gcloud secrets add-iam-policy-binding linguaecho-access-users --member="serviceAccount:$runtimeAccount" --role=roles/secretmanager.secretAccessor
```

The production factory ignores local `.env`, forces temporary paths and upload limits, and rejects missing/invalid access configuration or non-HTTPS CORS origins. `ACCESS_USERS` maps a 64-character SHA-256 token hash to a unique user ID. The frontend asks for the user's token and stores it in that tab's `sessionStorage`; closing the tab removes it. Invalid credentials are cleared after a failed API request; reload to enter a replacement. No public signup or password/account recovery is provided.

## 4. Protect logs and review configuration

`deploy/cloud-run.env.yaml` already allows `https://phyulwin.github.io`; CORS uses the **origin only**, not the repository URL path. If your Pages domain changes, edit this value before deployment. Multiple exact HTTPS origins may be comma-separated; never use `*`. Enforce HTTPS in GitHub Pages settings.

Project media/export links carry a signed, read-only capability valid for at most one hour and scoped to that project; they cannot edit a project or read transcript APIs. They are bearer secrets: do not share links. Account tokens are sent only in the Authorization header. Server-side ownership checks cover list, media ranges, audio, transcript, status, export, processing, cancellation, edits, and deletion; a different user receives 404 for another user's project ID. Responses are private/no-store, and referrers are suppressed.

Before opening access, go to **Google Cloud Console → Logging → Log Router → `_Default` → Edit sink → Add exclusion**, name it `linguaecho-request-urls`, and use this filter with a 100% exclusion:

```text
resource.type="cloud_run_revision"
resource.labels.service_name="linguaecho-api"
log_id("run.googleapis.com/requests")
```

This prevents the default log bucket from retaining signed URL query strings, at the cost of losing these request logs. Check any organization-level or additional sinks for the same issue; exclusions do not retroactively remove logs. Application logs do not intentionally include credentials or transcripts. Restrict access to all operational logs and secrets. Existing owner-only access remains safe without CORS: CORS is a browser policy, not authentication.

## 5. Build, publish the container, and deploy after approval

```powershell
# Publish the reviewed local image to the application's image registry.
gcloud auth configure-docker "$region-docker.pkg.dev"
$image = "$region-docker.pkg.dev/$gcpProject/linguaecho-images/api:v1"
docker build --platform linux/amd64 -t $image .
docker push $image

# Deploy a bounded, request-billed service with temporary media and metadata.
gcloud run deploy linguaecho-api --image=$image --region=$region `
  --service-account=$runtimeAccount --allow-unauthenticated --ingress=all `
  --execution-environment=gen2 --port=8080 --no-use-http2 `
  --cpu=1 --memory=2Gi --concurrency=8 --timeout=600 `
  --min=0 --max=1 --min-instances=0 --max-instances=1 --cpu-throttling `
  --env-vars-file=deploy/cloud-run.env.yaml `
  --set-secrets="OPENAI_API_KEY=linguaecho-openai-key:1,ACCESS_USERS=linguaecho-access-users:1" `
  --add-volume="name=workspace,type=in-memory,size-limit=512Mi" `
  --add-volume-mount="volume=workspace,mount-path=/tmp/linguaecho"

# Obtain the actual HTTPS endpoint; do not guess its generated hostname.
$backendUrl = gcloud run services describe linguaecho-api --region=$region --format='value(status.url)'
Invoke-RestMethod "$backendUrl/api/health"
```

`--allow-unauthenticated` enables browser reachability at Google IAM; it does **not** bypass the application's bearer-token gate. No credential may be embedded in `VITE_API_BASE_URL`. Verify health reports FFmpeg/FFprobe and configured AI, then test one small live job only when you accept the provider charge. The service's Docker engine/build/runtime and deployed HTTPS/CORS must pass smoke testing before distributing access. [Deployment flag reference](https://docs.cloud.google.com/sdk/gcloud/reference/run/deploy).

## 6. Publish the frontend in the existing GitHub repository

1. Review and commit these changes to the existing repository and push the approved commit to `main`; do not run `gh repo create`.
2. In repository **Settings → Pages → Build and deployment**, select **GitHub Actions**.
3. In **Settings → Secrets and variables → Actions → Variables**, create repository variable `VITE_API_BASE_URL` equal to `$backendUrl`, with no trailing slash or path; this is a public URL, not a secret.
4. In **Settings → Environments → github-pages**, configure a required reviewer if your GitHub plan supports it and restrict deployment to `main`; otherwise retain the manual workflow approval procedure.
5. In **Actions → Deploy frontend to GitHub Pages → Run workflow**, select `main` and explicitly approve the release; the job installs locked packages, tests, builds with the repository subpath, and deploys the Pages artifact.
6. Open `https://phyulwin.github.io/openai_multilingual_video_audio_translator_linguaecho/`, enter an individual access token, and run the checks below.

The workflow uses the existing repo's `GITHUB_TOKEN` with contents-read, Pages-write, and OIDC permissions; no personal GitHub token or GCP key is required. A repository must meet your plan's Pages eligibility; no plan purchase is included. A custom domain or user/organization-root site requires changing `PAGES_BASE_PATH` accordingly. [GitHub Pages workflow documentation](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages).

## 7. Acceptance, operating procedures, and costs

Use two separate browser profiles with distinct provisioned users: upload/create a demo as Alice, confirm Bob's library is empty, and verify Bob cannot read or mutate Alice's known project ID using his token. Never use Alice's signed link as an isolation test for Bob: possession of that private capability intentionally authorizes its limited read access.

Verify demo playback in all four modes, pause/resume, sentence replay, speed/voice/language choices, editing and regeneration on a live upload, cancellation, favorites/bookmarks, and TXT/SRT/JSON downloads. Reload while the instance exists, then test expiry/restart expectations with disposable data. The exported transcript is your durable text copy; retain your original media separately. Generated audio currently has no complete offline backup/import workflow.

Do not deploy updates while users need their temporary data. To rotate an OpenAI secret, add a secret version and redeploy pinned to its numeric version. To rotate/revoke a user token, replace its hash in the manifest while retaining that person's stable user ID, add a new access secret version, and redeploy; remove a user ID to revoke their tickets too. Old revisions/instances may remain briefly during rollout, so immediate revocation cannot be guaranteed across that transition. Use a new image tag on each release and keep a known-good image for rollback; rollback does not restore temporary projects.

Rate counters reset on process replacement and are not globally durable or a hard spending cap. Invited users reduce abuse; this is not sufficient for anonymous public signups or hostile high-volume traffic. Cloud Run's maximum instances limits capacity but cannot prevent all internet request/egress charges. Set Google Cloud billing alerts and OpenAI project usage controls before distributing tokens; budget alerts are not automatic shutdown. Do not assume provider processing is exactly once after disconnects.

Potential charges include Cloud Run CPU/RAM/request time, internet egress for original/generated media, Artifact Registry image storage, Secret Manager, logs outside the exclusion, GitHub Actions/Pages plan usage, and OpenAI transcription/translation/TTS. No permanent user-media database/storage is provisioned. Illustratively, at the published Tier-1 request-billed rates of $0.000024/vCPU-second and $0.0000025/GiB-second, one vCPU plus 2 GiB for a 300-second active interval is about **$0.0087** before free tiers, requests, egress, and provider charges; 1,000 such intervals are about **$8.70 in compute only**. Concurrent requests share an instance; polling can keep billing active. Confirm current regional rates before approval. [Cloud Run pricing](https://cloud.google.com/run/pricing).

## Verification record

- Backend: 44 tests passed, including per-user endpoint isolation, signed-ticket scope/tampering/revocation, byte ranges, HTTPS/CORS, expiry, admission recovery, request-owned processing, retry reuse, deadline, processing allowances, and invalid deployment configuration.
- Frontend: 22 unit/component tests passed, including the unchanged bilingual playback tests and new backend URL/credential/media-ticket tests; TypeScript and Vite build passed.
- Browser: both existing Playwright acceptance tests passed against an isolated local server; a separate real-browser smoke check passed the repository-subpath build against a different-origin API with production access middleware, covering the token prompt, CORS, signed media, bilingual transition, and export (local HTTP with simulated TLS ingress, not a deployed HTTPS test).
- Docker daemon was unavailable during preparation; the container image was not built or run, and Cloud Run/Pages were not deployed.
- No live OpenAI calls were used for verification; model-account access and paid end-to-end processing require your approved smoke test.

## File manifest

Modified existing files:

- `.gitignore`
- `backend/app/__init__.py`
- `backend/app/config.py`
- `backend/app/routes.py`
- `backend/app/services/ai.py`
- `backend/app/services/jobs.py`
- `backend/app/services/media.py`
- `frontend/index.html`
- `frontend/playwright.config.ts`
- `frontend/src/App.tsx`
- `frontend/src/api.ts`
- `frontend/src/components/MediaPlayer.tsx`
- `frontend/src/components/Workspace.test.tsx`
- `frontend/src/styles.css`
- `frontend/src/types.ts`
- `frontend/vite.config.ts`

Added files:

- `.dockerignore`
- `.gcloudignore`
- `.github/workflows/checks.yml`
- `.github/workflows/pages.yml`
- `DEPLOYMENT.md`
- `Dockerfile`
- `backend/app/security.py`
- `backend/cloud_run.py`
- `backend/tests/test_production.py`
- `deploy/cloud-run.env.yaml`
- `frontend/.env.example`
- `frontend/src/api.test.ts`
- `scripts/create_access_users.py`

Existing local `.env`, SQLite, uploads, and generated audio are excluded from deployment inputs and were not migrated or edited.
