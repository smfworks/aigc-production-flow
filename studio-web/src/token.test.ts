import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { getToken, setToken } from "./api.ts";

const TOKEN_KEY = "smf.aigc-studio.token";

function installStorage(): void {
  const store = new Map<string, string>();
  const storage = {
    getItem(key: string) {
      return store.has(key) ? (store.get(key) ?? null) : null;
    },
    setItem(key: string, value: string) {
      store.set(key, value);
    },
    removeItem(key: string) {
      store.delete(key);
    },
    clear() {
      store.clear();
    },
  };
  Object.defineProperty(globalThis, "localStorage", {
    value: storage,
    configurable: true,
    writable: true,
  });
}

describe("studio api token", () => {
  it("does not fall back to the retired default", () => {
    installStorage();
    localStorage.setItem(TOKEN_KEY, "local-dev-token");
    assert.equal(getToken(), "");
    assert.equal(localStorage.getItem(TOKEN_KEY), null);
  });

  it("keeps a token the operator saved", () => {
    installStorage();
    setToken("saved-secret");
    assert.equal(getToken(), "saved-secret");
  });
});
