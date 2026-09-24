"""HTTP client for the local Omarchy Grok Imagine app, plus a pure pack mirror.

Imagine listens on its own port (default :8010) with a bearer token. Studio does
not start that process. An empty ``STUDIO_IMAGINE_URL`` means the fast path is
not live. This module never calls Comfy and never invents an MP4.

Camera cards on an Imagine shot become Studio edit-list camera fields with this
table. Unlisted moves stay blank so the edit-list gate can fail honestly.

| Imagine ``camera.move`` | Studio ``cameraVerb`` |
|---|---|
| ``dolly_in`` | ``push`` |
| ``dolly_out`` | ``pull`` |
| ``orbit`` | ``arc`` |
| ``pan`` | ``pan`` |
| ``whip_pan`` | ``pan`` |
| ``tilt`` | ``tilt`` |
| ``handheld`` | ``shake`` |
| ``static`` | ``static`` |

| Imagine ``camera.scale`` | Studio ``cameraAmplitude`` |
|---|---|
| ``wide`` | ``wide`` |
| ``medium`` | ``medium`` |
| ``close`` | ``close`` |
| ``extreme_close`` | ``tight`` |

Imagine has no speed token. ``cameraSpeed`` stays empty. Studio does not invent one.

Beat roles become map energy (the pack gate's verse/chorus/bridge set):

| Imagine beat role | Studio ``energy`` |
|---|---|
| ``setup`` | ``verse`` |
| ``turn`` | ``bridge`` |
| ``climax`` | ``chorus`` |
| ``button`` | ``outro`` |

Map clocks are cumulative shot durations (``m:ss``) at the first shot of that beat.
"""

from __future__ import annotations

import time
from typing import Any

import httpx

from .blankpack import empty_pack, studio_meta
from .config import Settings, get_settings

IMAGINE_ADAPTER = "grok-imagine"
HEALTH_TIMEOUT_SECONDS = 2.0
HEALTH_CACHE_SECONDS = 10.0
PLAN_TIMEOUT_SECONDS = 120.0
DEFAULT_TIMEOUT_SECONDS = 60.0

CAMERA_MOVE_TO_VERB: dict[str, str] = {
    "dolly_in": "push",
    "dolly_out": "pull",
    "orbit": "arc",
    "pan": "pan",
    "whip_pan": "pan",
    "tilt": "tilt",
    "handheld": "shake",
    "static": "static",
}

CAMERA_SCALE_TO_AMPLITUDE: dict[str, str] = {
    "wide": "wide",
    "medium": "medium",
    "close": "close",
    "extreme_close": "tight",
}

BEAT_ROLE_TO_ENERGY: dict[str, str] = {
    "setup": "verse",
    "turn": "bridge",
    "climax": "chorus",
    "button": "outro",
}

_health_cache: dict[str, tuple[float, bool]] = {}
_transport_override: httpx.BaseTransport | None = None


class ImagineError(Exception):
    """Imagine returned an error, or the call could not be completed."""

    def __init__(self, message: str, status_code: int = 502):
        self.status_code = status_code
        super().__init__(message)


class ImagineNotConfigured(ImagineError):
    def __init__(self, message: str = "Imagine is not configured. Set STUDIO_IMAGINE_URL."):
        super().__init__(message, status_code=409)


def set_transport_for_tests(transport: httpx.BaseTransport | None) -> None:
    """Install an httpx transport. Tests use MockTransport so nothing leaves the process."""
    global _transport_override
    _transport_override = transport
    clear_health_cache()


def clear_health_cache() -> None:
    _health_cache.clear()


def imagine_url(settings: Settings | None = None) -> str:
    cfg = settings or get_settings()
    return (cfg.imagine_url or "").strip().rstrip("/")


def get_imagine_client(settings: Settings | None = None, *, timeout: float | None = None) -> ImagineClient:
    cfg = settings or get_settings()
    url = imagine_url(cfg)
    if not url:
        raise ImagineNotConfigured()
    return ImagineClient(
        url,
        (cfg.imagine_token or "local-dev-token").strip() or "local-dev-token",
        transport=_transport_override,
        timeout=timeout if timeout is not None else DEFAULT_TIMEOUT_SECONDS,
    )


def imagine_configured(settings: Settings | None = None) -> bool:
    """True only when GET {url}/api/health returns imagine_configured true.

    An empty URL is false and does not open a socket. Failures are false.
    A successful answer is cached briefly.
    """
    url = imagine_url(settings)
    if not url:
        return False
    now = time.monotonic()
    cached = _health_cache.get(url)
    if cached is not None and now - cached[0] < HEALTH_CACHE_SECONDS:
        return cached[1]
    ok = False
    try:
        body = get_imagine_client(settings, timeout=HEALTH_TIMEOUT_SECONDS).health()
        ok = bool(body.get("imagine_configured"))
    except Exception:
        ok = False
    _health_cache[url] = (now, ok)
    return ok


class ImagineClient:
    """Bearer-auth client for the Imagine pack API."""

    def __init__(
        self,
        base_url: str,
        token: str,
        *,
        transport: httpx.BaseTransport | None = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self._transport = transport
        self._timeout = timeout

    def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> httpx.Response:
        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            with httpx.Client(
                base_url=self.base_url,
                headers=headers,
                transport=self._transport,
                timeout=timeout if timeout is not None else self._timeout,
            ) as client:
                response = client.request(method, path, json=json_body)
        except httpx.HTTPError as exc:
            raise ImagineError(f"Imagine request failed: {exc.__class__.__name__}") from exc
        if response.status_code >= 400:
            raise ImagineError(
                _error_text(response),
                status_code=response.status_code if response.status_code < 500 else 502,
            )
        return response

    def health(self) -> dict[str, Any]:
        response = self._request("GET", "/api/health", timeout=HEALTH_TIMEOUT_SECONDS)
        body = _json_object(response)
        return body

    def plan(self, body: dict[str, Any]) -> dict[str, Any]:
        response = self._request(
            "POST",
            "/api/packs/plan",
            json_body=body,
            timeout=PLAN_TIMEOUT_SECONDS,
        )
        return _json_object(response)

    def create_pack(self, body: dict[str, Any]) -> dict[str, Any]:
        response = self._request("POST", "/api/packs", json_body=body)
        return _json_object(response)

    def run(self, pack_id: str) -> dict[str, Any]:
        response = self._request("POST", f"/api/packs/{pack_id}/run")
        return _json_object(response)

    def jobs(self, pack_id: str) -> dict[str, Any]:
        response = self._request("GET", f"/api/packs/{pack_id}/jobs")
        return _json_object(response)

    def download_episode(self, pack_id: str) -> bytes:
        response = self._request("GET", f"/api/packs/{pack_id}/episode")
        data = response.content or b""
        if not data:
            raise ImagineError("Imagine episode download was empty.", status_code=404)
        return data


def pack_body_for_create(plan: dict[str, Any]) -> dict[str, Any]:
    """Drop cast and music paths Imagine would reject.

    A plan may name cast before a file exists. Saving a pack requires those
    files under ``references/`` and ``music/``. This is not an upload.
    """
    body = dict(plan)
    cast = body.get("cast")
    if isinstance(cast, list):
        kept = []
        for item in cast:
            if not isinstance(item, dict):
                continue
            path = str(item.get("image_path") or "").strip()
            if path.startswith("references/"):
                kept.append(item)
        body["cast"] = kept
    music = str(body.get("music_path") or "").strip()
    if music and not music.startswith("music/"):
        body["music_path"] = ""
    return body


def studio_pack_from_imagine(plan: dict[str, Any]) -> dict[str, Any]:
    """Mirror an Imagine PackIn into a Studio pack.json. Does not call Imagine.

    Gates are whatever ``evaluate_gates`` says about this dict. Nothing here
    sets ``all_gates_green`` or stamps generate-ok.
    """
    title = _text(plan.get("title")) or "Imagine episode"
    pack = empty_pack(
        title,
        source="imagine-plan",
        note=(
            "Pack mirrored from an Imagine plan. Gates are evaluated as written. "
            "This mirror does not render, does not call Comfy, and does not invent an MP4."
        ),
    )
    pack["logLine"] = _text(plan.get("logline"))
    shots = [row for row in _list(plan.get("shots")) if isinstance(row, dict)]
    starts, total = _shot_clocks(shots)
    pack["durationTarget"] = f"{total}s" if total else ""
    pack["map"] = _map_rows(plan, shots, starts)
    pack["editList"] = _edit_rows(shots, starts)
    pack["look"]["styleLine"] = _style_line(plan.get("look_bible"))
    characters = _characters(plan.get("cast"))
    if characters:
        pack["characters"] = characters
    pack["studioMeta"] = studio_meta(
        source="imagine-plan",
        model="grok-imagine",
        model_ran=False,
        note=(
            "Mirrored from an Imagine plan. model_ran is false because this JSON is not a render. "
            "Gates stay whatever the pack actually satisfies. called_comfy is false."
        ),
    )
    pack["studioMeta"]["called_comfy"] = False
    pack["studioMeta"]["called_imagine"] = False
    pack["studioMeta"]["produced_mp4"] = False
    pack["studioMeta"]["generate_ready"] = False
    return pack


def _shot_clocks(shots: list[dict[str, Any]]) -> tuple[list[int], int]:
    starts: list[int] = []
    cursor = 0
    for shot in shots:
        starts.append(cursor)
        try:
            duration = int(shot.get("duration_sec") or 0)
        except (TypeError, ValueError):
            duration = 0
        cursor += max(0, duration)
    return starts, cursor


def _map_rows(
    plan: dict[str, Any],
    shots: list[dict[str, Any]],
    starts: list[int],
) -> list[dict[str, str]]:
    from .blankpack import _id

    beats = [row for row in _list(plan.get("beat_map")) if isinstance(row, dict)]
    if not beats:
        seen: list[str] = []
        for shot in shots:
            role = _text(shot.get("beat"))
            if role and role not in seen:
                seen.append(role)
        beats = [{"role": role, "summary": role} for role in seen]
    rows: list[dict[str, str]] = []
    for beat in beats:
        role = _text(beat.get("role")).lower()
        summary = _text(beat.get("summary")) or role
        clock = ""
        for shot, start in zip(shots, starts, strict=False):
            if _text(shot.get("beat")).lower() == role and role:
                clock = _clock(start)
                break
        rows.append(
            {
                "id": _id(),
                "clock": clock,
                "beat": summary,
                "energy": BEAT_ROLE_TO_ENERGY.get(role, ""),
            }
        )
    if not rows:
        rows.append({"id": _id(), "clock": "", "beat": "", "energy": ""})
    return rows


def _edit_rows(shots: list[dict[str, Any]], starts: list[int]) -> list[dict[str, str]]:
    from .blankpack import _id

    if not shots:
        return [
            {
                "id": _id(),
                "songT": "",
                "durS": "",
                "join": "",
                "take": "",
                "locationGrade": "",
                "cameraVerb": "",
                "cameraAmplitude": "",
                "cameraSpeed": "",
                "action": "",
                "hold": "",
                "notes": "",
                "entities": "",
            }
        ]
    rows: list[dict[str, str]] = []
    for index, (shot, start) in enumerate(zip(shots, starts, strict=False)):
        camera = shot.get("camera") if isinstance(shot.get("camera"), dict) else {}
        move = _text(camera.get("move")).lower()
        scale = _text(camera.get("scale")).lower()
        try:
            duration = int(shot.get("duration_sec") or 0)
        except (TypeError, ValueError):
            duration = 0
        notes = []
        if _text(shot.get("start_state")):
            notes.append(f"start: {_text(shot.get('start_state'))}")
        if _text(shot.get("end_state")):
            notes.append(f"end: {_text(shot.get('end_state'))}")
        if _text(camera.get("exit_frame")):
            notes.append(f"exit: {_text(camera.get('exit_frame'))}")
        rows.append(
            {
                "id": _id(),
                "songT": _clock(start),
                "durS": str(duration) if duration else "",
                "join": "cut" if index == 0 else "continue",
                "take": "A",
                "locationGrade": "",
                "cameraVerb": CAMERA_MOVE_TO_VERB.get(move, ""),
                "cameraAmplitude": CAMERA_SCALE_TO_AMPLITUDE.get(scale, ""),
                "cameraSpeed": "",
                "action": _text(shot.get("prompt_motion")),
                "hold": "no",
                "notes": " ".join(notes),
                "entities": "",
            }
        )
    return rows


def _style_line(bible: Any) -> str:
    if isinstance(bible, str):
        return bible.strip()
    if not isinstance(bible, dict):
        return ""
    lines = []
    for label in ("Cast", "Wardrobe", "Palette", "Lighting", "Camera"):
        value = _text(bible.get(label.lower()))
        if value:
            lines.append(f"{label}: {value}")
    return "\n".join(lines)


def _characters(cast: Any) -> list[dict[str, Any]]:
    from .blankpack import DEFAULT_CHARACTER_FORBIDDEN, DEFAULT_STILL_CANVAS, _id

    rows: list[dict[str, Any]] = []
    for item in _list(cast):
        if not isinstance(item, dict):
            continue
        name = _text(item.get("name"))
        if not name:
            continue
        rows.append(
            {
                "id": _id(),
                "name": name,
                "stillFile": "",
                "stillSource": "",
                "stillCanvas": DEFAULT_STILL_CANVAS,
                "speakerId": "none",
                "ageSex": "",
                "faceHairBeard": "",
                "body": "",
                "wardrobe": "",
                "footwear": "",
                "distinguishingMarks": _text(item.get("markers")),
                "eraForbiddenModern": "",
                "lockParagraph": "",
                "forbidden": DEFAULT_CHARACTER_FORBIDDEN,
                "motionNotes": "",
            }
        )
    return rows


def _clock(seconds: int) -> str:
    total = max(0, int(seconds))
    return f"{total // 60}:{total % 60:02d}"


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _json_object(response: httpx.Response) -> dict[str, Any]:
    try:
        body = response.json()
    except ValueError as exc:
        raise ImagineError("Imagine response was not JSON.") from exc
    if not isinstance(body, dict):
        raise ImagineError("Imagine response was not a JSON object.")
    return body


def _error_text(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return (response.text or f"Imagine HTTP {response.status_code}")[:500]
    if isinstance(payload, dict):
        detail = payload.get("detail")
        if isinstance(detail, str) and detail.strip():
            return detail.strip()[:500]
        if isinstance(detail, dict) and detail.get("message"):
            return str(detail["message"])[:500]
    return f"Imagine HTTP {response.status_code}"
