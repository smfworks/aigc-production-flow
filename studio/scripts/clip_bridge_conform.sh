#!/bin/sh
# CLIP_BRIDGE conform helpers (docs/CLIP_BRIDGE.md §12).
# Extract the rendered last frame, drop the held tail frame, hard-cut concat.
# Extract and stitch stay on ffmpeg. They are not Comfy nodes.
# A missing video exits without writing a stand-in frame or MP4.
set -eu

usage() {
  echo "usage: clip_bridge_conform.sh extract SRC.mp4 DEST.png" >&2
  echo "       clip_bridge_conform.sh trim SRC.mp4 DEST.mp4" >&2
  echo "       clip_bridge_conform.sh concat LIST.txt DEST.mp4" >&2
  exit 1
}

cmd=${1:-}
case "$cmd" in
  extract)
    src=${2:-}
    dest=${3:-}
    [ -n "$src" ] && [ -n "$dest" ] || usage
    if [ ! -f "$src" ]; then
      echo "Awaiting extract. No rendered clip at $src. No frame was invented." >&2
      exit 2
    fi
    command -v ffmpeg >/dev/null 2>&1 || {
      echo "ffmpeg is not on PATH. Awaiting extract." >&2
      exit 3
    }
    ffmpeg -y -sseof -0.05 -i "$src" -frames:v 1 -update 1 "$dest"
    ;;
  trim)
    src=${2:-}
    dest=${3:-}
    [ -n "$src" ] && [ -n "$dest" ] || usage
    if [ ! -f "$src" ]; then
      echo "Awaiting trim. No rendered clip at $src. No MP4 was invented." >&2
      exit 2
    fi
    command -v ffmpeg >/dev/null 2>&1 || {
      echo "ffmpeg is not on PATH. Awaiting trim." >&2
      exit 3
    }
    ffmpeg -y -i "$src" -vf "trim=end_frame=239" -an "$dest"
    ;;
  concat)
    list=${2:-}
    dest=${3:-}
    [ -n "$list" ] && [ -n "$dest" ] || usage
    if [ ! -f "$list" ]; then
      echo "Awaiting concat. No concat list at $list. No MP4 was invented." >&2
      exit 2
    fi
    command -v ffmpeg >/dev/null 2>&1 || {
      echo "ffmpeg is not on PATH. Awaiting concat." >&2
      exit 3
    }
    ffmpeg -y -f concat -safe 0 -i "$list" -c copy "$dest"
    ;;
  *)
    usage
    ;;
esac
