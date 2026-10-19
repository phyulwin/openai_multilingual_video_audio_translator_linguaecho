// test-setup.ts — Shared DOM matchers and cleanup for isolated UI tests.
import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";
afterEach(() => cleanup());
