#!/usr/bin/env bash
# One-time (or when a session expires) social login, run on THIS machine.
# Opens the container's Chromium on your desktop so you can log in by hand;
# the session is saved into ./fb_session or ./ig_session, which the running
# app container also mounts.
#
#   ./deploy/login.sh fb     # Facebook
#   ./deploy/login.sh ig     # Instagram
set -euo pipefail
cd "$(dirname "$0")/.."

case "${1:-}" in
  fb) cmd=login-fb ;;
  ig) cmd=login-ig ;;
  *) echo "usage: $0 fb|ig"; exit 1 ;;
esac

: "${DISPLAY:?No DISPLAY -- run this from the desktop session of this machine}"
xhost +SI:localuser:"$(id -un)" >/dev/null
trap 'xhost -SI:localuser:"$(id -un)" >/dev/null' EXIT

docker compose run --rm --no-deps \
  -e DISPLAY="$DISPLAY" \
  -v /tmp/.X11-unix:/tmp/.X11-unix \
  vs-app "$cmd"
