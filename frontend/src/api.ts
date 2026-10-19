// api.ts — Typed fetch helpers with consistent user-visible errors.
import type { Project } from "./types";
export async function api<T>(
  path: string,
  method = "GET",
  data?: unknown,
): Promise<T> {
  // Preserve server error messages while handling offline or non-JSON responses.
  const response = await fetch("/api" + path, {
    method,
    headers: data ? { "Content-Type": "application/json" } : {},
    body: data ? JSON.stringify(data) : undefined,
  });
  if (response.status === 204) return undefined as T;
  let payload;
  try {
    payload = await response.json();
  } catch {
    throw new Error("The server returned an invalid response.");
  }
  if (!response.ok)
    throw new Error(payload.error?.message || "Request failed.");
  return payload as T;
}
export function upload(
  file: File,
  progress: (value: number) => void,
  done: (project: Project) => void,
  fail: (message: string) => void,
) {
  // XHR provides real upload progress and cancellation for large media files.
  const xhr = new XMLHttpRequest();
  xhr.open("POST", "/api/projects");
  xhr.upload.onprogress = (event) => {
    if (event.lengthComputable)
      progress(Math.round((event.loaded / event.total) * 100));
  };
  xhr.onload = () => {
    try {
      const body = JSON.parse(xhr.responseText);
      if (xhr.status >= 400) fail(body.error?.message || "Upload failed");
      else done(body);
    } catch {
      fail("Invalid upload response");
    }
  };
  xhr.onerror = () =>
    fail("Upload failed; check your connection to the backend.");
  xhr.onabort = () => fail("Upload cancelled.");
  const data = new FormData();
  data.append("file", file);
  xhr.send(data);
  return xhr;
}
export const exportUrl = (
  project: Project,
  target: string,
  format: string,
  language: string,
) =>
  `/api/projects/${project.id}/export?target=${encodeURIComponent(target)}&format=${format}&language=${language}`;
