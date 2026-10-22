// App.tsx — Persistent local workspace, library, settings, and processing workflow.
import { useCallback, useEffect, useRef, useState } from "react";
import {
  Home,
  UploadCloud,
  FolderHeart,
  Heart,
  Download,
  GraduationCap,
  Settings,
  Globe2,
  Flower2,
  ArrowRight,
  Video,
  Headphones,
  Play,
  Search,
  Star,
  Trash2,
  Pencil,
  BookOpen,
  CheckCircle2,
  Info,
  X,
  LoaderCircle,
} from "lucide-react";
import { api } from "./api";
import type { Health, Project, Mode, Segment } from "./types";
import type { PlaybackEngine } from "./playback";
import { MediaPlayer, time } from "./components/MediaPlayer";
import {
  Panel,
  Uploader,
  LanguageSelector,
  Transcript,
  ExportPanel,
} from "./components/Workspace";
const modes: { id: Mode; name: string; description: string }[] = [
  {
    id: "original-translation",
    name: "Original → Translation",
    description: "Listen, then understand.",
  },
  {
    id: "translation-original",
    name: "Translation → Original",
    description: "Understand, then listen.",
  },
  {
    id: "translation",
    name: "Translation Only",
    description: "A familiar language.",
  },
  {
    id: "original",
    name: "Original Only",
    description: "The original experience.",
  },
];
const navigation = [
  ["Home", Home],
  ["My Library", FolderHeart],
  ["Favorites", Heart],
  ["Learning Tools", GraduationCap],
  ["Settings", Settings],
] as const;

export default function App() {
  // The server owns project data; local component state owns listening preferences.
  const [health, setHealth] = useState<Health | null>(null),
    [projects, setProjects] = useState<Project[]>([]),
    [project, setProject] = useState<Project | null>(null);
  const [page, setPage] = useState("Home"),
    [source, setSource] = useState("auto"),
    [target, setTarget] = useState("en"),
    [voice, setVoice] = useState("coral");
  const [mode, setMode] = useState<Mode>("original-translation"),
    [audioOnly, setAudioOnly] = useState(false),
    [active, setActive] = useState(0),
    [notice, setNotice] = useState(""),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [query, setQuery] = useState("");
  const engine = useRef<PlaybackEngine | null>(null);
  const fail = useCallback((message: string) => setError(message), []);
  const refresh = useCallback(async () => {
    const list = await api<Project[]>("/projects");
    setProjects(list);
    return list;
  }, []);
  const open = useCallback((p: Project) => {
    engine.current?.dispose();
    setProject(p);
    setActive(0);
    setSource(p.source_language);
    const first = Object.keys(p.translations)[0];
    if (first) {
      setTarget(first);
      setVoice(p.translations[first].voice);
    }
    setPage("Home");
    setError("");
    localStorage.setItem("linguaecho-project", p.id);
  }, []);
  useEffect(() => {
    void Promise.all([api<Health>("/health"), refresh()])
      .then(([h, list]) => {
        setHealth(h);
        setVoice(h.default_voice);
        const saved = list.find(
          (p) => p.id === localStorage.getItem("linguaecho-project"),
        );
        if (saved) open(saved);
      })
      .catch((e) => fail(e.message));
  }, []);
  useEffect(() => {
    if (!notice) return;
    const timer = setTimeout(() => setNotice(""), 5000);
    return () => clearTimeout(timer);
  }, [notice]);
  useEffect(() => {
    // Poll only active jobs and ignore responses belonging to an old project.
    if (!project || !["queued", "processing"].includes(project.status)) return;
    const id = project.id;
    let cancelled = false;
    const timer = setInterval(() => {
      void api<Project>(`/projects/${id}/status`)
        .then((p) => {
          if (!cancelled) {
            setProject(p);
            if (!["queued", "processing"].includes(p.status))
              void refresh().catch((e) => fail(e.message));
          }
        })
        .catch((e) => {
          if (!cancelled) {
            // Stop polling expired or unreachable workspaces instead of prompting repeatedly.
            fail(e.message);
            setProject((current) => current?.id === id
              ? { ...current, status: "error", message: e.message }
              : current);
          }
        });
    }, 1000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [project?.id, project?.status]);
  const run = async (action: () => Promise<void>) => {
    setError("");
    setBusy(true);
    try {
      await action();
    } catch (e) {
      fail(e instanceof Error ? e.message : "Operation failed.");
    } finally {
      setBusy(false);
    }
  };
  const demo = () =>
    void run(async () => {
      const p = await api<Project>("/demo", "POST");
      open(p);
      await refresh();
      setNotice(
        "Offline demo loaded: scripted text and local synthetic fixture voices, not live AI output.",
      );
    });
  const process = () =>
    void run(async () => {
      if (!project) return;
      engine.current?.pause();
      setProject({ ...project, status: "processing" });
      const result = await api<Project>(`/projects/${project.id}/process`, "POST", {
        source, target, voice,
      });
      setProject((current) => current?.id === result.id ? result : current);
    });
  const patch = async (id: string, data: unknown) => {
    const p = await api<Project>(`/projects/${id}`, "PATCH", data);
    if (project?.id === id) setProject(p);
    await refresh();
  };
  const segment = async (row: Segment, data: unknown) => {
    if (!project) return;
    setProject(
      await api<Project>(
        `/projects/${project.id}/segments/${row.id}`,
        "PATCH",
        data,
      ),
    );
  };
  const navigate = (name: string) => {
    setPage(name);
    if (
      [
        "My Library",
        "Favorites",
        "Settings",
        "Learning Tools",
        "Help",
        "Features",
      ].includes(name)
    )
      engine.current?.pause();
    setTimeout(() => {
      document
        .getElementById(
          name === "Upload Media"
            ? "upload"
            : name === "Export"
              ? "exports"
              : "workspace",
        )
        ?.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 0);
  };
  const processing =
    !!project && ["queued", "processing"].includes(project.status);
  const languages = health?.languages || [{ code: "en", name: "English" }];
  const library = page === "My Library" || page === "Favorites";
  const info = ["Settings", "Learning Tools", "Help", "Features"].includes(
    page,
  );
  const ready =
    (!!project && mode === "original") ||
    (!!project?.segments.length &&
      project.segments.every(
        (s) => project.translations[target]?.audio[voice]?.[String(s.id)],
      ));
  return (
    <div className="site-shell">
      <header className="topbar">
        <button className="wordmark" onClick={() => navigate("Home")}>
          <Globe2 />
          <span>
            Lingua<span>Echo</span>
            <small>MULTILINGUAL VIDEO & AUDIO PLAYER</small>
          </span>
        </button>
        <nav aria-label="Main navigation">
          {["Features", "Help"].map(
            (n) => (
              <button
                key={n}
                className={page === n ? "selected" : ""}
                onClick={() => navigate(n)}
              >
                {n}
              </button>
            ),
          )}
        </nav>
      </header>
      <section className="hero">
        <div className="hero-copy">
          <span className="eyebrow">
            A LITTLE CURIOSITY. A WHOLE NEW WORLD.
          </span>
          <h1>
            More Voices,
            <br />
            <em>A Wider World.</em>
          </h1>
          <p>
            Understand videos and audio in any language,
            <br />
            one sentence at a time.
          </p>
          <button className="primary" onClick={() => navigate("Upload Media")}>
            Start your journey <ArrowRight size={16} />
          </button>
          <button className="hero-demo" onClick={demo} disabled={busy}>
            <Play size={14} />
            Explore the demo
          </button>
        </div>
        <span className="hero-note">
          Different languages.
          <br />
          Same feelings.
        </span>
        <span className="hero-flourish" aria-hidden="true">
          ✧
        </span>
      </section>
      <div className="ribbon">
        <Flower2 size={14} />
        <span>A place for every voice, a bridge to every story.</span>
        <Flower2 size={14} />
      </div>
      <div className="layout" id="workspace">
        <aside className="left-sidebar">
          <nav className="side-nav frame" aria-label="Workspace navigation">
            {navigation.map(([name, Icon]) => (
              <button
                key={name}
                className={page === name ? "active" : ""}
                onClick={() => navigate(name)}
              >
                <Icon size={19} />
                {name}
              </button>
            ))}
          </nav>
          <div className="postcard frame">
            <span className="eyebrow">CURIOSITY HAS NO BORDERS</span>
            <Globe2 size={58} />
            <h3>
              Any language.
              <br />
              <em>More connection.</em>
            </h3>
            <p>Discover the stories waiting on the other side of a language.</p>
            <ul>
              <li>
                <CheckCircle2 />
                Auto detection
              </li>
              <li>
                <CheckCircle2 />
                {health?.languages.length || "50+"} speech languages
              </li>
              <li>
                <CheckCircle2 />
                Your own media
              </li>
              <li>
                <CheckCircle2 />
                Learn at your pace
              </li>
            </ul>
            <Flower2 className="postcard-flower" />
          </div>
        </aside>
        <main>
          {error && (
            <div role="alert" className="alert error">
              <Info size={18} />
              <span>{error}</span>
              <button aria-label="Dismiss error" onClick={() => setError("")}>
                <X size={16} />
              </button>
            </div>
          )}
          {!health && (
            <div className="alert">Connecting to your workspace…</div>
          )}
          {library ? (
            <Panel title={page}>
              <label className="search-box">
                <Search size={16} />
                <input
                  aria-label="Search projects"
                  placeholder="Search your collection…"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                />
              </label>
              <div className="library-grid">
                {projects
                  .filter(
                    (p) =>
                      (page !== "Favorites" || p.favorite) &&
                      p.name.toLowerCase().includes(query.toLowerCase()),
                  )
                  .map((p) => (
                    <article className="library-card" key={p.id}>
                      <button className="library-open" onClick={() => open(p)}>
                        <div className="library-art">
                          {p.kind === "video" ? <Video /> : <Headphones />}
                        </div>
                        <strong>{p.name}</strong>
                        <small>
                          {time(p.duration)} ·{" "}
                          {p.demo ? "Offline demo" : p.status}
                        </small>
                      </button>
                      <div className="library-actions">
                        <button
                          aria-label={`Favorite ${p.name}`}
                          onClick={() =>
                            void run(() =>
                              patch(p.id, { favorite: !p.favorite }),
                            )
                          }
                        >
                          <Star
                            size={16}
                            fill={p.favorite ? "currentColor" : "none"}
                          />
                        </button>
                        <button
                          aria-label={`Rename ${p.name}`}
                          onClick={() => {
                            const name = window.prompt("Project name", p.name);
                            if (name?.trim())
                              void run(() =>
                                patch(p.id, { name: name.trim() }),
                              );
                          }}
                        >
                          <Pencil size={16} />
                        </button>
                        <button
                          aria-label={`Delete ${p.name}`}
                          onClick={() => {
                            if (
                              window.confirm(
                                `Delete "${p.name}" and its local media and speech files?`,
                              )
                            )
                              void run(async () => {
                                await api(`/projects/${p.id}`, "DELETE");
                                if (project?.id === p.id) {
                                  setProject(null);
                                  localStorage.removeItem("linguaecho-project");
                                }
                                await refresh();
                              });
                          }}
                        >
                          <Trash2 size={16} />
                        </button>
                      </div>
                    </article>
                  ))}
              </div>
              {!projects.length && (
                <div className="empty">
                  <FolderHeart size={32} />
                  <h3>Your collection starts here</h3>
                  <p>Upload media or explore the offline demo.</p>
                  <button onClick={demo}>Open demo</button>
                </div>
              )}
              {page === "Favorites" && project && (
                <Transcript
                  project={project}
                  target={target}
                  active={active}
                  onPlay={(index) => {
                    setPage("Home");
                    setTimeout(() => engine.current?.sentence(index), 100);
                  }}
                  onEdit={async (sid, text) => {
                    await segment(project.segments.find((s) => s.id === sid)!, {
                      target,
                      translated_text: text,
                    });
                  }}
                  onFavorite={(row) =>
                    void run(() => segment(row, { favorite: !row.favorite }))
                  }
                  notify={setNotice}
                  favoritesOnly
                />
              )}
            </Panel>
          ) : info ? (
            <Panel title={page}>
              {page === "Settings" ? (
                <div className="settings-content">
                  <h3>Your listening preferences</h3>
                  <label>
                    AI voice
                    <select
                      aria-label="AI voice"
                      value={voice}
                      onChange={(e) => setVoice(e.target.value)}
                    >
                      {(health?.voices || ["coral"]).map((v) => (
                        <option key={v}>{v}</option>
                      ))}
                    </select>
                  </label>
                  <p>
                    Changing voice requires speech generation for that voice;
                    existing audio remains cached.
                  </p>
                  <label className="check">
                    <input
                      type="checkbox"
                      checked={audioOnly}
                      onChange={(e) => setAudioOnly(e.target.checked)}
                    />
                    Prefer audio-only listening
                  </label>
                  <h3>Server status</h3>
                  <p>
                    OpenAI:{" "}
                    {health?.ai_configured
                      ? "Configured"
                      : "Not configured — add OPENAI_API_KEY to .env"}
                  </p>
                  <p>
                    FFmpeg / FFprobe:{" "}
                    {health?.ffmpeg && health?.ffprobe
                      ? "Available"
                      : "Installation required"}
                  </p>
                  <p>Maximum upload: {health?.max_upload_mb || 200} MB</p>
                  <p>
                    Credentials are configured on the server and never sent to
                    the browser.
                  </p>
                </div>
              ) : (
                <div className="help-content">
                  <BookOpen size={34} />
                  <h3>
                    {page === "Learning Tools"
                      ? "Make every sentence a small discovery."
                      : "A familiar voice, a wider world."}
                  </h3>
                  <ol>
                    <li>
                      Upload a local video or audio file and choose your
                      languages.
                    </li>
                    <li>
                      Start processing to transcribe, translate, and generate an
                      AI voice.
                    </li>
                    <li>
                      Choose Original → Translation: the video pauses while the
                      translation speaks.
                    </li>
                    <li>
                      Replay a sentence, bookmark useful phrases, or hide the
                      translation to practice recall.
                    </li>
                    <li>
                      Keep transcript copies with TXT, SRT, or
                      JSON exports.
                    </li>
                  </ol>
                  <h3>Keyboard shortcuts</h3>
                  <p>
                    Space: play / pause · Left / Right: previous / next
                    sentence.
                  </p>
                  <h3>Your media, your workspace</h3>
                  <p>
                    Cloud projects expire after one hour and may disappear sooner; export your text and retain your original media. Processing sends audio
                    and transcript content to OpenAI. Translated speech uses an
                    AI voice. Local demo fixtures do not call any external
                    service.
                  </p>
                  <p>
                    Transcription is not speaker diarization; timing and
                    translation may need review. URL importing and accounts are
                    outside this local MVP.
                  </p>
                  <button className="primary" onClick={demo}>
                    <Play size={16} />
                    Try the offline demo
                  </button>
                </div>
              )}
            </Panel>
          ) : (
            <>
              <Uploader
                health={health}
                onProject={(p) => {
                  open(p);
                  setMode("original");
                  void refresh().catch((e) => fail(e.message));
                }}
                onError={fail}
              />
              <Panel title="2. Choose your languages">
                <div className="language-row">
                  <LanguageSelector
                    label="Source language"
                    value={source}
                    onChange={setSource}
                    languages={languages}
                    auto
                  />
                  <ArrowRight className="language-arrow" size={22} />
                  <LanguageSelector
                    label="Target language"
                    value={target}
                    onChange={setTarget}
                    languages={languages}
                  />
                </div>
                <div className="language-bottom">
                  <small>One world, many ways to say hello.</small>
                  <button
                    className="primary compact"
                    disabled={!project || processing || busy || project.demo}
                    onClick={process}
                  >
                    {processing ? (
                      <LoaderCircle size={15} className="spin" />
                    ) : (
                      <Flower2 size={15} />
                    )}{" "}
                    {project?.segments.length
                      ? "Generate translation & voice"
                      : "Translate my media"}
                  </button>
                </div>
                {project && (
                  <div className="project-status">
                    <span>
                      <strong>{project.name}</strong> · {time(project.duration)}{" "}
                      · {project.kind}
                    </span>
                    {project.demo ? (
                      <span className="demo-tag">OFFLINE DEMO</span>
                    ) : (
                      <small>{project.status}</small>
                    )}
                  </div>
                )}
                {project && (
                  <div className="status-line" aria-live="polite">
                    <span>{project.message}</span>
                    {processing && (
                      <>
                        <progress value={project.progress} max="100" />
                        <button
                          onClick={() =>
                            void run(async () => {
                              await api(
                                `/projects/${project.id}/cancel`,
                                "POST",
                              );
                              setNotice("Cancellation requested.");
                            })
                          }
                        >
                          Cancel
                        </button>
                      </>
                    )}
                  </div>
                )}
                {project?.demo && (
                  <p className="demo-disclosure">
                    Scripted sample text and local synthetic voices; this demo
                    does not use live AI.
                  </p>
                )}
              </Panel>
              <div className="playback-grid">
                <Panel title="3. Make it your own">
                  <div className="mode-grid">
                    {modes.map((m) => (
                      <label
                        key={m.id}
                        className={mode === m.id ? "chosen" : ""}
                      >
                        <input
                          type="radio"
                          name="mode"
                          value={m.id}
                          checked={mode === m.id}
                          onChange={() => setMode(m.id)}
                        />
                        <span>
                          <strong>{m.name}</strong>
                          <small>{m.description}</small>
                        </span>
                      </label>
                    ))}
                  </div>
                </Panel>
                <Panel title="4. Player options">
                  <div className="segmented">
                    <button
                      className={!audioOnly ? "selected" : ""}
                      onClick={() => setAudioOnly(false)}
                    >
                      <Video size={15} />
                      Video on
                    </button>
                    <button
                      className={audioOnly ? "selected" : ""}
                      onClick={() => setAudioOnly(true)}
                    >
                      <Headphones size={15} />
                      Audio only
                    </button>
                  </div>
                  <p className="info-note">
                    <Info size={15} />
                    <span>
                      The video pauses while the translated voice plays, then
                      your story continues.
                    </span>
                  </p>
                </Panel>
              </div>
              {project ? (
                <MediaPlayer
                  project={project}
                  target={target}
                  voice={voice}
                  mode={mode}
                  audioOnly={audioOnly}
                  onActive={setActive}
                  onError={fail}
                  engineRef={engine}
                />
              ) : (
                <div className="player-empty frame">
                  <div>
                    <span className="eyebrow">
                      EVERY STORY DESERVES TO BE UNDERSTOOD
                    </span>
                    <h2>
                      Your next favorite story
                      <br />
                      is waiting.
                    </h2>
                    <button onClick={demo} disabled={busy}>
                      <Play size={18} />
                      Listen to a sample
                    </button>
                    <small>
                      Clearly labeled offline demo · no API key needed
                    </small>
                  </div>
                </div>
              )}
              {project ? (
                <Transcript
                  project={project}
                  target={target}
                  active={active}
                  onPlay={(index) => {
                    if (!ready) {
                      fail("Generate speech first, or select Original Only.");
                      return;
                    }
                    engine.current?.sentence(index);
                  }}
                  onFavorite={(row) =>
                    void run(() => segment(row, { favorite: !row.favorite }))
                  }
                  onEdit={async (sid, text) => {
                    engine.current?.pause();
                    try {
                      await segment(
                        project.segments.find((s) => s.id === sid)!,
                        { target, translated_text: text },
                      );
                      setNotice(
                        "Correction saved; generate translation & voice to refresh speech.",
                      );
                    } catch (e) {
                      fail((e as Error).message);
                      throw e;
                    }
                  }}
                  notify={setNotice}
                />
              ) : (
                <Panel title="Transcript & translation">
                  <div className="empty">
                    <BookOpen size={30} />
                    <h3>Two languages. One conversation.</h3>
                    <p>
                      Your original words and translations will appear here.
                    </p>
                  </div>
                </Panel>
              )}
            </>
          )}
        </main>
        <aside className="right-sidebar">
          <Panel title="Welcome formats">
            <div className="format-icons">
              <Video />
              <span>
                MP4 · MOV
                <br />
                WEBM · MKV
              </span>
              <Headphones />
              <span>
                MP3 · WAV
                <br />
                M4A
              </span>
            </div>
            <p className="center muted">
              Up to {health?.max_upload_mb || 200} MB per file
            </p>
          </Panel>
          <ExportPanel project={project} target={target} notify={setNotice} />

          <div className="privacy-note">
            <CheckCircle2 size={15} />
            <span>
              Cloud workspaces are temporary; export before leaving.
            </span>
          </div>
        </aside>
      </div>
      <footer>
        <div className="footer-brand">
          <Globe2 size={34} />
          <div>
            Lingua<span>Echo</span>
            <small>Multilingual Video & Audio Player</small>
          </div>
        </div>
        <div className="footer-note">
          More understanding,
          <br />
          <em>a kinder world.</em>
          <small>LinguaEcho · A local, independent learning project</small>
        </div>
      </footer>
      {notice && (
        <div role="status" className="toast">
          <CheckCircle2 size={18} />
          {notice}
          <button
            aria-label="Dismiss notification"
            onClick={() => setNotice("")}
          >
            <X size={15} />
          </button>
        </div>
      )}
    </div>
  );
}
