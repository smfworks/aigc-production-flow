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
          className={`adapter-chip ${row.ok ? "is-ok" : "is-bad"}`}
          title={row.detail}
        >
          {row.id}
          {row.ok ? " · ok" : row.config_present ? " · down" : " · unset"}
        </span>
      ))}
      <span className="hint">
        Defaults still={stillDefault || "stub"} · clip={clipDefault || "stub"}. Stub is the CI
        default. Unset live hooks stay stub — health is a dry-run, not a generate.
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
