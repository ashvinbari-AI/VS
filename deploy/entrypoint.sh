#!/bin/sh
set -e
cd /app

case "$1" in
  serve)
    # Virtual display for headed (non-headless) scrapes, unless a real
    # display was passed in (see deploy/login.sh).
    if [ "$DISPLAY" = ":99" ]; then
      rm -f /tmp/.X99-lock
      Xvfb :99 -screen 0 1920x1080x24 -nolisten tcp >/dev/null 2>&1 &
    fi
    if [ -z "$ACCESS_TOKEN" ]; then
      echo "WARNING: ACCESS_TOKEN is not set -- the app is open to anyone." >&2
    fi
    cd /app/backend
    exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-4004}" \
         --proxy-headers --forwarded-allow-ips='*'
    ;;
  login-fb)
    exec python fb_scraper.py login
    ;;
  login-ig)
    exec python ig_scraper.py login
    ;;
  *)
    exec "$@"
    ;;
esac
