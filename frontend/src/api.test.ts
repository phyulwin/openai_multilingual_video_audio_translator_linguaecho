// api.test.ts — Cross-origin API, scoped media links, and credential handling.
import { afterEach, expect, test, vi } from "vitest";

afterEach(() => {
  // Restore environment and browser state between security-sensitive checks.
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  vi.resetModules();
  sessionStorage.clear();
});

test("Cloud Run API uses a bearer header and clears rejected credentials", async () => {
  // Account credentials never enter query strings or public build variables.
  vi.stubEnv("VITE_API_BASE_URL", "https://service.run.app");
  sessionStorage.setItem("linguaecho-access", "individual-secret");
  const fetcher = vi.fn().mockResolvedValue({ status: 401, ok: false, json: async () => ({ error: { message: "Rejected" } }) });
  vi.stubGlobal("fetch", fetcher);
  const { api } = await import("./api");
  await expect(api("/projects")).rejects.toThrow("Rejected");
  expect(fetcher).toHaveBeenCalledWith("https://service.run.app/api/projects", expect.objectContaining({ headers: { Authorization: "Bearer individual-secret" } }));
  expect(sessionStorage.getItem("linguaecho-access")).toBeNull();
});

test("media and export URLs use scoped tickets and the backend origin", async () => {
  // Preserve query parameters used by bilingual audio selection and downloads.
  vi.stubEnv("VITE_API_BASE_URL", "https://service.run.app/");
  const { mediaUrl, exportUrl } = await import("./api");
  const project = { id: "one", media_ticket: "scoped.ticket" } as import("./types").Project;
  expect(mediaUrl(project, "/api/projects/one/media")).toBe("https://service.run.app/api/projects/one/media?ticket=scoped.ticket");
  expect(exportUrl(project, "ja", "txt", "bilingual")).toContain("&ticket=scoped.ticket");
});
