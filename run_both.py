#!/usr/bin/env python3
"""
Run fb_scraper.py and ig_scraper.py back-to-back from one command.

This is a thin orchestrator, not a third scraper: it shells out to
`python fb_scraper.py scrape ...` and `python ig_scraper.py scrape ...` in
turn (each is its own real browser session -- Playwright vs. Selenium --
so they are not run concurrently by default, to avoid two automated
browsers fighting for focus/resources on one machine) and prints a combined
summary. Each platform still writes its own JSONL + CSV under its own
subfolder of --out, exactly as running it standalone would.

Usage
-----
  # one-time, per platform, before this will do anything:
  python fb_scraper.py login
  python ig_scraper.py login

  # then, one query for both:
  python run_both.py --fb-url https://www.facebook.com/<page>/ \\
                      --ig-url https://www.instagram.com/<profile>/ \\
                      --days 7 --out output --headed

  # only one platform (omit the other's --*-url and it's skipped):
  python run_both.py --ig-url https://www.instagram.com/<profile>/ --days 7

Any flag understood by both scrapers' `scrape` subcommand (--since/--until
instead of --days, --limit, --max-comments, --no-comments, --chrome-path)
is accepted here and passed through unchanged to whichever platform runs.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
FB_SCRIPT = HERE / "fb_scraper.py"
IG_SCRIPT = HERE / "ig_scraper.py"
FB_SESSION = HERE / "fb_session"
IG_COOKIES = HERE / "ig_session" / "cookies.pkl"


def build_common_args(args: argparse.Namespace) -> list[str]:
    """The window + shared knobs, in the form each scraper's argparse expects."""
    out: list[str] = []
    if args.days:
        out += ["--days", str(args.days)]
    else:
        out += ["--since", args.since]
        if args.until:
            out += ["--until", args.until]
    if args.limit:
        out += ["--limit", str(args.limit)]
    if args.max_comments:
        out += ["--max-comments", str(args.max_comments)]
    if args.no_comments:
        out += ["--no-comments"]
    if args.headed:
        out += ["--headed"]
    if args.chrome_path:
        out += ["--chrome-path", args.chrome_path]
    return out


def run_one(label: str, cmd: list[str]) -> tuple[bool, float]:
    print(f"\n{'=' * 70}\n  {label}\n  $ {' '.join(cmd)}\n{'=' * 70}\n", flush=True)
    t0 = time.perf_counter()
    proc = subprocess.run(cmd)
    dt = time.perf_counter() - t0
    return proc.returncode == 0, dt


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fb-url", help="Facebook page/profile URL")
    ap.add_argument("--ig-url", help="Instagram profile URL")
    ap.add_argument("--days", type=int, help="look back N days (e.g. --days 7)")
    ap.add_argument("--since", help="start date, YYYY-MM-DD (alternative to --days)")
    ap.add_argument("--until", help="end date, YYYY-MM-DD (default: now)")
    ap.add_argument("--out", default="output", help="base output directory "
                    "(each platform gets its own <out>/facebook or <out>/instagram)")
    ap.add_argument("--headed", action="store_true", help="show the browser "
                    "(required for full FB comment depth)")
    ap.add_argument("--limit", type=int, help="cap number of posts per platform (testing)")
    ap.add_argument("--max-comments", type=int, help="cap comments scraped per post")
    ap.add_argument("--no-comments", action="store_true", help="posts only, no comment threads")
    ap.add_argument("--chrome-path", help="path to a Chrome/Chromium binary, for both")
    ap.add_argument("--fb-workers", type=int, default=4, help="FB concurrent post pages")
    args = ap.parse_args()

    if not args.fb_url and not args.ig_url:
        ap.error("give at least one of --fb-url / --ig-url")
    if not args.days and not args.since:
        ap.error("give either --days N or --since YYYY-MM-DD")

    out = Path(args.out)
    common = build_common_args(args)
    results: list[tuple[str, bool, float]] = []

    if args.fb_url:
        if not FB_SESSION.exists():
            print(f"\n  ! No Facebook session at {FB_SESSION} -- skipping Facebook.\n"
                  f"    Run:  python {FB_SCRIPT.name} login\n")
        else:
            cmd = [sys.executable, str(FB_SCRIPT), "scrape", "--url", args.fb_url,
                   "--out", str(out / "facebook"), "--workers", str(args.fb_workers), *common]
            ok, dt = run_one("Facebook", cmd)
            results.append(("Facebook", ok, dt))

    if args.ig_url:
        if not IG_COOKIES.exists():
            print(f"\n  ! No Instagram session at {IG_COOKIES} -- skipping Instagram.\n"
                  f"    Run:  python {IG_SCRIPT.name} login\n")
        else:
            cmd = [sys.executable, str(IG_SCRIPT), "scrape", "--url", args.ig_url,
                   "--out", str(out / "instagram"), *common]
            ok, dt = run_one("Instagram", cmd)
            results.append(("Instagram", ok, dt))

    if not results:
        sys.exit("\n  Nothing ran -- no session was found for either requested platform.\n")

    print(f"\n{'=' * 70}\n  summary\n{'=' * 70}")
    failed = False
    for label, ok, dt in results:
        mins, secs = divmod(dt, 60)
        status = "ok" if ok else "FAILED"
        if not ok:
            failed = True
        print(f"  {label:10s} {status:7s} {int(mins)}m {secs:.0f}s"
              f"  -> {out / label.lower()}/")
    print()
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
