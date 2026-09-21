import assert from "node:assert/strict";
import test from "node:test";
import { studioBaseUrl, studioImportUrl } from "./studio.ts";

test("studio handoff defaults to local studio-web with import hint", () => {
  assert.equal(studioBaseUrl(), "http://localhost:5174");
  assert.equal(studioImportUrl(), "http://localhost:5174/?import=1#/projects");
});
