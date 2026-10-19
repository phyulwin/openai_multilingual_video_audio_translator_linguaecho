// Workspace.tsx — Reusable upload, language, transcript, and export panels.
import { useEffect, useRef, useState, type ReactNode } from "react";
import {
  UploadCloud,
  Globe2,
  Search,
  Play,
  Star,
  Copy,
  Download,
  Pencil,
  Check,
  X,
  Flower2,
} from "lucide-react";
import { upload, exportUrl } from "../api";
import { time } from "./MediaPlayer";
import type { Project, Health, Segment } from "../types";
export function Panel({
  title,
  children,
  id,
  extra,
}: {
  title: string;
  children: ReactNode;
  id?: string;
  extra?: ReactNode;
}) {
  // Shared vintage frame keeps the decoration separate from real controls.
  return (
    <section className="panel frame" id={id}>
      <div className="panel-heading">
        <h2>
          <Flower2 size={17} />
          {title}
        </h2>
        {extra || (
          <span className="ornament" aria-hidden="true">
            ❧ ✧
          </span>
        )}
      </div>
      <div className="panel-body">{children}</div>
    </section>
  );
}
export function Uploader({
  health,
  onProject,
  onError,
}: {
  health: Health | null;
  onProject: (project: Project) => void;
  onError: (message: string) => void;
}) {
  // Validate locally for immediate feedback; the server validates real media streams.
  const input = useRef<HTMLInputElement>(null),
    xhr = useRef<XMLHttpRequest | null>(null);
  const [progress, setProgress] = useState<number | null>(null),
    [drag, setDrag] = useState(false);
  useEffect(
    () => () => {
      xhr.current?.abort();
    },
    [],
  );
  const choose = (file?: File) => {
    if (!file || progress !== null) return;
    if (
      !["mp4", "mov", "webm", "mkv", "mp3", "wav", "m4a"].includes(
        file.name.split(".").pop()?.toLowerCase() || "",
      )
    ) {
      onError("Choose MP4, MOV, WEBM, MKV, MP3, WAV, or M4A media.");
      return;
    }
    if (file.size > (health?.max_upload_mb || 200) * 1024 * 1024) {
      onError(`The upload limit is ${health?.max_upload_mb || 200} MB.`);
      return;
    }
    setProgress(0);
    xhr.current = upload(
      file,
      setProgress,
      (p) => {
        setProgress(null);
        xhr.current = null;
        onProject(p);
      },
      (m) => {
        setProgress(null);
        xhr.current = null;
        onError(m);
      },
    );
  };
  return (
    <Panel title="1. Upload your media" id="upload">
      <div className="upload-tabs">
        <span className="tab-active">
          <UploadCloud size={15} /> Upload file
        </span>
        <span className="muted">Your next discovery starts here</span>
      </div>
      <button
        className={`dropzone ${drag ? "dragging" : ""}`}
        disabled={progress !== null}
        onClick={() => input.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setDrag(true);
        }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDrag(false);
          choose(e.dataTransfer.files[0]);
        }}
      >
        <UploadCloud size={35} />
        <strong>Drop a video or audio file here</strong>
        <span>
          or <u>browse your files</u>
        </span>
      </button>
      <input
        ref={input}
        aria-label="Upload media file"
        className="sr-only"
        type="file"
        accept=".mp4,.mov,.webm,.mkv,.mp3,.wav,.m4a"
        onChange={(e) => {
          choose(e.target.files?.[0]);
          e.target.value = "";
        }}
      />
      <small className="formats">
        MP4, MOV, WEBM, MKV, MP3, WAV, M4A{" "}
        <span>Up to {health?.max_upload_mb || 200} MB</span>
      </small>
      {progress !== null && (
        <div className="upload-progress">
          <progress max="100" value={progress} />
          <span>
            {progress}% {progress === 100 ? "· Validating media…" : ""}
          </span>
          <button onClick={() => xhr.current?.abort()}>Cancel upload</button>
        </div>
      )}
    </Panel>
  );
}
export function LanguageSelector({
  label,
  value,
  onChange,
  languages,
  auto = false,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  languages: Health["languages"];
  auto?: boolean;
}) {
  // A searchable native select remains accessible on mobile and keyboard devices.
  const [search, setSearch] = useState("");
  const options = languages.filter(
    (l) =>
      l.code === value ||
      `${l.name} ${l.code}`.toLowerCase().includes(search.toLowerCase()),
  );
  return (
    <div className="language-picker">
      <div className="language-label">
        <span>{label}</span>
        <div className="language-search">
          <Search size={13} />
          <input
            aria-label={`Search ${label.toLowerCase()}`}
            placeholder="Search languages…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <div className="select-wrap">
          <Globe2 size={18} />
          <select
            aria-label={label}
            value={value}
            onChange={(e) => onChange(e.target.value)}
          >
            {auto && <option value="auto">Auto Detect</option>}
            {options.map((l) => (
              <option key={l.code} value={l.code}>
                {l.name} ({l.code})
              </option>
            ))}
          </select>
        </div>
      </div>
    </div>
  );
}
export function ExportPanel({
  project,
  target,
  notify,
}: {
  project: Project | null;
  target: string;
  notify: (message: string) => void;
}) {
  // All download links resolve to backend-generated Unicode files.
  const copy = async () => {
    if (!project) return;
    try {
      await navigator.clipboard.writeText(
        project.segments
          .map(
            (s) =>
              `${s.original_text}\n${project.translations[target]?.texts[String(s.id)] || ""}`,
          )
          .join("\n\n"),
      );
      notify("Transcript copied.");
    } catch {
      notify("Clipboard unavailable; download TXT instead.");
    }
  };
  return (
    <Panel title="Export & keep" id="exports">
      <div className="export-list">
        <button
          disabled={!project?.segments.length}
          onClick={() => void copy()}
        >
          <Copy size={16} />
          Copy bilingual transcript
        </button>
        {[
          ["Original transcript", "txt", "original"],
          ["Translated transcript", "txt", "translated"],
          ["Bilingual transcript", "txt", "bilingual"],
          ["Original subtitles", "srt", "original"],
          ["Translated subtitles", "srt", "translated"],
          ["Bilingual JSON", "json", "bilingual"],
        ].map(([label, format, language]) =>
          project?.segments.length &&
          (language === "original" || project.translations[target]) ? (
            <a
              key={label}
              href={exportUrl(project, target, format, language)}
              download
            >
              <Download size={15} />
              {label}
              <small>{format.toUpperCase()}</small>
            </a>
          ) : (
            <button key={label} disabled>
              <Download size={15} />
              {label}
              <small>{format.toUpperCase()}</small>
            </button>
          ),
        )}
      </div>
    </Panel>
  );
}
export function Transcript({
  project,
  target,
  active,
  onPlay,
  onEdit,
  onFavorite,
  notify,
  favoritesOnly = false,
}: {
  project: Project;
  target: string;
  active: number;
  onPlay: (index: number) => void;
  onEdit: (sid: number, text: string) => Promise<void>;
  onFavorite: (row: Segment) => void;
  notify: (message: string) => void;
  favoritesOnly?: boolean;
}) {
  // Keep draft corrections separate until the user explicitly saves them.
  const [search, setSearch] = useState(""),
    [show, setShow] = useState(true),
    [copyMode, setCopyMode] = useState("both"),
    [editing, setEditing] = useState<number | null>(null),
    [draft, setDraft] = useState("");
  const current = useRef<HTMLDivElement>(null);
  const texts = project.translations[target]?.texts || {};
  useEffect(() => {
    const row = current.current,
      container = row?.parentElement;
    if (row && container)
      container.scrollTo?.({
        top: row.offsetTop - container.offsetTop - 30,
        behavior: "smooth",
      });
  }, [active]);
  const copy = async (row: Segment) => {
    try {
      await navigator.clipboard.writeText(
        copyMode === "original"
          ? row.original_text
          : copyMode === "translated"
            ? texts[String(row.id)] || ""
            : `${row.original_text}\n${texts[String(row.id)] || ""}`,
      );
      notify("Sentence copied.");
    } catch {
      notify("Clipboard unavailable; use a transcript export.");
    }
  };
  return (
    <Panel
      title={favoritesOnly ? "Favorite sentences" : "Transcript & translation"}
      id="transcript"
      extra={<span className="count">{project.segments.length} sentences</span>}
    >
      <div className="transcript-tools">
        <label className="search-box">
          <Search size={15} />
          <input
            aria-label="Search transcript"
            placeholder="Find a word or a little inspiration…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </label>
        <label className="check">
          <input
            type="checkbox"
            checked={show}
            onChange={(e) => setShow(e.target.checked)}
          />
          Translation
        </label>
        <select
          aria-label="Copy language"
          value={copyMode}
          onChange={(e) => setCopyMode(e.target.value)}
        >
          <option value="both">Copy both</option>
          <option value="original">Copy original</option>
          <option value="translated">Copy translated</option>
        </select>
      </div>
      <div className="transcript-rows">
        {project.segments
          .filter(
            (s) =>
              (!favoritesOnly || s.favorite) &&
              `${s.original_text} ${texts[String(s.id)] || ""}`
                .toLowerCase()
                .includes(search.toLowerCase()),
          )
          .map((row) => {
            const index = project.segments.findIndex((s) => s.id === row.id);
            return (
              <div
                className={`transcript-row ${index === active ? "active" : ""}`}
                key={row.id}
                ref={index === active ? current : undefined}
              >
                <button
                  className="sentence-play"
                  aria-label={`Play sentence ${row.id}`}
                  onClick={() => onPlay(index)}
                >
                  <span>{time(row.start)}</span>
                  <Play size={15} />
                </button>
                <p dir="auto" lang={project.source_language}>
                  {row.original_text}
                </p>
                {show &&
                  (editing === row.id ? (
                    <div className="edit-translation">
                      <textarea
                        aria-label="Translation correction"
                        dir="auto"
                        value={draft}
                        onChange={(e) => setDraft(e.target.value)}
                      />
                      <button
                        aria-label="Save correction"
                        onClick={() => {
                          void onEdit(row.id, draft)
                            .then(() => setEditing(null))
                            .catch((error) =>
                              notify(
                                error.message ||
                                  "Correction could not be saved.",
                              ),
                            );
                        }}
                      >
                        <Check size={16} />
                      </button>
                      <button
                        aria-label="Cancel correction"
                        onClick={() => setEditing(null)}
                      >
                        <X size={16} />
                      </button>
                    </div>
                  ) : (
                    <p dir="auto" lang={target}>
                      {texts[String(row.id)] || (
                        <em>Translation not generated</em>
                      )}
                    </p>
                  ))}
                <div className="row-actions">
                  <button
                    aria-label={`Copy sentence ${row.id}`}
                    onClick={() => void copy(row)}
                  >
                    <Copy size={14} />
                  </button>
                  <button
                    aria-label={`Favorite sentence ${row.id}`}
                    aria-pressed={row.favorite}
                    onClick={() => onFavorite(row)}
                  >
                    <Star
                      size={15}
                      fill={row.favorite ? "currentColor" : "none"}
                    />
                  </button>
                  <button
                    aria-label={`Edit sentence ${row.id}`}
                    disabled={project.demo || !texts[String(row.id)]}
                    onClick={() => {
                      setEditing(row.id);
                      setDraft(texts[String(row.id)] || "");
                    }}
                  >
                    <Pencil size={14} />
                  </button>
                </div>
              </div>
            );
          })}
      </div>
      {!project.segments.length && (
        <div className="empty">
          <Globe2 size={30} />
          <h3>A world of words awaits</h3>
          <p>Process your media to see every sentence, side by side.</p>
        </div>
      )}
    </Panel>
  );
}
