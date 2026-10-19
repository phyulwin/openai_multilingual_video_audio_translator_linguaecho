// types.ts — Shared REST response and playback contracts.
export interface Segment {
  id: number;
  start: number;
  end: number;
  original_text: string;
  favorite: boolean;
}
export interface Translation {
  texts: Record<string, string>;
  audio: Record<string, Record<string, string>>;
  voice: string;
}
export interface Project {
  id: string;
  name: string;
  filename: string;
  duration: number;
  kind: "audio" | "video";
  source_language: string;
  segments: Segment[];
  translations: Record<string, Translation>;
  favorite: boolean;
  demo: boolean;
  status: string;
  progress: number;
  message: string;
  created_at: string;
  updated_at: string;
  media_url: string;
}
export interface Health {
  ai_configured: boolean;
  ffmpeg: boolean;
  ffprobe: boolean;
  max_upload_mb: number;
  languages: { code: string; name: string }[];
  voices: string[];
  default_voice: string;
}
export type Mode =
  | "original-translation"
  | "translation-original"
  | "translation"
  | "original";
export type Phase = "idle" | "original" | "translation" | "paused" | "ended";
