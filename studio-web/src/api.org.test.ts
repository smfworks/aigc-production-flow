import assert from "node:assert/strict";
import { afterEach, beforeEach, describe, it } from "node:test";
import {
  api,
  getOrgId,
  noticeForMissingOrg,
  onStaleOrgCleared,
  resetStaleOrgRecoveryForTests,
  setOrgId,
  STALE_ORG_NOTICE,
  withStaleOrgRetry,
} from "./api.ts";

const ORG_KEY = "smf.aigc-studio.org";

function installStorage(): Map<string, string> {
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
  return store;
}

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

function orgHeader(init?: RequestInit): string | null {
  return new Headers(init?.headers).get("X-Org-Id");
}

const originalFetch = globalThis.fetch;

describe("stale saved organization", { concurrency: false }, () => {
  beforeEach(() => {
    resetStaleOrgRecoveryForTests();
    installStorage();
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
    resetStaleOrgRecoveryForTests();
  });

  it("does not treat an organization miss as recovered before a clear", () => {
    assert.equal(noticeForMissingOrg(new Error("Organization not found.")), null);
  });

  it("clears smf.aigc-studio.org and retries /api/me once without the header", async () => {
    const store = installStorage();
    setOrgId("stale-org");
    assert.equal(store.get(ORG_KEY), "stale-org");
    const seen: Array<string | null> = [];
    const methods: string[] = [];
    globalThis.fetch = async (input, init) => {
      methods.push(init?.method || "GET");
      const org = orgHeader(init);
      seen.push(org);
      if (org) return jsonResponse(404, { detail: "Organization not found." });
      assert.equal(String(input), "/api/me");
      return jsonResponse(200, {
        name: "local-dev",
        role: "producer",
        org_id: "org-real",
        org_name: "Local",
        permissions: ["mutate"],
        orgs: [],
        multi_org: false,
      });
    };
    const notices: string[] = [];
    const stop = onStaleOrgCleared(() => notices.push(STALE_ORG_NOTICE));
    try {
      const user = await api.me();
      assert.equal(user.org_id, "org-real");
      assert.deepEqual(user.permissions, ["mutate"]);
      assert.equal(getOrgId(), "");
      assert.equal(store.has(ORG_KEY), false);
      assert.deepEqual(seen, ["stale-org", null]);
      assert.deepEqual(methods, ["GET", "GET"]);
      assert.deepEqual(notices, [STALE_ORG_NOTICE]);
      assert.equal(noticeForMissingOrg(new Error("Organization not found.")), STALE_ORG_NOTICE);
    } finally {
      stop();
    }
  });

  it("retries /api/orgs once and keeps an empty list from the server", async () => {
    setOrgId("gone-org");
    const seen: Array<string | null> = [];
    globalThis.fetch = async (input, init) => {
      assert.equal(init?.method || "GET", "GET");
      assert.equal(String(input), "/api/orgs");
      const org = orgHeader(init);
      seen.push(org);
      if (org) return jsonResponse(404, { detail: "Organization not found." });
      return jsonResponse(200, []);
    };
    const orgs = await api.orgs();
    assert.deepEqual(orgs, []);
    assert.equal(getOrgId(), "");
    assert.deepEqual(seen, ["gone-org", null]);
  });

  it("retries me and orgs together when both requests carried the stale id", async () => {
    setOrgId("stale-org");
    const seen: string[] = [];
    globalThis.fetch = async (input, init) => {
      const org = orgHeader(init) || "";
      seen.push(`${String(input)}:${org}`);
      if (org) return jsonResponse(404, { detail: "Organization not found." });
      if (String(input).endsWith("/api/me")) {
        return jsonResponse(200, {
          name: "local-dev",
          org_id: "org-real",
          permissions: ["mutate"],
        });
      }
      return jsonResponse(200, [{ id: "org-real", name: "Local", is_default: true }]);
    };
    const [user, orgs] = await Promise.all([api.me(), api.orgs()]);
    assert.equal(user.org_id, "org-real");
    assert.equal(orgs[0]?.id, "org-real");
    assert.equal(getOrgId(), "");
    assert.equal(seen.filter((row) => row.endsWith(":stale-org")).length, 2);
    assert.equal(seen.filter((row) => row.endsWith(":")).length, 2);
  });

  it("stops after one retry when the organization is still missing", async () => {
    setOrgId("stale-org");
    let calls = 0;
    globalThis.fetch = async (_input, init) => {
      calls += 1;
      const org = orgHeader(init);
      if (calls === 1) assert.equal(org, "stale-org");
      else assert.equal(org, null);
      return jsonResponse(404, { detail: "Organization not found." });
    };
    await assert.rejects(() => api.me(), /Organization not found/);
    assert.equal(calls, 2);
    assert.equal(getOrgId(), "");
  });

  it("leaves the saved org in place for other failures", async () => {
    setOrgId("keep-me");
    let calls = 0;
    globalThis.fetch = async () => {
      calls += 1;
      return jsonResponse(500, { detail: "Database locked." });
    };
    await assert.rejects(() => api.orgs(), /Database locked/);
    assert.equal(calls, 1);
    assert.equal(getOrgId(), "keep-me");
    assert.equal(noticeForMissingOrg(new Error("Database locked.")), null);
  });

  it("does not retry when no organization id is saved", async () => {
    let calls = 0;
    let cleared = false;
    await assert.rejects(
      () =>
        withStaleOrgRetry(
          async () => {
            calls += 1;
            throw new Error("Organization not found.");
          },
          {
            getOrgId: () => "  ",
            setOrgId: () => {
              cleared = true;
            },
          },
        ),
      /Organization not found/,
    );
    assert.equal(calls, 1);
    assert.equal(cleared, false);
  });

  it("does not wipe a newer org id saved while the stale call was failing", async () => {
    let stored = "stale-org";
    const result = await withStaleOrgRetry(
      async () => {
        if (stored === "stale-org") {
          stored = "org-real";
          throw new Error("Organization not found.");
        }
        return stored;
      },
      {
        getOrgId: () => stored,
        setOrgId: (id) => {
          stored = id;
        },
      },
    );
    assert.equal(result, "org-real");
    assert.equal(stored, "org-real");
  });

  it("removes the saved organization key when setOrgId is cleared", () => {
    const store = installStorage();
    setOrgId("stale-org");
    assert.equal(store.get(ORG_KEY), "stale-org");
    setOrgId("");
    assert.equal(store.has(ORG_KEY), false);
    assert.equal(getOrgId(), "");
  });
});
