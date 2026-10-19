// playback.test.ts — Deterministic media ports verify ordering and cancellation.
import { describe, it, expect, vi } from "vitest";
import { PlaybackEngine, type MediaPort, type Snapshot } from "./playback";
import type { Mode } from "./types";
function setup(mode: Mode = "original-translation") {
  // Fake channels record concurrent state without needing real device audio.
  const media = (): MediaPort => ({
    currentTime: 0,
    duration: 8,
    paused: true,
    src: "",
    playbackRate: 1,
    volume: 1,
    muted: false,
    onended: null,
    play: vi.fn(async function (this: MediaPort) {
      this.paused = false;
    }),
    pause: vi.fn(function (this: MediaPort) {
      this.paused = true;
    }),
  });
  const video = media(),
    speech = media();
  let snapshot: Snapshot | undefined;
  const error = vi.fn();
  const engine = new PlaybackEngine(
    video,
    speech,
    [
      { id: 1, start: 0, end: 2, original_text: "One", favorite: false },
      { id: 2, start: 3, end: 5, original_text: "Two", favorite: false },
    ],
    mode,
    (id) => `/${id}.mp3`,
    (s) => (snapshot = s),
    error,
  );
  return { engine, video, speech, error, state: () => snapshot! };
}
describe("sentence playback", () => {
  it("preserves gaps in translation-first mode", () => {
    // After an original sentence, source gap audio precedes the next translation.
    const t = setup("translation-original");
    t.engine.play();
    t.speech.onended?.();
    t.video.currentTime = 2;
    t.engine.tick();
    expect(t.video.paused).toBe(false);
    expect(t.speech.paused).toBe(true);
    t.video.currentTime = 3;
    t.engine.tick();
    expect(t.video.paused).toBe(true);
    expect(t.speech.src).toBe("/2.mp3");
  });
  it("resumes a paused seek at the requested source time", () => {
    const t = setup();
    t.engine.seek(1.25, false);
    t.engine.play();
    expect(t.video.currentTime).toBe(1.25);
  });
  it("stops a stale asynchronous source when another channel owns playback", async () => {
    // Resolve an old play promise after switching into translated speech.
    const t = setup("original");
    let resolve: () => void = () => undefined;
    t.video.play = vi.fn(() => new Promise<void>((done) => {resolve = done;}));
    t.engine.play();
    t.engine.setMode("translation");
    t.video.paused = false;
    resolve();
    await Promise.resolve();
    expect(t.video.paused).toBe(true);
    expect(t.speech.paused).toBe(false);
  });
  it("pauses original during translation and resumes through the gap", () => {
    const t = setup();
    t.engine.play();
    expect(t.video.paused).toBe(false);
    t.video.currentTime = 2;
    t.engine.tick();
    expect(t.video.paused).toBe(true);
    expect(t.speech.paused).toBe(false);
    t.speech.onended?.();
    expect(t.speech.paused).toBe(true);
    expect(t.video.paused).toBe(false);
    expect(t.video.currentTime).toBe(2);
    expect(t.state().index).toBe(1);
  });
  it("plays translation before original", () => {
    const t = setup("translation-original");
    t.engine.play();
    expect(t.video.paused).toBe(true);
    expect(t.speech.paused).toBe(false);
    t.speech.onended?.();
    expect(t.video.paused).toBe(false);
    expect(t.speech.paused).toBe(true);
  });
  it("keeps original-only uninterrupted at sentence boundaries", () => {
    const t = setup("original");
    t.engine.play();
    t.video.currentTime = 2.5;
    t.engine.tick();
    expect(t.video.paused).toBe(false);
    expect(t.speech.play).not.toHaveBeenCalled();
  });
  it("translation-only holds video on each corresponding frame", () => {
    const t = setup("translation");
    t.engine.play();
    t.speech.onended?.();
    expect(t.video.paused).toBe(true);
    expect(t.video.currentTime).toBe(3);
    expect(t.speech.src).toBe("/2.mp3");
    t.speech.onended?.();
    expect(t.state().phase).toBe("ended");
  });
  it("pause and resume preserve translated audio time", () => {
    const t = setup("translation");
    t.engine.play();
    t.speech.currentTime = 1.2;
    t.engine.pause();
    expect(t.video.paused && t.speech.paused).toBe(true);
    t.engine.play();
    expect(t.speech.currentTime).toBe(1.2);
    expect(t.speech.paused).toBe(false);
  });
  it("seeking invalidates stale speech callbacks", () => {
    const t = setup("translation");
    t.engine.play();
    const stale = t.speech.onended;
    t.engine.seek(3);
    stale?.();
    expect(t.state().index).toBe(1);
    expect(t.speech.src).toBe("/2.mp3");
  });
  it("switching modes cancels the previous channel", () => {
    const t = setup("translation");
    t.engine.play();
    const stale = t.speech.onended;
    t.engine.setMode("original");
    stale?.();
    expect(t.speech.paused).toBe(true);
    expect(t.video.paused).toBe(false);
    expect(t.state().phase).toBe("original");
  });
  it("supports skipping, replay, rate, volume, and mute", () => {
    const t = setup();
    t.engine.skip(1);
    expect(t.state().index).toBe(1);
    t.engine.sentence(0);
    expect(t.video.currentTime).toBe(0);
    t.engine.settings(1.5, 0.4, true);
    expect(t.video.playbackRate).toBe(1.5);
    expect(t.speech.volume).toBe(0.4);
    expect(t.video.muted).toBe(true);
  });
  it("preserves trailing original content before completion", () => {
    const t = setup();
    t.engine.sentence(1);
    t.video.currentTime = 5;
    t.engine.tick();
    t.speech.onended?.();
    expect(t.video.currentTime).toBe(5);
    expect(t.video.paused).toBe(false);
    t.engine.mediaEnded();
    expect(t.state().phase).toBe("ended");
  });
  it("dispose prevents stale callbacks from resuming video", () => {
    const t = setup("translation");
    t.engine.play();
    const stale = t.speech.onended;
    t.engine.dispose();
    stale?.();
    expect(t.video.paused && t.speech.paused).toBe(true);
  });
  it("reports autoplay failures and stops both sources", async () => {
    const t = setup();
    t.video.play = vi.fn().mockRejectedValue(new Error("Autoplay blocked"));
    t.engine.play();
    await Promise.resolve();
    expect(t.error).toHaveBeenCalledWith("Autoplay blocked");
    expect(t.video.paused && t.speech.paused).toBe(true);
  });
});
