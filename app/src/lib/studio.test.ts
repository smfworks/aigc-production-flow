import assert from "node:assert/strict";
import test from "node:test";
import {
  handoffFailureMessage,
  isLoopbackStudioHost,
  studioApiUrl,
  studioBaseUrl,
  studioHandoffUrl,
  studioImportUrl,
  studioToken,
} from "./studio.ts";

test("studio handoff defaults to local studio-web with import hint", () => {
  assert.equal(studioBaseUrl(), "http://localhost:5174");
  assert.equal(studioImportUrl(), "http://localhost:5174/?import=1#/projects");
});

test("studio API URL defaults to local FastAPI for Vite studio-web", () => {
  assert.equal(studioApiUrl(), "http://localhost:8000");
});

test("studio token does not fall back to the retired default", () => {
  assert.equal(studioToken(), "");
  assert.notEqual(studioToken(), "local-dev-token");
});

test("IPv6 loopback uses the bracketed URL hostname", () => {
  assert.equal(new URL("http://[::1]:8000").hostname, "[::1]");
  assert.equal(isLoopbackStudioHost("http://[::1]:8000"), true);
  assert.equal(isLoopbackStudioHost("http://127.0.0.1:8000"), true);
  assert.equal(isLoopbackStudioHost("http://localhost:8000"), true);
  assert.equal(isLoopbackStudioHost("http://10.0.0.5:8000"), false);
  assert.equal(isLoopbackStudioHost("http://::1:8000"), false);
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
