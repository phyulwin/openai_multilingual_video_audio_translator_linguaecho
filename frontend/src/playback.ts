// playback.ts — Explicit, cancellable sentence playback state machine.
import type { Mode, Phase, Segment } from "./types";
export interface MediaPort {
  currentTime: number;
  duration: number;
  paused: boolean;
  src: string;
  playbackRate: number;
  volume: number;
  muted: boolean;
  play(): Promise<void>;
  pause(): void;
  onended: ((...args: never[]) => void) | null;
}
export interface Snapshot {
  phase: Phase;
  index: number;
  playing: boolean;
  time: number;
}

export class PlaybackEngine {
  // Epochs invalidate promises from seeks, mode changes, and disposed players.
  private epoch = 0;
  private phase: Phase = "idle";
  private resumePhase: Phase = "original";
  private playing = false;
  private index = 0;
  private disposed = false;
  private gap = false;
  constructor(
    private video: MediaPort,
    private speech: MediaPort,
    private segments: Segment[],
    private mode: Mode,
    private audioUrl: (id: number) => string,
    private changed: (snapshot: Snapshot) => void,
    private error: (message: string) => void,
  ) {}

  private emit() {
    this.changed({
      phase: this.phase,
      index: this.index,
      playing: this.playing,
      time: this.video.currentTime,
    });
  }
  private stopBoth() {
    this.epoch++;
    this.video.pause();
    this.speech.pause();
    this.speech.onended = null;
  }
  private async playMedia(media: MediaPort) {
    // Rejected autoplay and network failures stop both sources visibly.
    const token = this.epoch;
    try {
      await media.play();
      if (
        token !== this.epoch &&
        (!this.playing ||
          media !== (this.phase === "translation" ? this.speech : this.video))
      )
        media.pause();
    } catch (error) {
      if (token === this.epoch && !this.disposed) {
        this.pause();
        this.error(error instanceof Error ? error.message : "Playback failed.");
      }
    }
  }
  private original(seek?: number) {
    // The translated channel is always paused before original speech resumes.
    this.stopBoth();
    this.phase = "original";
    this.playing = true;
    if (seek !== undefined) this.video.currentTime = seek;
    this.emit();
    void this.playMedia(this.video);
  }
  private translated() {
    // Keep the video on the corresponding sentence while AI speech plays.
    this.stopBoth();
    this.gap = false;
    const segment = this.segments[this.index];
    if (!segment) {
      this.finish();
      return;
    }
    this.video.currentTime = segment.start;
    this.phase = "translation";
    this.playing = true;
    this.speech.src = this.audioUrl(segment.id);
    this.speech.currentTime = 0;
    const token = this.epoch;
    this.speech.onended = () => {
      if (token === this.epoch && this.playing) this.translationEnded();
    };
    this.emit();
    void this.playMedia(this.speech);
  }
  private translationEnded() {
    // Translation-first returns to this sentence; other modes advance once.
    if (this.mode === "translation-original")
      this.original(this.segments[this.index].start);
    else this.advance();
  }
  private advance() {
    // Original-bearing modes preserve inter-sentence gaps and final trailing audio.
    const previous = this.segments[this.index];
    this.index++;
    if (this.index >= this.segments.length) {
      if (
        this.mode !== "translation" &&
        previous &&
        previous.end < this.video.duration - 0.05
      )
        this.original(previous.end);
      else this.finish();
      return;
    }
    if (
      this.mode === "translation-original" &&
      previous &&
      previous.end < this.segments[this.index].start
    ) {
      this.gap = true;
      this.original(previous.end);
    } else if (
      this.mode === "translation" ||
      this.mode === "translation-original"
    )
      this.translated();
    else this.original(previous?.end ?? this.segments[this.index].start);
  }
  private finish() {
    this.stopBoth();
    this.playing = false;
    this.phase = "ended";
    this.index = Math.max(0, this.segments.length - 1);
    this.emit();
  }
  play() {
    // Resume the active channel without restarting the translated sentence.
    if (this.disposed || this.playing) return;
    if (this.phase === "paused") {
      this.phase = this.resumePhase;
      this.playing = true;
      if (this.phase === "translation") {
        const token = this.epoch;
        this.speech.onended = () => {
          if (token === this.epoch && this.playing) this.translationEnded();
        };
      }
      this.emit();
      void this.playMedia(
        this.phase === "translation" ? this.speech : this.video,
      );
      return;
    }
    if (this.phase === "ended") {
      this.index = 0;
      this.video.currentTime = 0;
    }
    if (this.mode === "original" || !this.segments.length) this.original();
    else if (this.mode === "original-translation") this.original();
    else if (
      this.mode === "translation-original" &&
      this.video.currentTime < this.segments[this.index].start
    ) {
      this.gap = true;
      this.original();
    } else this.translated();
  }
  pause() {
    if (!this.playing) {
      this.stopBoth();
      this.emit();
      return;
    }
    this.resumePhase =
      this.phase === "translation" ? "translation" : "original";
    this.stopBoth();
    this.playing = false;
    this.phase = "paused";
    this.emit();
  }
  toggle() {
    if (this.playing) this.pause();
    else this.play();
  }
  seek(time: number, autoplay = this.playing) {
    // Seeking cancels stale translated callbacks and synchronizes the row index.
    this.stopBoth();
    this.gap = false;
    this.playing = false;
    this.phase = "idle";
    this.video.currentTime = Math.max(
      0,
      Math.min(time, this.video.duration || time),
    );
    const index = this.segments.findIndex((segment) => segment.end > time);
    this.index = index < 0 ? Math.max(0, this.segments.length - 1) : index;
    if (autoplay) {
      if (this.mode === "translation" || this.mode === "translation-original")
        this.translated();
      else this.original();
    } else this.emit();
  }
  sentence(index: number, autoplay = true) {
    const i = Math.max(0, Math.min(index, this.segments.length - 1));
    if (this.segments[i]) this.seek(this.segments[i].start, autoplay);
  }
  skip(delta: number) {
    this.sentence(this.index + delta);
  }
  setMode(mode: Mode) {
    const playing = this.playing;
    this.mode = mode;
    this.seek(this.video.currentTime, playing);
  }
  tick() {
    // Called every animation frame: stop video at the source timestamp boundary.
    if (!this.playing) return;
    if (this.phase === "original" && this.mode !== "original") {
      const segment = this.segments[this.index];
      if (this.gap && segment && this.video.currentTime >= segment.start) {
        this.translated();
        return;
      }
      if (this.gap) {
        this.emit();
        return;
      }
      if (segment && this.video.currentTime >= segment.end) {
        this.video.pause();
        this.video.currentTime = segment.end;
        if (this.mode === "original-translation") this.translated();
        else this.advance();
        return;
      }
    } else if (this.mode === "original") {
      const i = this.segments.findIndex((s) => s.end > this.video.currentTime);
      if (i >= 0) this.index = i;
    }
    this.emit();
  }
  mediaEnded() {
    if (this.phase === "original") {
      if (this.mode === "original-translation" && this.segments[this.index])
        this.translated();
      else this.finish();
    }
  }
  settings(speed: number, volume: number, muted: boolean) {
    for (const media of [this.video, this.speech]) {
      media.playbackRate = speed;
      media.volume = volume;
      media.muted = muted;
    }
  }
  dispose() {
    this.disposed = true;
    this.playing = false;
    this.stopBoth();
  }
}
