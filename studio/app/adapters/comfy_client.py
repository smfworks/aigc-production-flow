"""ComfyUI HTTP client for AIGC Studio.

SMF Works reimplementation of the queue / prompt / history / view / free flow
used by local Qwen-Image and MiniMax H3 boxes. Behavior is adapted from the
MIT-licensed community tools noted in NOTICE and THIRD_PARTY.md. This module
is not a plugin host, and it does not speak to a public GPU API.

Lane URLs must be loopback or a private network. File results are paths on
disk. Image and video bytes are stored as media; they are not copied into
job receipts.
"""

from __future__ import annotations

import ipaddress
import json
from typing import Any
from urllib.parse import urlencode, urlparse

import httpx

from ..config import Settings
from ..local_only import is_cloud_generation_host

IMAGE_CLIENT_ID = "smf-aigc-studio"
VIDEO_CLIENT_ID = "smf-aigc-studio"
STILL_PREFIX = "smf_still"
CLIP_PREFIX = "smf_clip"

_PRIVATE_V4_EXTRA = ipaddress.ip_network("100.64.0.0/10")


class ComfyError(Exception):
    """A lane refused the call, or the graph failed. `busy` is a clean refusal."""

    def __init__(self, message: str, *, busy: bool = False):
        super().__init__(message)
        self.busy = busy


def parse_lane_list(raw: str | None) -> list[str]:
    text = (raw or "").strip()
    if not text:
        return []
    if text.startswith("["):
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            data = None
        if isinstance(data, list):
            return [str(item).strip().rstrip("/") for item in data if str(item).strip()]
    return [part.strip().rstrip("/") for part in text.split(",") if part.strip()]


def lanes_for_slot(settings: Settings, slot_id: str) -> list[str]:
    if slot_id == "comfy-qwen":
        return parse_lane_list(settings.comfy_still_lanes)
    if slot_id == "comfy-h3":
        return parse_lane_list(settings.comfy_clip_lanes)
    return []


def native_ready(settings: Settings, slot_id: str) -> bool:
    return bool(lanes_for_slot(settings, slot_id))


def allow_hosts(settings: Settings) -> set[str]:
    hosts = {"localhost"}
    for item in (settings.comfy_allow_hosts or "").split(","):
        name = item.strip().lower()
        if name:
            hosts.add(name)
    return hosts


def validate_lane(url: str, settings: Settings) -> tuple[bool, str]:
    """Accept loopback, private, link-local, and Tailscale CGNAT. Refuse public hosts."""
    raw = (url or "").strip()
    if not raw:
        return False, "ComfyUI lane URL is empty."
    parsed = urlparse(raw)
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in {"http", "https"} or not host:
        return False, f"ComfyUI lane must be http(s) with a host: {raw}"
    if is_cloud_generation_host(host):
        return False, (
            f"ComfyUI lane host {host} is a cloud generation API. "
            "Studio stays on local inference."
        )
    if host in allow_hosts(settings):
        return True, ""
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False, (
            f"ComfyUI lane host {host} is not a private address. "
            "Use 127.0.0.1 or a private network, or list a trusted name in STUDIO_COMFY_ALLOW_HOSTS."
        )
    if ip.is_loopback or ip.is_link_local or ip.is_private:
        return True, ""
    if ip.version == 4 and ip in _PRIVATE_V4_EXTRA:
        return True, ""
    return False, (
        f"ComfyUI lane {host} is not on loopback or a private network. "
        "Studio will not send prompts to a public host."
    )


def assert_lanes(lanes: list[str], settings: Settings) -> None:
    if not lanes:
        raise ComfyError("No ComfyUI lanes are configured.")
    errors = [err for lane in lanes for ok, err in [validate_lane(lane, settings)] if not ok]
    if errors:
        raise ComfyError(errors[0])


def comfy_out_dir(settings: Settings):
    from pathlib import Path

    raw = (settings.comfy_out_dir or "").strip()
    path = Path(raw).expanduser() if raw else settings.media_path / "comfy"
    path.mkdir(parents=True, exist_ok=True)
    return path.resolve()


def first_images_output(outputs: Any) -> dict[str, Any] | None:
    """Finished Comfy jobs report files under `images`, including video saves."""
    if not isinstance(outputs, dict):
        return None
    for node in outputs.values():
        if not isinstance(node, dict):
            continue
        images = node.get("images")
        if isinstance(images, list) and images:
            first = images[0]
            if isinstance(first, dict) and first.get("filename"):
                return first
    return None


class ComfyClient:
    def __init__(self, settings: Settings, *, client: httpx.Client | None = None):
        self.settings = settings
        self._client = client

    def _timeout(self, seconds: float | None = None) -> float:
        value = float(seconds if seconds is not None else self.settings.comfy_request_timeout_seconds or 30)
        return max(0.2, value)

    def _owned_client(self) -> tuple[httpx.Client, bool]:
        if self._client is not None:
            return self._client, False
        return httpx.Client(timeout=self._timeout(), follow_redirects=False), True

    def request_json(
        self,
        method: str,
        url: str,
        *,
        body: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> Any:
        client, owned = self._owned_client()
        try:
            try:
                response = client.request(
                    method,
                    url,
                    json=body,
                    timeout=self._timeout(timeout),
                    follow_redirects=False,
                )
            except httpx.TimeoutException as exc:
                raise ComfyError(f"ComfyUI request timed out: {method} {url}") from exc
            except httpx.ConnectError as exc:
                raise ComfyError(f"ComfyUI lane unreachable: {url} (connection refused)") from exc
            except httpx.HTTPError as exc:
                raise ComfyError(f"ComfyUI request failed: {method} {url}: {exc}") from exc
            if response.status_code >= 400:
                detail = f"HTTP {response.status_code}"
                try:
                    payload = response.json()
                except json.JSONDecodeError:
                    payload = None
                if isinstance(payload, dict) and payload.get("error"):
                    err = payload["error"]
                    detail = err if isinstance(err, str) else json.dumps(err)[:500]
                raise ComfyError(f"ComfyUI {method} {url} failed: {detail}")
            if not response.content:
                return {}
            try:
                return response.json()
            except json.JSONDecodeError as exc:
                raise ComfyError(f"ComfyUI {method} {url} returned non-JSON.") from exc
        finally:
            if owned:
                client.close()

    def request_bytes(self, url: str, *, timeout: float | None = None) -> bytes:
        client, owned = self._owned_client()
        try:
            try:
                response = client.get(url, timeout=self._timeout(timeout), follow_redirects=False)
            except httpx.TimeoutException as exc:
                raise ComfyError(f"ComfyUI request timed out: GET {url}") from exc
            except httpx.ConnectError as exc:
                raise ComfyError(f"ComfyUI lane unreachable: {url} (connection refused)") from exc
            except httpx.HTTPError as exc:
                raise ComfyError(f"ComfyUI request failed: GET {url}: {exc}") from exc
            if response.status_code >= 400:
                raise ComfyError(f"ComfyUI /view failed: HTTP {response.status_code}")
            return bytes(response.content)
        finally:
            if owned:
                client.close()

    def lane_state(self, lane: str) -> str:
        """`free`, `busy`, or `down`. Unreachable counts as down, not as a silent queue."""
        try:
            payload = self.request_json("GET", f"{lane}/queue", timeout=min(8.0, self._timeout()))
        except ComfyError:
            return "down"
        if not isinstance(payload, dict):
            return "down"
        running = payload.get("queue_running") or []
        pending = payload.get("queue_pending") or []
        if not isinstance(running, list):
            running = []
        if not isinstance(pending, list):
            pending = []
        if len(running) + len(pending) > 0:
            return "busy"
        return "free"

    def pick_lane(self, lanes: list[str]) -> str:
        assert_lanes(lanes, self.settings)
        saw_busy = False
        saw_down = False
        for lane in lanes:
            state = self.lane_state(lane)
            if state == "free":
                return lane
            if state == "busy":
                saw_busy = True
            else:
                saw_down = True
        joined = ", ".join(lanes)
        if saw_busy:
            raise ComfyError(
                f"All ComfyUI lanes ({joined}) are busy. "
                "Refusing to queue behind a long render.",
                busy=True,
            )
        if saw_down:
            raise ComfyError(
                f"All ComfyUI lanes ({joined}) are unreachable. "
                "Refusing to queue a generate.",
                busy=True,
            )
        raise ComfyError(f"No free ComfyUI lane in ({joined}).", busy=True)

    def submit_prompt(self, lane: str, graph: dict[str, Any], client_id: str) -> str:
        payload = self.request_json(
            "POST",
            f"{lane}/prompt",
            body={"prompt": graph, "client_id": client_id},
        )
        if not isinstance(payload, dict) or not payload.get("prompt_id"):
            raise ComfyError("ComfyUI accepted the prompt but returned no prompt_id.")
        return str(payload["prompt_id"])

    def history_entry(self, lane: str, prompt_id: str) -> dict[str, Any] | None:
        try:
            payload = self.request_json(
                "GET",
                f"{lane}/history/{prompt_id}",
                timeout=min(15.0, self._timeout()),
            )
        except ComfyError:
            return None
        if not isinstance(payload, dict):
            return None
        entry = payload.get(prompt_id)
        if isinstance(entry, dict):
            return entry
        if "outputs" in payload or "status" in payload:
            return payload
        return None

    def output_file(self, entry: dict[str, Any] | None, prompt_id: str) -> dict[str, Any] | None:
        """Return the first `images` file, or None while the job is still running.

        A `video` key alone is not completion. Polling that key hangs while the
        file is already listed under `images`.
        """
        if not entry:
            return None
        status = entry.get("status") if isinstance(entry.get("status"), dict) else {}
        if status.get("status_str") == "error":
            raise ComfyError(f"ComfyUI job {prompt_id} failed (status error).")
        outputs = entry.get("outputs")
        if not isinstance(outputs, dict) or not outputs:
            return None
        image = first_images_output(outputs)
        if image:
            return image
        completed = bool(status.get("completed")) or status.get("status_str") == "success"
        if completed:
            raise ComfyError(
                f"ComfyUI job {prompt_id} finished but reported no 'images' outputs."
            )
        return None

    def download_output(self, lane: str, output: dict[str, Any]) -> bytes:
        query = urlencode(
            {
                "filename": str(output.get("filename") or ""),
                "subfolder": str(output.get("subfolder") or ""),
                "type": str(output.get("type") or "output"),
            }
        )
        return self.request_bytes(f"{lane}/view?{query}", timeout=max(30.0, self._timeout()))

    def free_memory(self, lane: str) -> bool:
        try:
            self.request_json(
                "POST",
                f"{lane}/free",
                body={"unload_models": True, "free_memory": True},
                timeout=min(20.0, max(5.0, self._timeout())),
            )
        except ComfyError:
            return False
        return True


def probe_lane(lane: str, timeout: float) -> tuple[bool, str]:
    try:
        response = httpx.get(f"{lane}/queue", timeout=timeout, follow_redirects=False)
    except Exception as exc:  # noqa: BLE001 — health is advisory
        return False, f"{lane} unreachable: {exc}"
    if response.status_code >= 500:
        return False, f"{lane} HTTP {response.status_code}"
    return True, f"{lane} reachable (HTTP {response.status_code})"
