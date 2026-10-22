// MediaPlayer.tsx — HTML5 player controls around the isolated playback engine.
import { useEffect, useRef, useState } from "react";
import {
  Play,
  Pause,
  SkipBack,
  SkipForward,
  RotateCcw,
  Volume2,
  VolumeX,
  Maximize,
  Headphones,
} from "lucide-react";
import { PlaybackEngine, type Snapshot, type MediaPort } from "../playback";
import { mediaUrl } from "../api";
import type { Project, Mode } from "../types";
export const time = (value: number) =>
  `${Math.floor((value || 0) / 60)
    .toString()
    .padStart(2, "0")}:${Math.floor((value || 0) % 60)
    .toString()
    .padStart(2, "0")}`;
interface Props {
  project: Project;
  target: string;
  voice: string;
  mode: Mode;
  audioOnly: boolean;
  onActive: (index: number) => void;
  onError: (message: string) => void;
  engineRef: React.RefObject<PlaybackEngine | null>;
}
export function MediaPlayer({
  project,
  target,
  voice,
  mode,
  audioOnly,
  onActive,
  onError,
  engineRef,
}: Props) {
  // Recreate only for a changed media/translation identity, not polling updates.
  const video = useRef<HTMLVideoElement>(null),
    speech = useRef<HTMLAudioElement>(null);
  const [state, setState] = useState<Snapshot>({
    phase: "idle",
    index: 0,
    playing: false,
    time: 0,
  });
  const [speed, setSpeed] = useState(1),
    [volume, setVolume] = useState(0.8),
    [muted, setMuted] = useState(false);
  const callbacks = useRef({ onActive, onError });
  callbacks.current = { onActive, onError };
  const ready =
    mode === "original" ||
    (project.segments.length > 0 && project.segments.every(
      (s) => project.translations[target]?.audio[voice]?.[String(s.id)],
    ));
  const readyRef = useRef(ready);
  readyRef.current = ready;
  useEffect(() => {
    const engine = new PlaybackEngine(
      video.current! as unknown as MediaPort,
      speech.current! as unknown as MediaPort,
      project.segments,
      mode,
      (id) =>
        mediaUrl(project, `/api/projects/${project.id}/audio/${id}?target=${encodeURIComponent(target)}&voice=${encodeURIComponent(voice)}&v=${encodeURIComponent(project.translations[target]?.audio[voice]?.[String(id)] || "")}`),
      (snapshot) => {
        setState(snapshot);
        callbacks.current.onActive(snapshot.index);
      },
      (message) => callbacks.current.onError(message),
    );
    engineRef.current = engine;
    engine.setMode(mode);
    let frame = 0;
    const tick = () => {
      engine.tick();
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => {
      cancelAnimationFrame(frame);
      engine.dispose();
      engineRef.current = null;
    };
  }, [
    project.id,
    project.media_ticket,
    target,
    voice,
    JSON.stringify(project.segments),
    JSON.stringify(project.translations[target]?.texts),
  ]);
  useEffect(() => {
    if (!ready) engineRef.current?.pause();
    engineRef.current?.setMode(mode);
  }, [mode, ready]);
  useEffect(() => {
    engineRef.current?.settings(speed, volume, muted);
  }, [speed, volume, muted, project.id, target, voice]);
  useEffect(() => {
    // Keyboard controls never intercept typing in forms or editable text.
    const key = (event: KeyboardEvent) => {
      if (!readyRef.current) return;
      if (
        (event.target as HTMLElement).closest(
          "input,textarea,select,button,[contenteditable]",
        )
      )
        return;
      if (event.code === "Space") {
        event.preventDefault();
        engineRef.current?.toggle();
      }
      if (event.code === "ArrowRight") {
        event.preventDefault();
        engineRef.current?.skip(1);
      }
      if (event.code === "ArrowLeft") {
        event.preventDefault();
        engineRef.current?.skip(-1);
      }
    };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, []);
  const texts = project.translations[target]?.texts || {};
  const row = project.segments[state.index];
  return (
    <section className="player frame" aria-label="Media player">
      <div
        className={`screen ${audioOnly || project.kind === "audio" ? "audio-screen" : ""}`}
      >
        <video
          ref={video}
          src={mediaUrl(project, project.media_url)}
          playsInline
          preload="metadata"
          poster={`${import.meta.env.BASE_URL}hero.png`}
          onEnded={() => engineRef.current?.mediaEnded()}
          onError={() =>
            onError(
              "This browser cannot decode the media preview; try an MP4/H.264 or MP3 file.",
            )
          }
          className={
            audioOnly || project.kind === "audio" ? "concealed-video" : ""
          }
        />
        {(audioOnly || project.kind === "audio") && (
          <div className="audio-art">
            <Headphones size={54} />
            <h3>{project.name}</h3>
            <span>Listen. Understand. Connect.</span>
          </div>
        )}
        <div className="screen-badge">
          {project.demo ? "OFFLINE DEMO · FIXTURE MEDIA" : project.name}
        </div>
        {row && (
          <div className="subtitles">
            <span dir="auto">{row.original_text}</span>
            <strong dir="auto">{texts[String(row.id)]}</strong>
          </div>
        )}
        <span className="phase">
          {state.phase === "translation"
            ? "Translated voice · video paused"
            : state.playing
              ? "Original audio"
              : "Ready when you are"}
        </span>
      </div>
      <audio
        ref={speech}
        preload="auto"
        onError={() => {
          engineRef.current?.pause();
          onError(
            "Translated audio could not load; regenerate speech or try again.",
          );
        }}
      />
      <div className="player-controls">
        <input
          aria-label="Seek"
          type="range"
          min="0"
          max={project.duration}
          step="0.05"
          value={Math.min(state.time, project.duration)}
          onChange={(e) => engineRef.current?.seek(+e.target.value)}
        />
        <div className="control-row">
          <button
            aria-label={state.playing ? "Pause" : "Play"}
            disabled={!ready}
            onClick={() => engineRef.current?.toggle()}
          >
            {state.playing ? <Pause /> : <Play />}
          </button>
          <button
            aria-label="Previous sentence"
            onClick={() => engineRef.current?.skip(-1)}
            disabled={!ready || !row}
          >
            <SkipBack size={18} />
          </button>
          <button
            aria-label="Next sentence"
            onClick={() => engineRef.current?.skip(1)}
            disabled={!ready || !row}
          >
            <SkipForward size={18} />
          </button>
          <button
            aria-label="Replay sentence"
            onClick={() => engineRef.current?.sentence(state.index)}
            disabled={!ready || !row}
          >
            <RotateCcw size={16} />
          </button>
          <small>
            {time(state.time)} / {time(project.duration)}
          </small>
          <span className="spacer" />
          <button
            aria-label={muted ? "Unmute" : "Mute"}
            onClick={() => setMuted(!muted)}
          >
            {muted ? <VolumeX size={18} /> : <Volume2 size={18} />}
          </button>
          <input
            aria-label="Volume"
            className="volume"
            type="range"
            min="0"
            max="1"
            step="0.05"
            value={volume}
            onChange={(e) => setVolume(+e.target.value)}
          />
          <select
            aria-label="Playback speed"
            value={speed}
            onChange={(e) => setSpeed(+e.target.value)}
          >
            {[0.5, 0.75, 1, 1.25, 1.5, 2].map((v) => (
              <option key={v} value={v}>
                {v}×
              </option>
            ))}
          </select>
          <button
            aria-label="Fullscreen"
            onClick={() => {
              void video.current?.parentElement
                ?.requestFullscreen()
                .catch(() =>
                  onError("Fullscreen is unavailable in this browser."),
                );
            }}
          >
            <Maximize size={18} />
          </button>
        </div>
        {!ready && (
          <p className="player-warning">
            Generate speech for this language and voice, or choose Original
            Only.
          </p>
        )}
      </div>
    </section>
  );
}
