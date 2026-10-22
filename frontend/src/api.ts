// api.ts — Typed fetch helpers with consistent user-visible errors.
import type { Project } from "./types";
const configuredBackend = import.meta.env.VITE_API_BASE_URL || "";
const backend = configuredBackend.endsWith("/") ? configuredBackend.slice(0, -1) : configuredBackend;
// Use a per-tab credential, never a bundled secret or a URL account token.
function authorization(): Record<string, string> {
  if (!backend) return {};
  let token = sessionStorage.getItem("linguaecho-access");
  if (!token) {
    token = window.prompt("Enter your individual LinguaEcho access token (provided by the operator).");
    if (token) sessionStorage.setItem("linguaecho-access", token);
  }
  return token ? { Authorization: `Bearer ${token}` } : {};
}
// Media elements cannot send Authorization; use a short-lived project-only ticket.
export function mediaUrl(project: Project, path: string): string {
  const ticket = project.media_ticket;
  return backend + path + (ticket ? `${path.includes("?") ? "&" : "?"}ticket=${encodeURIComponent(ticket)}` : "");
}
export async function api<T>(
  path: string,
  method = "GET",
  data?: unknown,
): Promise<T> {
  // Preserve server error messages while handling offline or non-JSON responses.
  const response = await fetch(backend + "/api" + path, {
    method,
    headers: { ...(path === "/health" ? {} : authorization()), ...(data ? { "Content-Type": "application/json" } : {}) },
    referrerPolicy: "no-referrer",
    body: data ? JSON.stringify(data) : undefined,
  });
  if (response.status === 401) sessionStorage.removeItem("linguaecho-access");
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
  xhr.open("POST", backend + "/api/projects");
  for (const [name, value] of Object.entries(authorization())) xhr.setRequestHeader(name, value);
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
  mediaUrl(project, `/api/projects/${project.id}/export?target=${encodeURIComponent(target)}&format=${format}&language=${language}`);
