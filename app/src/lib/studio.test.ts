import assert from "node:assert/strict";
import test from "node:test";
import {
  handoffFailureMessage,
  studioApiUrl,
  studioBaseUrl,
  studioHandoffUrl,
  studioImportUrl,
} from "./studio.ts";

test("studio handoff defaults to local studio-web with import hint", () => {
  assert.equal(studioBaseUrl(), "http://localhost:5174");
  assert.equal(studioImportUrl(), "http://localhost:5174/?import=1#/projects");
});

test("studio API URL defaults to local FastAPI for Vite studio-web", () => {
  assert.equal(studioApiUrl(), "http://localhost:8000");
});

test("handoff URL carries the staged zip id", () => {
  assert.equal(
    studioHandoffUrl("abc-123"),
    "http://localhost:5174/?handoff=abc-123#/projects",
  );
});

test("failure copy never claims auto-generate", () => {
  for (const kind of ["auth", "studio-down", "none"] as const) {
    const text = handoffFailureMessage(kind);
    assert.match(text, /never auto-generate/i);
    assert.doesNotMatch(text, /auto generate(?!-)/i);
  }
});
