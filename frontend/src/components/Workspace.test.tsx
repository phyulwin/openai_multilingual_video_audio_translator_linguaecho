// Workspace.test.tsx — User-facing upload, language, transcript, and export behavior.
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import {
  Uploader,
  LanguageSelector,
  Transcript,
  ExportPanel,
} from "./Workspace";
import type { Project } from "../types";
const project: Project = {
  id: "test",
  name: "Example",
  filename: "example.mp4",
  duration: 3,
  kind: "video",
  source_language: "ja",
  segments: [
    { id: 1, start: 0, end: 2, original_text: "こんにちは。", favorite: false },
  ],
  translations: {
    en: {
      texts: { "1": "Hello." },
      voice: "coral",
      audio: { coral: { "1": "1.mp3" } },
    },
  },
  favorite: false,
  demo: false,
  status: "ready",
  progress: 100,
  message: "Ready",
  created_at: "",
  updated_at: "",
  media_url: "/media",
};
describe("workspace controls", () => {
  it("rejects unsupported uploads with useful feedback", () => {
    const error = vi.fn();
    render(<Uploader health={null} onProject={vi.fn()} onError={error} />);
    fireEvent.change(screen.getByLabelText("Upload media file"), {
      target: { files: [new File(["oops"], "bad.exe")] },
    });
    expect(error).toHaveBeenCalledWith(expect.stringContaining("Choose MP4"));
  });
  it("searches and selects broader supported languages", () => {
    const change = vi.fn();
    render(
      <LanguageSelector
        label="Target language"
        value="en"
        onChange={change}
        languages={[
          { code: "en", name: "English" },
          { code: "ar", name: "Arabic" },
          { code: "uk", name: "Ukrainian" },
        ]}
      />,
    );
    fireEvent.change(screen.getByLabelText("Search target language"), {
      target: { value: "Arabic" },
    });
    expect(screen.queryByText("Ukrainian (uk)")).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Target language"), {
      target: { value: "ar" },
    });
    expect(change).toHaveBeenCalledWith("ar");
  });
  it("renders Unicode, filters transcript, and replays a selected row", () => {
    const play = vi.fn();
    render(
      <Transcript
        project={project}
        target="en"
        active={0}
        onPlay={play}
        onEdit={vi.fn()}
        onFavorite={vi.fn()}
        notify={vi.fn()}
      />,
    );
    expect(screen.getByText("こんにちは。")).toBeVisible();
    fireEvent.click(screen.getByLabelText("Play sentence 1"));
    expect(play).toHaveBeenCalledWith(0);
    fireEvent.change(screen.getByLabelText("Search transcript"), {
      target: { value: "missing" },
    });
    expect(screen.queryByText("こんにちは。")).not.toBeInTheDocument();
  });
  it("copies both languages with the clipboard control", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText },
      configurable: true,
    });
    render(
      <Transcript
        project={project}
        target="en"
        active={0}
        onPlay={vi.fn()}
        onEdit={vi.fn()}
        onFavorite={vi.fn()}
        notify={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByLabelText("Copy sentence 1"));
    await waitFor(() =>
      expect(writeText).toHaveBeenCalledWith("こんにちは。\nHello."),
    );
  });
  it("saves corrections and toggles favorites", async () => {
    const edit = vi.fn().mockResolvedValue(undefined),
      favorite = vi.fn();
    render(
      <Transcript
        project={project}
        target="en"
        active={0}
        onPlay={vi.fn()}
        onEdit={edit}
        onFavorite={favorite}
        notify={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByLabelText("Favorite sentence 1"));
    expect(favorite).toHaveBeenCalledWith(project.segments[0]);
    fireEvent.click(screen.getByLabelText("Edit sentence 1"));
    fireEvent.change(screen.getByLabelText("Translation correction"), {
      target: { value: "Hi." },
    });
    fireEvent.click(screen.getByLabelText("Save correction"));
    await waitFor(() => expect(edit).toHaveBeenCalledWith(1, "Hi."));
  });
  it("exports real backend download URLs", () => {
    // Validate downloads against either the local API or the configured cloud origin.
    const configured = import.meta.env.VITE_API_BASE_URL || "";
    const backend = configured.endsWith("/") ? configured.slice(0, -1) : configured;
    render(<ExportPanel project={project} target="en" notify={vi.fn()} />);
    expect(
      screen.getByRole("link", { name: /Translated subtitles/ }),
    ).toHaveAttribute(
      "href",
      `${backend}/api/projects/test/export?target=en&format=srt&language=translated`,
    );
    expect(screen.getAllByRole("link")).toHaveLength(6);
  });
});
