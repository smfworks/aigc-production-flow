import { useEffect, useState } from "react";
import { api } from "./api.ts";
import type { AdapterHealth } from "./types.ts";

export function AdapterStrip({
  stillDefault,
  clipDefault,
  onError,
}: {
  stillDefault?: string;
  clipDefault?: string;
  onError: (err: unknown) => void;
}) {
  const [health, setHealth] = useState<AdapterHealth[]>([]);

  useEffect(() => {
    void api
      .adapterHealth()
      .then(setHealth)
      .catch(() => {
        /* meta can load before auth; strip stays empty */
      });
  }, [onError]);

  if (health.length === 0) return null;
  const liveUnhealthy = health.filter((row) => row.live && !row.ok);

  return (
    <div className="adapter-strip" aria-label="Adapter health">
      {health.map((row) => (
        <span
          key={row.id}
          className={`adapter-chip ${
            row.ok ? (row.not_live && row.id !== "stub" ? "is-muted" : "is-ok") : "is-bad"
          }`}
          title={row.detail}
        >
          {row.id}
          {row.ok
            ? row.not_live || !row.live
              ? row.id === "stub"
                ? " · ok"
                : " · not live"
              : " · live"
            : row.config_present
              ? " · down"
              : " · not live"}
          {row.lanes_configured ? <em className="adapter-badge">lanes</em> : null}
        </span>
      ))}
      <span className="hint">
        Defaults still={stillDefault || "stub"} · clip={clipDefault || "stub"}. Stub is the CI
        default. Unset ComfyUI lanes are <strong>not live</strong> and stay stub. A configured
        lane that cannot be reached is <strong>down</strong>. comfy-h3 window is measured 10.125s
        / 243f @ 24fps. Health is a dry-run, not a generate. Live adapters never skip hop-1 watch.
      </span>
      {liveUnhealthy.length ? (
        <span className="hint adapter-warn">
          Live adapter {liveUnhealthy.map((row) => row.id).join(", ")} is unhealthy. Enqueue is
          blocked for that slot until the hook is reachable, or use stub.
        </span>
      ) : null}
    </div>
  );
}
