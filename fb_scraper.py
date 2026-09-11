#!/usr/bin/env python3
"""
Async Facebook page/profile scraper -- Phase 1 of the Citizen Pain-Point pipeline.

Collects posts (caption, media, reaction breakdown, comment/share counts) and
their full comment threads within a time window, and writes them as the four
collections defined in scrape_schema.md: posts / comments / users / scrape_runs.
Storage lives in schema_store.py (JSONL + CSV, and MongoDB when asked).

No labelling happens here. sentiment, category, district and the rest are Phase 2.

Usage
-----
  # 1. one-time: log in by hand, session is saved to ./fb_session/
  python pipeline/vendor/fb_scraper.py login

  # 2. scrape -- --headed is required for full comment depth
  python pipeline/vendor/fb_scraper.py scrape \
        --url https://www.facebook.com/devendra.fadnavis/ \
        --days 2 --headed --out data/raw/
  python pipeline/vendor/fb_scraper.py scrape \
        --url https://www.facebook.com/devendra.fadnavis/ \
        --since 2026-07-19 --until 2026-07-21 --workers 3 --headed \
        --mongo-uri mongodb://localhost:27017

Two things bite hardest on this target, and both are handled below:
  * Video and reel permalinks bounce to Facebook's Watch player, which carries no
    post text, timestamp or comments -- see scrape_url_for().
  * "Most relevant" ordering hides much of the thread; comments come from a replay
    of Facebook's own paginated GraphQL query -- see harvest_comments_graphql().

Facebook's DOM is obfuscated and changes often. Every selector this script depends
on lives in the SELECTORS / TEXT_PATTERNS blocks below -- when something silently
returns empty, that's the first place to look. Run with --headed to watch it work.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import random
import re
import sys
import time
import urllib.parse
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from playwright.async_api import (
    async_playwright,
    Browser,
    BrowserContext,
    Page,
    ElementHandle,
    TimeoutError as PWTimeout,
)

from schema_store import (
    Phase1Store,
    local_iso,
    make_run_id,
    resolve_threads,
    utc_now,
)
import selector_overrides

# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------

SESSION_DIR = Path("fb_session")
DEFAULT_OUT = Path("output")

# Facebook throttles hard. These are deliberately conservative.
NAV_TIMEOUT_MS = 45_000
ACTION_TIMEOUT_MS = 8_000
SCROLL_PAUSE = (1.4, 2.8)      # random.uniform range, seconds
POST_PAUSE = (1.0, 2.5)        # between post page loads, per worker
MAX_EXPAND_CLICKS = 40         # cap on "view more comments" clicks per post
MAX_SCROLLS = 200              # hard stop on feed scrolling
BARREN_LIMIT = 6               # give up after N scrolls that load no new posts
COMMENT_DEADLINE_S = 900       # per-post ceiling on GraphQL comment pagination

UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

# Drive the system's real Google Chrome rather than Playwright's bundled
# Chromium: it has no prebuilt binary for Ubuntu 26.04, and real Chrome trips
# fewer of Facebook's automation checks anyway. Override with --chrome-path.
CHROME_CHANNEL = "chrome"

# Anything matching these is chrome/UI, not post media.
_MEDIA_JUNK = re.compile(r"(emoji|static\.xx|rsrc\.php|/p\d+x\d+/|safe_image)", re.I)

REACTION_TYPES = ["like", "love", "care", "haha", "wow", "sad", "angry"]


class SELECTORS:
    """Every DOM hook in one place. Fix breakage here."""

    # Feed / timeline
    article = 'div[role="article"]'
    permalink = (
        'a[href*="/posts/"], a[href*="/videos/"], a[href*="/reel/"], '
        'a[href*="story_fbid="], a[href*="permalink"]'
    )
    # Where the post's age is read from, INSIDE one feed article. Separate from
    # `permalink` because the two are only sometimes the same node: on classic
    # pages the timestamp is the permalink's own text ("5h"), but on layouts
    # that put a caption or an author name in that anchor, reading its text
    # dates the post by the wrong string -- and a post mis-dated as recent
    # survives the feed filter only to be dropped by scrape_post's authoritative
    # creation_time check, which looks exactly like "the scraper lost my posts".
    # Empty string = fall back to the permalink node itself.
    feed_time = ""

    # Post page
    post_text_expand = 'div[role="button"]:has-text("See more"), div[role="button"]:has-text("See More")'
    images = 'img[src*="scontent"], img[src*="fbcdn"]'
    videos = "video"

    # Reactions
    reaction_bar = '[aria-label*="reaction"], [aria-label*="Reaction"]'
    dialog = 'div[role="dialog"]'
    dialog_tab = '[role="tab"]'
    dialog_close = '[aria-label="Close"], [aria-label="close"]'

    # Comments
    # Profile header
    followers_link = 'a[href$="/followers/"], a[href*="/followers"]'
    following_link = 'a[href$="/following/"], a[href*="/following"]'
    profile_name = "h1"

    comment_sort_button = 'div[role="button"]:has-text("Most relevant"), div[role="button"]:has-text("Top comments")'
    comment_article = 'div[role="article"][aria-label]'
    cookie_banner = '[data-cookiebanner="accept_button"], [aria-label*="Allow all cookies"]'
    login_popup_close = '[aria-label="Close"]'


class TEXT_PATTERNS:
    """Button labels we click. Facebook localises these -- add your locale's strings."""

    all_comments = ["All comments", "All Comments"]
    more_comments = [
        "View more comments",
        "View previous comments",
        "See more comments",
        "Load more comments",
    ]
    # Reply-thread EXPANDERS only -- must NOT match the bare "Reply" compose
    # button (clicking that opens a reply box). Matched as a regex on button
    # text: "View 3 replies", "3 replies", "View all 5 replies", "1 reply".
    reply_expander = re.compile(r"(view\s+(all\s+)?\d+\s+repl|^\d+\s+repl|view\s+repl)", re.I)
    see_more = ["See more", "See More"]


# --------------------------------------------------------------------------
# Data model
# --------------------------------------------------------------------------


@dataclass
class ProfileMeta:
    """One row per run. Appended, not overwritten -- runs build a time series."""
    profile_url: str = ""
    profile_name: str = ""
    followers: int = 0
    followers_raw: str = ""      # FB rounds to "9.6M"; keep what it displayed
    following: int = 0
    following_raw: str = ""
    run_started: str = ""
    run_finished: str = ""
    run_duration_seconds: float = 0.0
    window_since: str = ""
    window_until: str = ""
    workers: int = 0
    posts_scraped: int = 0
    comments_scraped: int = 0


# --------------------------------------------------------------------------
# Parsing helpers
# --------------------------------------------------------------------------


def parse_count(raw: str | None) -> int:
    """'1.2K' -> 1200, '3.4M' -> 3400000, '1,234' -> 1234, 'All 57' -> 57."""
    if not raw:
        return 0
    m = re.search(r"([\d.,]+)\s*([KMB])?", raw.replace(" ", " "), re.I)
    if not m:
        return 0
    num, suffix = m.group(1), (m.group(2) or "").upper()
    try:
        val = float(num.replace(",", ""))
    except ValueError:
        return 0
    return int(val * {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000}.get(suffix, 1))


_MONTHS = {
    m.lower(): i
    for i, m in enumerate(
        ["January", "February", "March", "April", "May", "June", "July",
         "August", "September", "October", "November", "December"], start=1)
}
_MONTHS.update({k[:3]: v for k, v in list(_MONTHS.items())})


def parse_fb_time(raw: str, now: datetime | None = None) -> datetime | None:
    """
    Turn Facebook's timestamp text into a datetime (local tz).

    Handles the relative forms the feed uses ('2h', '3d', 'Yesterday at 20:15')
    and the absolute forms the hover-tooltip uses
    ('Monday, 13 July 2026 at 10:30', 'July 13 at 10:30 AM').
    """
    if not raw:
        return None
    now = now or datetime.now().astimezone()
    s = raw.strip().replace(" ", " ").replace(" ", " ")

    # Drop a leading weekday name (with or without comma): "Monday 13 July..."
    # would otherwise be misread as month="Monday".
    s = re.sub(r"^(Mon|Tue|Wed|Thu|Fri|Sat|Sun)[a-z]*,?\s+", "", s, flags=re.I)

    if re.fullmatch(r"just now|now", s, re.I):
        return now

    # Compact relative: 5m / 2h / 3d / 2w
    m = re.fullmatch(r"(\d+)\s*(m|min|mins|minutes?|h|hr|hrs|hours?|d|days?|w|wks?|weeks?)", s, re.I)
    if m:
        n, unit = int(m.group(1)), m.group(2).lower()
        if unit.startswith(("m", "min")):
            return now - timedelta(minutes=n)
        if unit.startswith(("h", "hr")):
            return now - timedelta(hours=n)
        if unit.startswith("d"):
            return now - timedelta(days=n)
        return now - timedelta(weeks=n)

    # Clock time, if present anywhere in the string
    tm = re.search(r"(\d{1,2}):(\d{2})\s*(AM|PM)?", s, re.I)
    hh, mm = 0, 0
    if tm:
        hh, mm = int(tm.group(1)), int(tm.group(2))
        ap = (tm.group(3) or "").upper()
        if ap == "PM" and hh != 12:
            hh += 12
        elif ap == "AM" and hh == 12:
            hh = 0

    if re.match(r"yesterday", s, re.I):
        d = now - timedelta(days=1)
        return d.replace(hour=hh, minute=mm, second=0, microsecond=0)
    if re.match(r"today", s, re.I):
        return now.replace(hour=hh, minute=mm, second=0, microsecond=0)

    # Absolute: "13 July 2026", "July 13, 2026", "13 July"
    dm = re.search(r"(\d{1,2})\s+([A-Za-z]{3,9})|([A-Za-z]{3,9})\s+(\d{1,2})", s)
    if dm:
        if dm.group(1):
            day, mon_name = int(dm.group(1)), dm.group(2)
        else:
            day, mon_name = int(dm.group(4)), dm.group(3)
        mon = _MONTHS.get(mon_name.lower()) or _MONTHS.get(mon_name.lower()[:3])
        if mon:
            ym = re.search(r"\b(20\d{2})\b", s)
            year = int(ym.group(1)) if ym else now.year
            try:
                dt = datetime(year, mon, day, hh, mm, tzinfo=now.tzinfo)
            except ValueError:
                return None
            # No year given and the date is in the future => it was last year.
            if not ym and dt > now + timedelta(days=1):
                dt = dt.replace(year=year - 1)
            return dt
    return None


def extract_post_id(url: str) -> str:
    for pat in (
        r"/posts/(pfbid[\w]+|\d+)",
        r"/videos/(\d+)",
        r"/reel/(\d+)",
        r"story_fbid=(pfbid[\w]+|\d+)",
        r"/permalink/(\d+)",
        r"[?&]v=(\d+)",
    ):
        m = re.search(pat, url)
        if m:
            return m.group(1)
    return url.rsplit("/", 1)[-1][:64]


def clean_url(url: str) -> str:
    """Strip FB's tracking query junk but keep the identifying params."""
    if "?" not in url:
        return url
    base, _, qs = url.partition("?")
    keep = [
        p for p in qs.split("&")
        if p.split("=")[0] in {"story_fbid", "id", "fbid", "v"}
    ]
    return base + ("?" + "&".join(keep) if keep else "")


def post_type_of(url: str) -> str:
    """`post` / `reel` / `video` / `photo`, from the permalink shape."""
    if "/reel/" in url:
        return "reel"
    if "/videos/" in url or re.search(r"[?&]v=\d+", url) or "/watch" in url:
        return "video"
    if "/photo" in url or "fbid=" in url:
        return "photo"
    return "post"


def scrape_url_for(url: str) -> str:
    """
    The URL we actually navigate to, which is not always the permalink.

    Loading `/<page>/videos/<id>/` or `/reel/<id>` directly bounces to Facebook's
    Watch player -- a bare video surface with no role=article, no message div and
    no comment stream, which is why video posts previously came back empty.
    `/watch/?v=<id>` renders the ordinary story layout (comments included), so
    every video-ish permalink is rewritten to it. The original permalink is still
    what gets stored as post_url.
    """
    m = re.search(r"/reel/(\d+)", url) or re.search(r"/videos/(?:[^/]+/)?(\d+)", url)
    if m:
        return f"https://www.facebook.com/watch/?v={m.group(1)}"
    return url


def _b64_comment_ids(token: str) -> tuple[str, str]:
    """
    Decode a Facebook comment node id.

    'Y29tbWVudDoxMjNfNDU2' -> b'comment:123_456' -> ('123', '456'), i.e.
    (owning feedback id, comment id). Used to recover a reply's parent.
    """
    if not token:
        return "", ""
    try:
        raw = base64.b64decode(token + "=" * (-len(token) % 4)).decode("utf-8", "ignore")
    except Exception:
        return "", ""
    m = re.match(r"comment:(\d+)_(\d+)", raw)
    return (m.group(1), m.group(2)) if m else ("", "")


async def jitter(rng: tuple[float, float]) -> None:
    await asyncio.sleep(random.uniform(*rng))


# --------------------------------------------------------------------------
# Browser
# --------------------------------------------------------------------------


async def launch_ctx(p, headless: bool, chrome_path: str | None = None) -> BrowserContext:
    """Persistent context => the login cookie survives between runs."""
    SESSION_DIR.mkdir(exist_ok=True)
    opts: dict[str, Any] = dict(
        user_data_dir=str(SESSION_DIR),
        headless=headless,
        user_agent=UA,
        locale="en-US",
        viewport={"width": 1400, "height": 900},
        args=["--disable-blink-features=AutomationControlled"],
    )
    if chrome_path:
        opts["executable_path"] = chrome_path
    else:
        opts["channel"] = CHROME_CHANNEL

    # A Ctrl-C'd run leaves these behind and Chrome then refuses to start.
    for lock in ("SingletonLock", "SingletonSocket", "SingletonCookie"):
        (SESSION_DIR / lock).unlink(missing_ok=True)

    try:
        return await p.chromium.launch_persistent_context(**opts)
    except Exception as e:
        msg = str(e)
        if "ProcessSingleton" in msg or "already in use" in msg:
            sys.exit(
                "\n  The session profile is locked by another Chrome instance.\n"
                "  A previous run is probably still open -- close that window, or:\n"
                f"    pkill -f 'user-data-dir={SESSION_DIR.resolve()}'\n"
            )
        sys.exit(
            f"\n  Could not start Chrome: {msg.splitlines()[0]}\n"
            f"  Point at a browser explicitly, e.g.:\n"
            f"    --chrome-path /usr/bin/google-chrome\n"
            f"    --chrome-path /usr/bin/brave-browser\n"
        )


async def is_logged_in(ctx: BrowserContext) -> bool:
    """A Facebook session is exactly the c_user + xs cookie pair."""
    names = {c["name"] for c in await ctx.cookies() if "facebook" in c.get("domain", "")}
    return {"c_user", "xs"} <= names


async def dismiss_overlays(page: Page) -> None:
    for sel in (SELECTORS.cookie_banner,):
        try:
            btn = page.locator(sel).first
            if await btn.count() and await btn.is_visible():
                await btn.click(timeout=2000)
                await asyncio.sleep(0.5)
        except Exception:
            pass


async def cmd_login(chrome_path: str | None = None) -> None:
    async with async_playwright() as p:
        ctx = await launch_ctx(p, headless=False, chrome_path=chrome_path)
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()
        await page.goto("https://www.facebook.com/login", timeout=NAV_TIMEOUT_MS)
        print("\n  A browser window is open.")
        print("  Log in to Facebook there (solve any 2FA / checkpoint).")
        print("  Wait until your NEWS FEED is actually visible -- not the 2FA screen,")
        print("  not a checkpoint -- then come back here and press Enter.\n")
        await asyncio.get_event_loop().run_in_executor(None, input, "  Press Enter when logged in... ")

        ok = await is_logged_in(ctx)
        await ctx.close()

    if ok:
        print(f"\n  Login confirmed. Session saved to {SESSION_DIR}/ -- you can now run `scrape`.\n")
    else:
        sys.exit(
            "\n  Login NOT saved -- no c_user/xs cookie was set.\n"
            "  You probably pressed Enter before the feed finished loading, or the\n"
            "  login stopped at a checkpoint. Run `login` again and go all the way through.\n"
        )


# --------------------------------------------------------------------------
# Feed: collect post permalinks within the time window
# --------------------------------------------------------------------------


async def scrape_profile_meta(page: Page, profile_url: str) -> ProfileMeta:
    """
    Follower / following counts off the profile header. Facebook rounds these
    ('9.6M'), so the raw string is kept alongside the parsed int.
    """
    meta = ProfileMeta(profile_url=profile_url)

    # Logged-in profiles have no <h1> and a useless tab title ("(20+) Facebook").
    # The display name is, however, the most frequent link that points back at
    # the profile itself. Count those and take the winner (ignoring the section
    # links -- Photos, About, followers... -- that share the profile slug).
    _GENERIC = re.compile(
        r"^(photos?|about|posts?|reels?|videos?|more|all|friends?|following|"
        r"followers?|intro|mentions?|likes?|see all|\d)", re.I)
    slug = re.sub(r"/+$", "", profile_url).split("/")[-1].split("?")[0]
    try:
        counts: dict[str, int] = {}
        if slug:
            for a in await page.query_selector_all(f'a[href*="{slug}"]'):
                t = (await a.inner_text() or "").strip().split("\n")[0]
                if 1 < len(t) < 50 and "facebook" not in t.lower() and not _GENERIC.match(t):
                    counts[t] = counts.get(t, 0) + 1
        if counts:
            meta.profile_name = max(counts, key=counts.get)
    except Exception:
        pass

    # Fallbacks: og:title (present when logged out), then de-badged tab title.
    if not meta.profile_name:
        try:
            og_el = await page.query_selector('meta[property="og:title"]')
            og = await og_el.get_attribute("content") if og_el else None
            if og and og.strip():
                meta.profile_name = og.strip()
        except Exception:
            pass
    if not meta.profile_name:
        try:
            t = re.sub(r"^\(\d+\+?\)\s*", "", await page.title()).split("|")[0].strip()
            if t and t.lower() != "facebook":
                meta.profile_name = t
        except Exception:
            pass

    for sel, raw_attr, num_attr in (
        (SELECTORS.followers_link, "followers_raw", "followers"),
        (SELECTORS.following_link, "following_raw", "following"),
    ):
        try:
            el = await page.query_selector(sel)
            if el:
                txt = (await el.inner_text() or "").strip()
                if txt:
                    # "9.6M followers" -> keep just "9.6M"
                    bare = re.sub(r"\s*(followers?|following)\s*", "", txt, flags=re.I).strip()
                    setattr(meta, raw_attr, bare or txt)
                    setattr(meta, num_attr, parse_count(txt))
        except Exception:
            continue

    # Fallback: read them out of the page text.
    body = ""
    if not meta.followers or not meta.following:
        try:
            body = await page.inner_text("body")
        except Exception:
            pass
    if body and not meta.followers:
        m = re.search(r"([\d.,]+\s*[KMB]?)\s*followers?", body, re.I)
        if m:
            meta.followers_raw, meta.followers = m.group(1).strip(), parse_count(m.group(1))
    if body and not meta.following:
        m = re.search(r"([\d.,]+\s*[KMB]?)\s*following", body, re.I)
        if m:
            meta.following_raw, meta.following = m.group(1).strip(), parse_count(m.group(1))

    return meta


async def collect_post_links(
    page: Page, profile_url: str, since: datetime, until: datetime,
    limit: int | None = None, verbose: bool = True,
) -> tuple[list[str], ProfileMeta, dict[str, str]]:
    """
    Scroll the timeline, harvesting permalinks.

    Also returns each link's feed time text. Live videos redirect to
    /watch/live/, a surface that embeds no story JSON at all, so the post page
    has no publish time to offer and they were stored undated; the feed knew the
    time all along and used to throw it away here.

    Facebook VIRTUALISES the feed: posts that scroll out of view are unmounted
    and their DOM nodes recycled, so at any instant only a handful of articles
    exist. We therefore re-scan every article on every scroll and dedupe by
    permalink, rather than tracking "new" ones by index (which breaks the moment
    the count goes down). Stopping is driven by two independent signals:
      * we've collected N unique posts older than the window, or
      * the page height stops growing (feed genuinely exhausted).
    """
    await page.goto(profile_url.rstrip("/"), timeout=NAV_TIMEOUT_MS, wait_until="domcontentloaded")
    await dismiss_overlays(page)
    await asyncio.sleep(3)

    meta = await scrape_profile_meta(page, profile_url)
    if verbose:
        print(f"  {meta.profile_name or '?'} -- "
              f"{meta.followers_raw or '?'} followers, {meta.following_raw or '?'} following")

    links: dict[str, None] = {}    # in-window permalinks, ordered
    unknown: dict[str, None] = {}  # permalinks whose feed time didn't parse
    stale: set[str] = set()        # unique permalinks older than the window
    times: dict[str, str] = {}     # permalink -> feed time text, for the fallback
    last_height = 0
    stagnant = 0

    for scroll_i in range(MAX_SCROLLS):
        for art in await page.query_selector_all(SELECTORS.article):
            href, raw_time = await _article_link_and_time(art)
            if not href:
                continue
            url = clean_url(href)
            if url in links or url in stale:
                continue

            dt = parse_fb_time(raw_time)
            if raw_time:
                times[url] = raw_time
            if dt and dt < since:
                stale.add(url)
            elif dt and dt <= until:
                links[url] = None
                unknown.pop(url, None)
            elif not dt:
                # Feed gave no parseable time -- hold it; the post page decides.
                unknown[url] = None

        if limit and len(links) >= limit:
            if verbose:
                print(f"\n  reached --limit ({limit}) after {scroll_i} scrolls")
            break
        if len(stale) >= 3:
            if verbose:
                print(f"\n  passed {len(stale)} posts older than the window "
                      f"after {scroll_i} scrolls")
            break

        await page.mouse.wheel(0, random.randint(2200, 3200))
        await jitter(SCROLL_PAUSE)

        height = await page.evaluate("document.body.scrollHeight")
        if height <= last_height:
            stagnant += 1
            if stagnant >= BARREN_LIMIT:
                if verbose:
                    print(f"\n  feed stopped growing after {scroll_i} scrolls")
                break
        else:
            stagnant = 0
            last_height = height

        if verbose and scroll_i % 3 == 0:
            print(f"  scroll {scroll_i}: {len(links)} in-window, "
                  f"{len(unknown)} unknown-time, {len(stale)} past-window", end="\r", flush=True)

    # If nothing carried a parseable feed time (locale/format we don't handle),
    # fall back to the unknown-time links so the run still produces something;
    # scrape_post re-checks each against the window from the post page itself.
    result = list(links) if links else list(unknown)
    if limit:
        result = result[:limit]
    if verbose:
        print(f"\n  collected {len(result)} candidate post links "
              f"({len(links)} dated in-window, {len(unknown)} undated)")
    return result, meta, times


async def _article_link_and_time(art: ElementHandle) -> tuple[str, str]:
    """Pull the permalink + its displayed time text out of one feed article.

    The two are read separately (see SELECTORS.feed_time): pairing a permalink
    with a timestamp that belongs to a different node is worse than having no
    timestamp at all, because an undated link is held and re-checked on the post
    page while a wrongly-dated one is silently discarded.
    """
    try:
        a = await art.query_selector(SELECTORS.permalink)
        if not a:
            return "", ""
        href = await a.get_attribute("href") or ""
        if href.startswith("/"):
            href = "https://www.facebook.com" + href

        # Dedicated timestamp node if this profile's layout needs one...
        raw = ""
        if SELECTORS.feed_time:
            t = await art.query_selector(SELECTORS.feed_time)
            if t:
                raw = ((await t.inner_text() or "").strip()
                       or (await t.get_attribute("aria-label") or "").strip())
        # ...otherwise the permalink's own text, then its aria-label.
        if not raw:
            raw = (await a.inner_text() or "").strip()
        if not raw or len(raw) > 40:
            raw = (await a.get_attribute("aria-label") or "").strip()
        # Anything that is plainly not a timestamp is dropped rather than fed to
        # parse_fb_time, which would return None anyway but only after the
        # caller has lost the chance to treat the link as undated.
        return href, (raw if _looks_like_time(raw) else "")
    except Exception:
        return "", ""


_TIME_ISH = re.compile(
    r"^\s*(just now|now|yesterday|today|\d+\s*(m|min|mins|minutes?|h|hr|hrs|"
    r"hours?|d|days?|w|wks?|weeks?)\b|\d{1,2}\s+[A-Za-z]{3,9}|[A-Za-z]{3,9}\s+"
    r"\d{1,2}|(mon|tue|wed|thu|fri|sat|sun)[a-z]*,?\s)", re.I)


def _looks_like_time(raw: str) -> bool:
    """Cheap guard: does this string plausibly denote a time at all?"""
    return bool(raw) and len(raw) <= 40 and bool(_TIME_ISH.match(raw))


# --------------------------------------------------------------------------
# Post page: text, media, counts, reactions
# --------------------------------------------------------------------------


async def _looks_logged_out(page: Page) -> bool:
    """
    Facebook answers a hammered session with a logged-out shell: the cookies are
    still valid, but the page renders a QR-login panel and no content. Detecting
    it lets the caller back off instead of recording an empty post.
    """
    try:
        return await page.locator(
            'div[role="button"]:has-text("Log in with QR code"), '
            'form[action*="/login"] input[name="pass"]').count() > 0
    except Exception:
        return False


async def scrape_post(
    ctx: BrowserContext,
    url: str,
    since: datetime,
    until: datetime,
    want_comments: bool,
    want_breakdown: bool,
    max_comments: int = 0,
    profile: str = "",
    feed_time: str = "",
) -> tuple[dict | None, list[dict]]:
    """
    Scrape one post into a Phase-1 `posts` document plus its `comments` documents.

    Returns (None, []) when the post falls outside the window or the page can't
    be read, so the caller records nothing rather than a hollow row.
    """
    page = await ctx.new_page()
    page.set_default_timeout(ACTION_TIMEOUT_MS)
    try:
        post_id = extract_post_id(url)
        # Video/reel permalinks must be rewritten or Facebook serves the Watch
        # player, which carries no post text, timestamp or comments at all.
        nav_url = scrape_url_for(url)
        await page.goto(nav_url, timeout=NAV_TIMEOUT_MS, wait_until="domcontentloaded")
        await dismiss_overlays(page)
        await asyncio.sleep(3)

        if await _looks_logged_out(page):
            print(f"  ! logged-out shell served for {url} -- backing off")
            await asyncio.sleep(random.uniform(20, 40))
            return None, []

        # On a permalink page the POST is not wrapped in role=article (only the
        # comments are), so everything is extracted at page level from the top
        # of the document.
        # The embedded story JSON is the authority for publish time and reaction
        # totals. It is several megabytes, so it is fetched once and shared.
        try:
            html = await page.content()
        except Exception:
            html = ""

        created = story_creation_time(html, post_id)
        if created:
            dt = datetime.fromtimestamp(created).astimezone()
            timestamp_raw = f"creation_time:{created}"
        else:
            timestamp_raw = await _exact_time(page, post_id)
            dt = parse_fb_time(timestamp_raw)
            if dt is None and feed_time:
                # Last resort, and the only one that works for live videos: the
                # /watch/live/ surface carries no story JSON, and _exact_time
                # there latches onto the player chrome (it returned the literal
                # string "Reels"). The feed's own time text is coarse but real.
                dt = parse_fb_time(feed_time)
                if dt:
                    timestamp_raw = f"feed:{feed_time}"
        if dt and not (since <= dt <= until):
            return None, []              # outside window -- drop it

        # Nudge the comment stream into existence: _story_scope anchors on it,
        # and it has to be mounted before any of the counts can be scoped.
        try:
            await page.mouse.wheel(0, 1200)
            await asyncio.sleep(1.5)
        except Exception:
            pass

        # Everything numeric is read inside the story column so the Watch
        # sidebar's recommended videos can't donate their counts to this post.
        # Scoping must never lose data, so anything that comes back empty is
        # retried page-wide -- the old, contamination-prone but complete path.
        scope = await _story_scope(page)
        counts = await _engagement_counts(page, scope)
        if scope is not None and not counts["comments"]:
            counts = await _engagement_counts(page, None)

        # The comment total has three independent sources because each one has
        # gone missing in production: the rendered summary string (removed by
        # Facebook on permalinks), the story JSON (absent on /watch/live/), and
        # the mounted comment nodes (present but lazy). Take the largest -- they
        # can only ever undercount, never invent comments that aren't there.
        n_rendered = await _rendered_comment_count(page)
        counts["comments"] = max(counts["comments"],
                                 story_comment_total(html, post_id),
                                 n_rendered)

        # No page-wide retry for these two: an empty result is better than a
        # confident wrong one borrowed from a recommended video in the sidebar.
        breakdown = await _reaction_breakdown(page, scope) if want_breakdown else {}
        views = await _view_count(page, scope)
        # Per-type counts only exist in the DOM, but the JSON total is the more
        # trustworthy figure and is the only one reels publish at all.
        rx_total = story_reaction_total(html, post_id) or sum(breakdown.values())

        images, videos = await _media(page)

        post = {
            "post_id": post_id,
            "profile": profile,
            "page_id": story_page_id(html, post_id),
            "platform": "facebook",
            "post_url": url,
            "post_type": post_type_of(url),
            "caption": await _post_text(page, html, post_id),
            "post_timestamp": dt.isoformat(timespec="seconds") if dt else "",
            "post_timestamp_raw": timestamp_raw,
            "author": await _author(page),
            "reactions": {**{k: breakdown.get(k, 0) for k in REACTION_TYPES},
                          "total": rx_total or counts["reactions"]},
            "comment_count": counts["comments"],
            "share_count": counts["shares"],
            "view_count": views,
            "media_urls": [u for u in (images.split(" | ") + videos.split(" | ")) if u],
            "scrape_url": nav_url,
        }

        comments: list[dict] = []
        # Gated on "is there a comment stream", never on the count alone: a count
        # that fails to parse must not be indistinguishable from a post nobody
        # commented on. n_rendered is the independent witness.
        if want_comments and (post["comment_count"] or n_rendered):
            # Prefer the GraphQL replay (gets the full thread); fall back to the
            # DOM click-scraper if the request template can't be captured.
            comments = await harvest_comments_graphql(page, post_id, max_comments)
            if not comments:
                comments = await scrape_comments(page, post_id, max_comments)
        post["comments_captured"] = len(comments)

        return post, comments

    except PWTimeout:
        print(f"  ! timeout on {url}")
        return None, []
    except Exception as e:
        print(f"  ! error on {url}: {type(e).__name__}: {e}")
        return None, []
    finally:
        await page.close()


_STORY_ANCHOR = re.compile(r'"creation_time":(\d{10}),"url":"((?:[^"\\]|\\.)*)"')
_REACTION_COUNT = re.compile(r'"reaction_count":\{"count":(\d+)')
# Two spellings of the same figure. Permalinks serialise the post's feedback as
# `"comments":{"total_count":N}`; the /watch/ (video and live) surface uses the
# flat `"total_comment_count":N` instead.
_COMMENT_TOTAL = re.compile(
    r'"comments":\{"total_count":(\d+)\}|"total_comment_count":(\d+)')


def story_anchors(html: str, post_id: str) -> list[int]:
    """Offsets of this post's story blocks inside the page's embedded JSON."""
    return [m.start() for m in _STORY_ANCHOR.finditer(html)
            if post_id and post_id in m.group(2).replace("\\/", "/")]


def story_page_id(html: str, post_id: str) -> str:
    """
    Numeric id of the profile that published the post.

    The slug in the URL can be changed by its owner, so the schema's `page_id`
    wants the permanent id. It sits in the story's `owning_profile` block, just
    ahead of the creation_time that identifies the story.
    """
    ancs = story_anchors(html, post_id)
    hits = [(m.start(), m.group(1))
            for m in re.finditer(r'"owning_profile":\{[^{}]*?"id":"(\d+)"', html)]
    if not (ancs and hits):
        return ""
    return min(hits, key=lambda t: min(abs(t[0] - a) for a in ancs))[1]


def story_reaction_total(html: str, post_id: str) -> int:
    """
    Total reactions on the post, from the embedded story JSON.

    Reels expose no 'Like: N people' aria-label at all, so the DOM route reports
    zero for them; and reading the DOM page-wide instead lets a recommended
    video's reaction bar stand in for the post's. The JSON figure is tied to the
    story itself. It is located either by the post id appearing alongside it, or
    failing that by proximity to the story block -- other stories embedded on the
    same page keep their counts far away from this one.
    """
    hits = [(m.start(), int(m.group(1))) for m in _REACTION_COUNT.finditer(html)]
    if not hits:
        return 0
    for pos, val in hits:
        if post_id and post_id in html[max(0, pos - 4000):pos + 4000]:
            return val
    ancs = story_anchors(html, post_id)
    if ancs:
        return min(hits, key=lambda t: min(abs(t[0] - a) for a in ancs))[1]
    return 0


def story_comment_total(html: str, post_id: str) -> int:
    """
    Total comments on the post, from the embedded story JSON.

    Facebook stopped rendering the '134 comments' summary string on permalinks,
    which is all `_engagement_counts` could ever read. The count then came back
    as zero for every ordinary post, and because the comment harvest was gated on
    it, those posts were filed as having no comments at all rather than as having
    failed -- 68 of 88 posts in one run, each with tens to hundreds of real
    comments. The JSON figure is unaffected by that rendering change.

    Located exactly like `story_reaction_total`: the post's own feedback block
    carries its permalink alongside the count, and failing that the nearest count
    to the story block wins -- other stories embedded on the same page (sidebar
    videos, shared posts) keep theirs far away.
    """
    hits = [(m.start(), int(m.group(1) or m.group(2)))
            for m in _COMMENT_TOTAL.finditer(html)]
    if not hits:
        return 0
    for pos, val in hits:
        if post_id and post_id in html[max(0, pos - 4000):pos + 4000]:
            return val
    ancs = story_anchors(html, post_id)
    if ancs:
        return min(hits, key=lambda t: min(abs(t[0] - a) for a in ancs))[1]
    return 0


def story_creation_time(html: str, post_id: str) -> int | None:
    """
    The post's true publish time, as a unix timestamp, from the page's embedded
    story JSON.

    This is the only trustworthy source. The DOM route dates a post by whichever
    timestamp link is found first, and on these pages every such link belongs to
    a *comment* -- comment permalinks embed the post id too, so the post ends up
    stamped with the time of its newest comment, changing on every run. Hovering
    for a tooltip has the same flaw: it reports the time of whatever was hovered.

    In the JSON each story carries its own `"creation_time":<ts>,"url":"<perma>"`
    pair, so matching on the permalink picks out this post's time exactly, even
    though the page embeds several other stories. Note that comments serialise
    theirs as `created_time` -- a different key -- so the two cannot be confused.
    """
    for m in _STORY_ANCHOR.finditer(html):
        url = m.group(2).replace("\\/", "/")
        if post_id and post_id in url:
            return int(m.group(1))
    return None


async def _exact_time(page: Page, post_id: str) -> str:
    """
    The post's timestamp is the link whose href carries the post's own id (its
    text is relative, e.g. '10m'). Hovering it makes Facebook render a tooltip
    with the full absolute date; we prefer that, falling back to the link text.
    """
    try:
        # Every comment's own timestamp link also carries the post id in its
        # href, and those links vastly outnumber the post's own. Taking the first
        # match therefore dated each post by its newest comment, which is why the
        # same post came back with a different timestamp on every run. The
        # comment_id parameter is what distinguishes them.
        async def usable(el) -> bool:
            href = await el.get_attribute("href") or ""
            return "comment_id=" not in href and "reply_comment_id=" not in href

        a = None
        if post_id:
            for cand in await page.query_selector_all(f'a[href*="{post_id}"]'):
                t = (await cand.inner_text() or "").strip()
                if t and parse_fb_time(t) and await usable(cand):
                    a = cand
                    break
        if a is None:
            for cand in await page.query_selector_all(SELECTORS.permalink):
                if await usable(cand):
                    a = cand
                    break
        if not a:
            return ""
        fallback = (await a.inner_text() or "").strip()
        try:
            await a.hover(timeout=3000)
            await asyncio.sleep(1.2)
            tip = await page.query_selector('div[role="tooltip"]')
            if tip:
                txt = (await tip.inner_text() or "").strip()
                if txt:
                    return txt
        except Exception:
            pass
        return fallback
    except Exception:
        return ""


async def _author(page: Page) -> str:
    # The post author is the first name-heading at the top of the story.
    for sel in ("h3 a", "h2 a", '[role="main"] h3 a'):
        try:
            el = await page.query_selector(sel)
            if el:
                t = (await el.inner_text() or "").strip().split("\n")[0]
                if t and "facebook" not in t.lower():
                    return t
        except Exception:
            continue
    return ""


async def _post_text(page: Page, html: str = "", post_id: str = "") -> str:
    # Expand any truncated body first (page-level "See more").
    try:
        btn = page.locator(SELECTORS.post_text_expand).first
        if await btn.count() and await btn.is_visible():
            await btn.click(timeout=2500)
            await asyncio.sleep(0.6)
    except Exception:
        pass

    # data-ad-* wrappers are the most stable handle on the body copy. The first
    # instance on the page is the post itself.
    #
    # Wait for it rather than sampling immediately: on a slow render the query
    # returns nothing, we fall through to the JSON fallback below, and a stray
    # string from elsewhere on the page gets stored as the caption.
    sels = ('div[data-ad-comet-preview="message"]',
            'div[data-ad-preview="message"]',
            'div[data-ad-rendering-role="story_message"]')
    try:
        await page.wait_for_selector(", ".join(sels), timeout=6000, state="attached")
    except Exception:
        pass                      # genuinely absent on video/reel surfaces

    # A permalink page often renders more than one story (a neighbouring post,
    # a suggested one), so the first message div is not reliably ours -- that is
    # how an unrelated one-word post ended up stored as the caption. The page
    # title carries the opening of the real caption, so use it to pick; failing
    # that, the longest candidate is the post body rather than a stray blurb.
    cands: list[str] = []
    for sel in sels:
        for el in await page.query_selector_all(sel):
            t = (await el.inner_text() or "").strip()
            if t and t not in cands:
                cands.append(t)
    if cands:
        try:
            title = await page.title()
            frag = re.sub(r"\s*\|\s*Facebook\s*$", "", title)
            frag = frag.split(" - ", 1)[1] if " - " in frag else ""
            frag = frag.replace("…", "").rstrip(". ").strip()
            if len(frag) >= 12:
                for c in cands:
                    if c.startswith(frag[:24]):
                        return c
        except Exception:
            pass
        # No title match: only guess at the longest candidate if this page really
        # is our story's permalink. On a Watch-player page the candidates all
        # belong to other stories, and guessing there stores someone else's post.
        if not post_id or not html or story_anchors(html, post_id):
            return max(cands, key=len)

    # Video/watch surfaces carry no data-ad-* wrapper. The og:description meta
    # tag holds the caption there, and is also what a logged-out fetch returns.
    for sel in ('meta[property="og:description"]', 'meta[name="description"]'):
        el = await page.query_selector(sel)
        if el:
            t = (await el.get_attribute("content") or "").strip()
            if t:
                return t

    # Reels and videos render no caption element while logged in, and Facebook
    # strips the og: tags for logged-in requests. The caption is still in the
    # page's embedded story JSON, where the post body is "message" (comments use
    # "body"), so it can be lifted without touching the DOM.
    #
    # Only trust this when the page actually contains our story: a live video
    # served as the bare Watch player carries no story JSON, and the longest
    # "message" then belongs to something else entirely -- that is how the UI
    # string "Live videos for you" ended up stored as a post's caption. An empty
    # caption is recoverable; a confidently wrong one silently corrupts Phase 2.
    page_html = html
    if not page_html:
        try:
            page_html = await page.content()
        except Exception:
            page_html = ""
    if page_html and post_id and story_anchors(page_html, post_id):
        best = ""
        for m in re.finditer(r'"message":\{"text":"((?:[^"\\]|\\.)*)"', page_html):
            cand = _unescape_json_str(m.group(1))
            if len(cand) > len(best):
                best = cand
        if best.strip():
            return best.strip()
    return ""


async def _view_count(page: Page, scope: ElementHandle | None = None) -> int:
    """
    '1.2M views' / '45K plays' off the video surface. 0 when not shown.

    Scoped to the story column for the same reason as the reaction counts: the
    recommendation sidebar is full of other videos' view counts.
    """
    body = await _scoped_text(page, scope)
    vals = [parse_count(m) for m in
            re.findall(r"([\d.,]+\s*[KMB]?)\s*(?:views?|plays?)", body, re.I)]
    return max(vals) if vals else 0


async def _media(page: Page) -> tuple[str, str]:
    """
    Post images/videos. The story's own media sits in the header region above
    the first comment, so we only look at images that appear before it and skip
    avatars/emoji/UI chrome.
    """
    imgs, vids = [], []
    first_comment = await page.query_selector(SELECTORS.comment_article)
    for img in await page.query_selector_all(SELECTORS.images):
        # Stop once we reach the comment stream.
        if first_comment and await img.evaluate(
            "(n, c) => !!(c.compareDocumentPosition(n) & Node.DOCUMENT_POSITION_FOLLOWING)",
            first_comment,
        ):
            continue
        src = await img.get_attribute("src") or ""
        w = await img.get_attribute("width")
        try:
            wide = (not w) or float(w) > 80    # FB reports widths as floats
        except ValueError:
            wide = True
        # Avatars render at <=60px; skip them and UI junk.
        if src and not _MEDIA_JUNK.search(src) and src not in imgs and wide:
            imgs.append(src)
    for v in await page.query_selector_all(SELECTORS.videos):
        src = await v.get_attribute("src") or await v.get_attribute("data-src") or ""
        poster = await v.get_attribute("poster") or ""
        pick = src or poster
        if pick and pick not in vids:
            vids.append(pick)
    return " | ".join(imgs), " | ".join(vids)


async def _story_scope(page: Page) -> ElementHandle | None:
    """
    The container holding the post and its engagement bar.

    On a Watch/reel surface the page also renders a sidebar of recommended
    videos, each with its own '167M views' and reaction labels. Reading counts
    page-wide and taking the maximum therefore picks up whichever unrelated video
    happens to be most viral.

    We anchor on the comment stream and walk up to the first ancestor that shows
    the post's own engagement summary ('23K comments'). Anchoring on a reaction
    label instead does not work: every comment carries one of those, so the walk
    stops immediately on a single comment.
    """
    try:
        anchor = await page.query_selector(SELECTORS.comment_article)
        if not anchor:
            return None
        handle = await anchor.evaluate_handle(
            """n => {
                const rx = '[aria-label^="Like:"], [aria-label*="reaction"]';
                const re = /[\\d.,]+\\s*[KMB]?\\s*comments?/i;
                let el = n;
                for (let i = 0; i < 12 && el.parentElement; i++) {
                    el = el.parentElement;
                    // Require BOTH the engagement summary and a reaction label:
                    // stopping at the first container with just the comment
                    // count lands above the reaction bar on reel surfaces, and
                    // the post comes back with zero reactions.
                    if (re.test(el.innerText || "") && el.querySelector(rx))
                        return el;
                }
                // Facebook stopped rendering that summary string on permalinks,
                // which left this walk returning null for every ordinary post.
                // Fall back to the same landmark by structure instead of text:
                // the story column is the first ancestor holding a reaction bar
                // that is NOT inside a comment (every comment carries one too,
                // so an unfiltered reaction test stops on the anchor itself).
                el = n;
                for (let i = 0; i < 14 && el.parentElement; i++) {
                    el = el.parentElement;
                    const own = [...el.querySelectorAll(rx)].filter(
                        x => !x.closest('[role="article"][aria-label]'));
                    if (own.length) return el;
                }
                return null;
            }"""
        )
        return handle.as_element() if handle else None
    except Exception:
        return None


async def _scoped_text(page: Page, scope: ElementHandle | None) -> str:
    """inner_text of the story column, falling back to the whole document."""
    if scope is not None:
        try:
            t = await scope.inner_text()
            if t:
                return t
        except Exception:
            pass
    try:
        return await page.inner_text("body")
    except Exception:
        return ""


async def _engagement_counts(page: Page, scope: ElementHandle | None = None) -> dict[str, int]:
    """
    Comment / share totals are shown as '134 comments', '49 shares' spans. The
    same number is rendered several times; the post's own totals are the largest
    within the story column (embedded/quoted posts show smaller ones).
    """
    out = {"reactions": 0, "comments": 0, "shares": 0}
    body = await _scoped_text(page, scope)
    if not body:
        return out
    for key, pat in (
        ("comments", r"([\d.,]+\s*[KMB]?)\s*comments?"),
        ("shares", r"([\d.,]+\s*[KMB]?)\s*shares?"),
    ):
        vals = [parse_count(m) for m in re.findall(pat, body, re.I)]
        if vals:
            out[key] = max(vals)
    return out


async def _rendered_comment_count(page: Page) -> int:
    """
    How many comments are actually mounted in the DOM right now.

    The last-resort floor under the comment count: it can only ever undercount
    (the stream is lazily rendered), but it is the one signal that survives when
    both the summary string and the story JSON are missing, and any non-zero
    value is proof the post HAS comments -- which is all the harvest gate needs.
    """
    try:
        return await page.eval_on_selector_all(
            '[role="article"][aria-label]',
            'els => els.filter(e => /^Comment by /.test('
            'e.getAttribute("aria-label") || "")).length')
    except Exception:
        return 0


# "Like: 757 people", "Sad: 149 people" -- the reaction tooltip labels.
_REACT_LABEL = re.compile(
    r"^(Like|Love|Care|Haha|Wow|Sad|Angry):\s*([\d.,]+\s*[KMB]?)", re.I)


async def _reaction_breakdown(page: Page, scope: ElementHandle | None = None) -> dict[str, int]:
    """
    Read the per-type reaction counts straight from the aria-labels Facebook
    renders on the summary row ('Like: 757 people', ...), no dialog click
    needed. A given type can appear for both the post and a comment; the post's
    figure is the largest, so we take the max per type -- but only inside the
    story column, or a viral video in the sidebar wins instead.
    """
    out = {k: 0 for k in REACTION_TYPES}

    # Largest per type inside the story column. Document order is NOT usable to
    # separate the post from its comments here -- Facebook's DOM order does not
    # follow the visual layout, so "the reaction bar above the comments" selects
    # the wrong element. The column scope is what keeps the Watch sidebar out.
    root = scope if scope is not None else page
    try:
        els = await root.query_selector_all("[aria-label]")
    except Exception:
        return out
    for el in els:
        # Per-element guard: Facebook recycles nodes while we iterate, and one
        # stale handle used to abort the whole scan and report zero reactions.
        try:
            label = (await el.get_attribute("aria-label") or "").strip()
        except Exception:
            continue
        m = _REACT_LABEL.match(label)
        if m:
            rtype = m.group(1).lower()
            out[rtype] = max(out[rtype], parse_count(m.group(2)))
    return out


# --------------------------------------------------------------------------
# Comments
# --------------------------------------------------------------------------


async def _click_by_text(page: Page, needles: Iterable[str], limit: int = 1) -> int:
    """Click visible role=button elements whose text contains any needle."""
    clicked = 0
    for needle in needles:
        if clicked >= limit:
            break
        try:
            loc = page.locator(f'div[role="button"]:has-text("{needle}")')
            n = min(await loc.count(), limit - clicked)
            for i in range(n):
                el = loc.nth(i)
                if await el.is_visible():
                    await el.click(timeout=3000)
                    clicked += 1
                    await asyncio.sleep(random.uniform(0.9, 1.6))
        except Exception:
            continue
    return clicked


async def _expand_replies(page: Page, limit: int = 30) -> int:
    """
    Click reply-thread expanders ('View 3 replies'), never the bare 'Reply'
    compose button. Uses a regex on button text so 'Reply' can't match.
    """
    clicked = 0
    try:
        loc = page.get_by_role("button", name=TEXT_PATTERNS.reply_expander)
        n = min(await loc.count(), limit)
        for i in range(n):
            el = loc.nth(i)
            try:
                if await el.is_visible():
                    await el.scroll_into_view_if_needed(timeout=1500)
                    await el.click(timeout=2500)
                    clicked += 1
                    await asyncio.sleep(random.uniform(0.7, 1.3))
            except Exception:
                continue
    except Exception:
        pass
    return clicked


def _unescape_json_str(raw: str) -> str:
    """Decode a raw JSON string body (\\uXXXX, \\n, emoji) safely."""
    try:
        return json.loads('"' + raw + '"')
    except Exception:
        return raw


def _unfiltered_pd(pd: str) -> str:
    """
    Ask for the unfiltered comment ordering.

    Facebook's default `RANKED_FILTERED_INTENT_V1` is the "Most relevant" view,
    which silently withholds a large share of comments (the response even says so
    in replies_fields.filtering_footer_string). Swapping the intent token for the
    unfiltered variant is the same thing the "All comments" menu item does. The
    edit is a byte-level substring replace: re-serialising the variables JSON
    makes Facebook reject the request as tampered.
    """
    if "RANKED_FILTERED_INTENT_V1" not in pd:
        return pd
    return pd.replace("RANKED_FILTERED_INTENT_V1", "RANKED_UNFILTERED_INTENT_V1")


def _is_comments_query(post_data: str) -> tuple[bool, bool]:
    """
    Is this GraphQL POST the paginated comment query, and does it carry a cursor?

    Matched on the variables' SHAPE, not on fb_api_req_friendly_name. This gate
    used to require the literal name `CommentsListComponentsPaginationQuery`;
    Facebook renamed the query, the equality check stopped matching, and the
    scraper silently fell back to the DOM for every post -- ~10 comments instead
    of thousands, with no timestamps or user ids. Names churn, the variables
    shape does not: the comment query is the one carrying a comments cursor.
    """
    if "commentsAfterCursor" not in post_data:
        return False, False
    try:
        variables = json.loads(dict(urllib.parse.parse_qsl(post_data))["variables"])
    except Exception:
        return False, False
    if "commentsAfterCursor" not in variables:
        return False, False
    return True, bool(variables.get("commentsAfterCursor"))


def _with_cursor(post_data: str, cursor: str) -> str | None:
    """
    Point a captured comments request at `cursor`.

    Two cases. A request that already carried a cursor gets that value swapped
    byte-for-byte, which definitely round-trips. The first-page request carries
    `null` instead, so the null is replaced inside the decoded variables and only
    that one field is re-encoded -- the JSON text is otherwise untouched, because
    re-serialising it makes Facebook reject the request as tampered. Accepting
    the first-page request matters: on a post whose "View more comments" button
    never renders, it is the only template we ever see.
    """
    try:
        variables = dict(urllib.parse.parse_qsl(post_data))["variables"]
        old = json.loads(variables).get("commentsAfterCursor")
    except Exception:
        return None

    if isinstance(old, str) and old:
        return post_data.replace(old, cursor)

    marker = '"commentsAfterCursor":null'
    if marker not in variables:
        return None
    patched = variables.replace(marker, '"commentsAfterCursor":' + json.dumps(cursor))

    # Splice into the raw body so every other field keeps Facebook's own encoding.
    i = post_data.find("variables=")
    if i < 0:
        return None
    i += len("variables=")
    j = post_data.find("&", i)
    j = len(post_data) if j < 0 else j
    return post_data[:i] + urllib.parse.quote(patched, safe="") + post_data[j:]


def _iter_comment_nodes(obj: Any):
    """
    Yield every comment node anywhere in a parsed GraphQL response.

    A comment node is identified structurally (it carries both `legacy_fbid` and
    `depth`) rather than by path, because Facebook returns them under several
    different connection names -- top-level `comments.edges`, `replies_connection`
    for reply sub-threads, and the feedback echo on a freshly posted comment.
    Walking the whole tree picks up replies for free.
    """
    stack = [obj]
    while stack:
        o = stack.pop()
        if isinstance(o, dict):
            if "legacy_fbid" in o and "depth" in o:
                yield o
            stack.extend(o.values())
        elif isinstance(o, list):
            stack.extend(o)


def _attachment_media(node: dict) -> str:
    """First image/gif/sticker URI attached to a comment, if any."""
    found: list[str] = []

    def walk(o: Any) -> None:
        if len(found) or not isinstance(o, (dict, list)):
            return
        if isinstance(o, dict):
            uri = o.get("uri")
            if isinstance(uri, str) and uri.startswith("http") and not _MEDIA_JUNK.search(uri):
                found.append(uri)
                return
            for v in o.values():
                walk(v)
        else:
            for v in o:
                walk(v)

    walk(node.get("attachments") or [])
    return found[0] if found else ""


def stable_user_id(author: dict) -> str:
    """
    A user key that survives between runs.

    Facebook returns either a permanent numeric id or a rotating `pfbid…` token,
    and the pfbid changes every few months -- keying on it would split one
    complainant into several people over time. So: numeric id if there is one,
    otherwise the vanity slug from the profile URL (also stable), and only as a
    last resort the pfbid. Matches the schema's "fall back to profile_url if no
    numeric id".
    """
    raw = str(author.get("id") or "")
    if raw.isdigit():
        return raw
    url = author.get("url") or ""
    slug = re.sub(r"/+$", "", url).split("/")[-1].split("?")[0]
    if slug and not slug.startswith("pfbid") and "/people/" not in url:
        return f"fb:{slug}"
    return raw


def comment_doc_from_node(node: dict, post_id: str) -> dict | None:
    """
    Map one GraphQL comment node to a Phase-1 `comments` document.

    Field names follow scrape_schema.md exactly; nothing is inferred or labelled.
    thread_root_id / depth normalisation happens later in resolve_threads once
    the whole thread is in hand.
    """
    cid = str(node.get("legacy_fbid") or "")
    if not cid:
        return None
    fb = node.get("feedback") or {}
    author = node.get("author") or {}
    body = node.get("body") or node.get("preferred_body") or {}
    text = body.get("text", "") if isinstance(body, dict) else ""

    # A depth-0 node's parent_object_ent points back at itself; only a genuinely
    # different id means this is a reply.
    _, parent_id = _b64_comment_ids(((fb.get("parent_object_ent") or {}).get("id") or ""))
    if parent_id == cid:
        parent_id = ""

    replies = fb.get("replies_fields") or {}
    created = node.get("created_time")
    uid = stable_user_id(author)
    raw_uid = str(author.get("id") or "")

    return {
        "comment_id": cid,
        "post_id": str(post_id),
        "parent_comment_id": parent_id or None,
        "thread_root_id": None,                     # filled by resolve_threads
        "depth": int(node.get("depth") or 0),
        "user_id": uid,
        "user_id_raw": raw_uid,                     # the pfbid/numeric FB gave us
        "user_name": author.get("name") or "",
        "user_profile_url": (author.get("url")
                             or (f"https://www.facebook.com/{raw_uid}" if raw_uid else "")),
        "comment_text": text,                       # raw, original language
        "comment_timestamp": local_iso(created) if created else "",
        "like_count": parse_count(str((fb.get("reactors") or {}).get("count_reduced") or "0")),
        "reply_count": int(replies.get("total_count") or replies.get("count") or 0),
        "media_url": _attachment_media(node),
        "comment_url": fb.get("url") or "",
        "is_edited": False,     # not exposed on the node; DOM-only "Edited" badge
        "is_pinned": False,
        "author_liked": False,
        "source_dialect": (node.get("translatability_for_viewer") or {}).get("source_dialect", ""),
    }


def _parse_comment_nodes(body: str, post_id: str, out: dict) -> int:
    """
    Extract comment documents from a GraphQL response body into out{id: doc}.

    The body is a single JSON object, so it is parsed properly rather than
    scraped with regexes -- the old regex approach missed `created_time` outright
    (it sits past the author's several-hundred-character profile-picture URLs)
    and could not see reply sub-threads at all.
    """
    added = 0
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return _parse_comment_nodes_regex(body, post_id, out)
    for node in _iter_comment_nodes(data):
        doc = comment_doc_from_node(node, post_id)
        if doc and doc["comment_id"] not in out:
            out[doc["comment_id"]] = doc
            added += 1
    return added


def _parse_comment_nodes_regex(body: str, post_id: str, out: dict) -> int:
    """
    Fallback for bodies that aren't valid JSON (Facebook streams some responses
    as several concatenated objects). Less complete -- no replies, no media.
    """
    added = 0
    for m in re.finditer(
        r'"legacy_fbid":"(\d+)","depth":(\d+),"body":\{"text":"((?:[^"\\]|\\.)*)"', body):
        cid, depth, text = m.group(1), int(m.group(2)), m.group(3)
        if cid in out:
            continue
        seg = body[m.end():m.end() + 4000]
        am = re.search(r'"author":\{"__typename":"[^"]*","id":"(\d+)","name":"((?:[^"\\]|\\.)*)"', seg)
        tm = re.search(r'"created_time":(\d{10})', seg)
        lm = re.search(r'"reactors":\{"count_reduced":"(\d+)"\}', body[max(0, m.start() - 4000):m.start()])
        uid = am.group(1) if am else ""
        out[cid] = {
            "comment_id": cid, "post_id": str(post_id),
            "parent_comment_id": None, "thread_root_id": None, "depth": depth,
            "user_id": uid,
            "user_name": _unescape_json_str(am.group(2)) if am else "",
            "user_profile_url": f"https://www.facebook.com/{uid}" if uid else "",
            "comment_text": _unescape_json_str(text),
            "comment_timestamp": local_iso(int(tm.group(1))) if tm else "",
            "like_count": int(lm.group(1)) if lm else 0,
            "reply_count": 0, "media_url": "", "comment_url": "",
            "is_edited": False, "is_pinned": False, "author_liked": False,
            "source_dialect": "",
        }
        added += 1
    return added


def _live_cursor(body: str) -> str | None:
    """
    The comment-list end_cursor that still has more pages.

    Reply sub-threads carry their own page_info; taking the first cursor with
    has_next_page would sometimes follow a sub-thread instead of the main list,
    so the top-level `comments` connection is preferred when the body parses.
    """
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        data = None

    if data is not None:
        best: str | None = None
        stack = [(data, False)]
        while stack:
            o, under_comments = stack.pop()
            if isinstance(o, dict):
                pi = o.get("page_info")
                if isinstance(pi, dict) and pi.get("has_next_page") and pi.get("end_cursor"):
                    if under_comments:
                        return pi["end_cursor"]        # the main list -- take it
                    best = best or pi["end_cursor"]
                for k, v in o.items():
                    stack.append((v, under_comments or k == "comments"))
            elif isinstance(o, list):
                for v in o:
                    stack.append((v, under_comments))
        return best

    for m in re.finditer(
        r'"page_info":\{"end_cursor":("(?:[^"\\]|\\.)*"|null),"has_next_page":(true|false)', body):
        if m.group(2) == "true" and m.group(1) != "null":
            try:
                return json.loads(m.group(1))
            except Exception:
                continue
    return None


_COMMENT_SCROLLER = """() => {
  // The comment list has its own scroll container, several levels above any one
  // comment and not always reachable by walking up from it, so it is found by
  // sweeping for the tallest scrollable element that contains comments.
  let best = null;
  document.querySelectorAll('*').forEach(e => {
    if (e.scrollHeight > e.clientHeight + 60 && e.clientHeight > 200 &&
        e.querySelector('[aria-label^="Comment by"]') &&
        (!best || e.scrollHeight > best.scrollHeight)) best = e;
  });
  if (!best) return null;
  const r = best.getBoundingClientRect();
  return {x: r.x + r.width / 2, y: r.y + r.height / 2};
}"""


async def _park_over_comments(page: Page) -> bool:
    """
    Put the mouse over the comment list so wheel events land on IT.

    Facebook paginates comments on scroll, but only in response to real wheel
    events delivered to the comment container: assigning `scrollTop` moves the
    list without loading anything, and wheeling at the default cursor position
    (0,0) scrolls the page behind the post instead. Parking the mouse here is
    what makes the pagination query fire at all.
    """
    try:
        box = await page.evaluate(_COMMENT_SCROLLER)
        if not box:
            return False
        await page.mouse.move(box["x"], box["y"])
        return True
    except Exception:
        return False


async def harvest_comments_graphql(page: Page, post_id: str, max_comments: int = 0) -> list[dict]:
    """
    Get the full comment thread by REPLAYING Facebook's own paginated GraphQL
    query. Clicking "View more comments" plateaus at ~30; this instead captures
    the CommentsListComponentsPaginationQuery request the page fires, then re-POSTs
    it with each successive `commentsAfterCursor`, walking every page ~20 at a
    time. Requires a real (headed) browser to fire the first request. Returns []
    if the template can't be captured, so the caller can fall back to the DOM.
    """
    comments: dict[str, dict] = {}
    tpl: dict[str, Any] = {"pd": None, "hdr": None, "live": False}
    start: dict[str, Any] = {"cursor": None}

    async def on_req(req):
        if "/api/graphql" not in req.url or req.method != "POST":
            return
        if tpl["live"]:
            return                          # already hold the better template
        body = req.post_data or ""
        is_comments, has_cursor = _is_comments_query(body)
        if not is_comments:
            return
        # A request that already carries a cursor is the better template; a
        # first-page request is kept meanwhile so there is always something to
        # replay (see _with_cursor).
        if tpl["pd"] is None or has_cursor:
            # Read the headers *before* storing anything. all_headers() is a
            # round trip to the browser, so it raises TargetClosedError if the
            # page goes away mid-call; assigning pd first would leave the
            # template half-built (body, no headers) and the failure would
            # surface much later as an AttributeError on tpl["hdr"].items().
            # This listener runs detached on the event loop, so an exception
            # escaping it is an unhandled-task dump rather than something the
            # caller's `except` can see -- one more reason to swallow it here.
            try:
                hdr = await req.all_headers()
            except Exception:
                return                      # page closed; keep what we have
            tpl["pd"], tpl["hdr"], tpl["live"] = body, hdr, has_cursor

    async def on_resp(resp):
        if "/api/graphql" in resp.url:
            try:
                body = await resp.text()
            except Exception:
                return
            if '"body":{"text"' in body:
                _parse_comment_nodes(body, post_id, comments)
                cur = _live_cursor(body)
                if cur:
                    start["cursor"] = cur

    page.on("request", on_req)
    page.on("response", on_resp)
    try:
        # Bootstrap: get the comment section rendered, switch to "All comments",
        # then click "View more comments" -- one of these fires the first
        # paginated query, which hands us the request template + a live cursor.
        await page.mouse.wheel(0, 1600)
        await asyncio.sleep(1.2)
        try:
            sb = page.locator(SELECTORS.comment_sort_button).first
            if await sb.count():
                await sb.click(timeout=4000)
                await asyncio.sleep(1)
                opt = page.locator('[role="menuitem"]:has-text("All comments")').first
                if await opt.count():
                    await opt.click(timeout=3000)
                    await asyncio.sleep(2)
        except Exception:
            pass
        # Two ways in, because the layout varies between surfaces and even
        # between loads of the same post. Older/reel surfaces still render a
        # "View more comments" button; permalinks no longer do -- there the list
        # paginates on scroll, so the mouse is parked over it and we wheel.
        parked = await _park_over_comments(page)
        for _ in range(8):
            if tpl["pd"] and start["cursor"]:
                break
            b = page.get_by_text("View more comments", exact=False).first
            if await b.count():
                try:
                    await b.scroll_into_view_if_needed(timeout=2000)
                    await b.click(timeout=2500)
                except Exception:
                    pass
                await asyncio.sleep(2.2)
                continue
            # Re-park each pass: the container is remounted as the virtualised
            # list recycles, and a stale position stops scrolling it.
            parked = await _park_over_comments(page) or parked
            await page.mouse.wheel(0, 900)
            await asyncio.sleep(1.5)

        if os.environ.get("FB_DEBUG"):
            print(f"    [harvest] template={bool(tpl['pd'])} hdr={bool(tpl['hdr'])} "
                  f"cursor={bool(start['cursor'])} parsed={len(comments)}")
        # Headers are checked alongside the body: on_req sets the two together,
        # and replaying without them is what used to raise AttributeError here.
        if not (tpl["pd"] and tpl["hdr"] and start["cursor"]):
            # Loud on purpose. The DOM fallback returns the first screen only --
            # a few dozen comments with no timestamps and no user ids -- which
            # looks like a successful small scrape unless it is called out.
            print(f"    ! comment pagination did not bootstrap "
                  f"(template={bool(tpl['pd'])} hdr={bool(tpl['hdr'])} "
                  f"cursor={bool(start['cursor'])}) "
                  f"-- DOM fallback, expect only the first screen")
            return []

        # Replay: point the captured request at each successive cursor, drop
        # accept-encoding so the reply is plain text, and follow to the end.
        headers = {k: v for k, v in tpl["hdr"].items()
                   if not k.startswith(":") and k.lower() != "accept-encoding"}
        base_pd = _unfiltered_pd(tpl["pd"])
        cursor = start["cursor"]
        errs = 0
        empty_pages = 0
        deadline = time.perf_counter() + COMMENT_DEADLINE_S
        while cursor and time.perf_counter() < deadline:
            if max_comments and len(comments) >= max_comments:
                break
            pd = _with_cursor(base_pd, cursor)
            if pd is None:
                print("    ! could not splice the cursor into the request template")
                break
            try:
                r = await page.request.post("https://www.facebook.com/api/graphql/",
                                            data=pd, headers=headers)
                body = await r.text()
            except Exception:
                body = ""
            if not body or '"error":' in body[:80]:
                errs += 1
                if errs >= 3:
                    # The unfiltered-ordering rewrite is the likeliest culprit;
                    # drop back to the exact captured request before giving up.
                    if base_pd is not tpl["pd"] and base_pd != tpl["pd"]:
                        base_pd, errs = tpl["pd"], 0
                        continue
                    break
                await asyncio.sleep(1.0)
                continue
            errs = 0
            added = _parse_comment_nodes(body, post_id, comments)
            # Facebook will keep handing out cursors long after the last comment;
            # a few consecutive empty pages means the thread is exhausted.
            empty_pages = empty_pages + 1 if added == 0 else 0
            if empty_pages >= 4:
                break
            cursor = _live_cursor(body)
            await asyncio.sleep(random.uniform(0.2, 0.5))
    finally:
        page.remove_listener("request", on_req)
        page.remove_listener("response", on_resp)

    result = list(comments.values())
    return result[:max_comments] if max_comments else result


async def scrape_comments(page: Page, post_id: str, max_comments: int = 0) -> list[dict]:
    # Default ordering is "Most relevant", which hides a large share of comments.
    # Switch to "All comments" so pagination walks the full thread.
    try:
        sort_btn = page.locator(SELECTORS.comment_sort_button).first
        if await sort_btn.count():
            await sort_btn.click(timeout=4000)
            await asyncio.sleep(1.2)
            for label in TEXT_PATTERNS.all_comments:
                opt = page.locator(f'[role="menuitem"]:has-text("{label}")').first
                if await opt.count():
                    await opt.click(timeout=3000)
                    await asyncio.sleep(2)
                    break
    except Exception:
        pass

    # Expand the thread by repeatedly clicking "View more comments". NOTE: this
    # only works in a HEADED browser -- headless Chrome gets no pagination from
    # Facebook and stalls at the first ~20. Each click loads the next batch; we
    # stop when the button is gone, the count stalls, or we hit max_comments.
    stall = 0
    for _ in range(MAX_EXPAND_CLICKS):
        before = len(await page.query_selector_all(SELECTORS.comment_article))
        if max_comments and before >= max_comments:
            break

        clicked = False
        for pat in TEXT_PATTERNS.more_comments:
            btn = page.get_by_text(pat, exact=False).first
            try:
                if await btn.count():
                    await btn.scroll_into_view_if_needed(timeout=2000)
                    await btn.click(timeout=2500)
                    clicked = True
                    break
            except Exception:
                continue
        # Expand nested reply threads as we go.
        await _expand_replies(page, limit=8)
        await asyncio.sleep(random.uniform(1.3, 2.1))

        after = len(await page.query_selector_all(SELECTORS.comment_article))
        if after <= before and not clicked:
            stall += 1
            if stall >= 3:
                break
        else:
            stall = 0

    # Reveal any remaining collapsed reply threads and truncated bodies.
    await _expand_replies(page, limit=40)
    await _click_by_text(page, TEXT_PATTERNS.see_more, limit=60)
    await asyncio.sleep(1.5)

    out: list[dict] = []
    seen: set[str] = set()
    last_top_id = ""     # most recent top-level comment, for reply linkage

    for el in await page.query_selector_all(SELECTORS.comment_article):
        try:
            label = await el.get_attribute("aria-label") or ""
            # Post body itself is also role=article; comments are labelled "Comment by ..."
            if not re.search(r"comment|repl", label, re.I):
                continue

            is_reply = bool(re.search(r"^reply", label, re.I))
            author = ""
            raw_time = ""

            # The aria-label is the reliable source of author + time:
            #   "Comment by Vishranti Yadav 5 hours ago"
            #   "Reply by Chetan Jadhav to Vishranti Yadav's comment 4 hours ago"
            m = re.match(
                r"(?:Comment|Reply) by (.+?)"
                r"(?: to .+?'s (?:comment|reply))?"
                r"\s+((?:about\s+|over\s+|almost\s+)?(?:\d+\s+\w+|a few\s+\w+|an?\s+\w+)\s+ago"
                r"|just now)$",
                label, re.I)
            if m:
                author, raw_time = m.group(1).strip(), m.group(2).strip()
            else:
                m2 = re.match(r"(?:Comment|Reply) by (.+?)(?: to |$)", label)
                author = m2.group(1).strip() if m2 else ""

            # Author profile link -> user_id where Facebook exposes a numeric one.
            author_url = ""
            a = await el.query_selector('a[href*="/user/"], a[href^="https://www.facebook.com/"]')
            if a:
                href = await a.get_attribute("href") or ""
                author_url = clean_url(href if href.startswith("http")
                                       else "https://www.facebook.com" + href)
            uid = ""
            um = re.search(r"/user/(\d+)|[?&]id=(\d+)", author_url)
            if um:
                uid = um.group(1) or um.group(2)

            # Body: comment text lives in a div[dir=auto] that isn't the author
            # name, the timestamp, or a UI verb. Take the longest such block.
            parts = []
            for d in await el.query_selector_all('div[dir="auto"]'):
                t = (await d.inner_text() or "").strip()
                if (t and t != author
                        and not re.fullmatch(r"[\d.,]+[wdhms]|\d+ \w+|Like|Reply|Share|Author|Follow",
                                             t, re.I)):
                    parts.append(t)
            text = max(parts, key=len) if parts else ""

            # IDs + parent linkage. FB's comment permalink carries the ids:
            #   top-level:  ...?comment_id=<self>
            #   reply:      ...?comment_id=<parent>&reply_comment_id=<self>
            href = ""
            for ln in await el.query_selector_all('a[href*="comment_id"]'):
                h = await ln.get_attribute("href") or ""
                if "comment_id=" in h:
                    href = h
                    if "reply_comment_id=" in h:
                        break          # prefer the link that exposes both ids
            parent = re.search(r"[?&]comment_id=(\d+)", href)
            self_reply = re.search(r"reply_comment_id=(\d+)", href)
            cid = ""
            parent_id = ""
            if self_reply:             # this row is a reply
                cid = self_reply.group(1)
                parent_id = parent.group(1) if parent else last_top_id
                is_reply = True
            elif parent:               # top-level comment
                cid = parent.group(1)
                last_top_id = cid

            # Order-based fallback when the aria-label said "reply" but the href
            # didn't expose ids (keeps the thread linkage intact).
            if is_reply and not parent_id:
                parent_id = last_top_id

            likes = 0
            like_el = await el.query_selector('[aria-label*="reaction"], [aria-label^="Like:"]')
            if like_el:
                likes = parse_count(await like_el.get_attribute("aria-label"))

            # The schema forbids storing "2d ago", so the relative label is
            # resolved to an absolute instant at scrape time.
            dt = parse_fb_time(raw_time)
            body_txt = (await el.inner_text() or "")

            key = cid or f"{author}|{text[:60]}"
            if key in seen or not (text or author):
                continue
            seen.add(key)
            out.append({
                "comment_id": cid or key,
                "post_id": str(post_id),
                "parent_comment_id": parent_id or None,
                "thread_root_id": None,
                "depth": 1 if is_reply else 0,
                "user_id": uid,
                "user_name": author,
                "user_profile_url": author_url,
                "comment_text": text,
                "comment_timestamp": dt.isoformat(timespec="seconds") if dt else "",
                "comment_timestamp_raw": raw_time,
                "like_count": likes,
                "reply_count": 0,
                "media_url": "",
                "comment_url": href,
                "is_edited": bool(re.search(r"\bEdited\b", body_txt)),
                "is_pinned": bool(re.search(r"\bPinned\b", body_txt)),
                "author_liked": False,
                "source_dialect": "",
            })
        except Exception:
            continue

    return out


# --------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------


async def worker_pool(
    ctx: BrowserContext,
    urls: list[str],
    since: datetime,
    until: datetime,
    workers: int,
    want_comments: bool,
    want_breakdown: bool,
    store: Phase1Store,
    run_id: str,
    profile: str,
    max_comments: int = 0,
    errors: list[str] | None = None,
    feed_times: dict[str, str] | None = None,
) -> tuple[int, int]:
    """
    Scrape each URL and commit it to the store the moment it finishes, flushing
    as we go so an interrupt (Ctrl-C, crash, block) never loses what was already
    collected. Returns (posts_scanned, comments_seen).

    The store is plain synchronous dict work, so concurrent workers can't
    interleave a half-written document.
    """
    sem = asyncio.Semaphore(workers)
    errors = errors if errors is not None else []
    n_posts = 0
    n_comments = 0
    done = 0
    total = len(urls)

    async def run(url: str) -> None:
        nonlocal done, n_posts, n_comments
        async with sem:
            await jitter(POST_PAUSE)
            post, cs = await scrape_post(ctx, url, since, until, want_comments,
                                         want_breakdown, max_comments, profile,
                                         (feed_times or {}).get(url, ""))
            done += 1
            if not post:
                print(f"  [{done}/{total}] skipped (outside window or unreadable)")
                errors.append(f"unreadable_or_out_of_window: {url}")
                # Also written straight to disk, not just held for record_run:
                # this list IS the diagnosis of a thin run, and a run killed
                # part-way (or SIGTERM'd from the control room) never reaches
                # the finally block that would have persisted it.
                try:
                    with (store.out / "skipped.jsonl").open(
                            "a", encoding="utf-8") as fh:
                        fh.write(json.dumps(
                            {"run_id": run_id, "url": url,
                             "at": datetime.now().astimezone()
                                   .isoformat(timespec="seconds"),
                             "reason": "unreadable_or_out_of_window"},
                            ensure_ascii=False) + "\n")
                except OSError:
                    pass        # diagnostics must never take a run down
                return

            # thread_root_id / depth need the whole thread, so resolve before
            # the comments are split across store documents.
            resolve_threads(cs)
            store.upsert_post(post, run_id)
            seen_ids = set()
            for c in cs:
                store.upsert_comment(c, run_id)
                seen_ids.add(str(c["comment_id"]))
                store.upsert_user(c.get("user_id", ""), c.get("user_name", ""),
                                  c.get("user_profile_url", ""))
            # Only meaningful once a post has been scanned at least twice.
            store.mark_missing(post["post_id"], seen_ids, run_id)
            store.flush()

            n_posts += 1
            n_comments += len(cs)
            claimed = post.get("comment_count") or 0
            pct = f"{100 * len(cs) / claimed:.0f}%" if claimed else "n/a"
            print(f"  [{done}/{total}] {post.get('post_timestamp', '')[:16]}  "
                  f"{post['reactions']['total']} reactions, "
                  f"{len(cs)}/{claimed} comments ({pct})  (saved)")

    await asyncio.gather(*(run(u) for u in urls))
    return n_posts, n_comments


# --------------------------------------------------------------------------
# MongoDB
# --------------------------------------------------------------------------


def connect_mongo_db(uri: str, db_name: str):
    """The database handle for the four Phase-1 collections, or a clear exit."""
    try:
        import pymongo
    except ImportError:
        sys.exit("  pymongo not installed. Run:  pip install pymongo")
    try:
        client = pymongo.MongoClient(uri, serverSelectionTimeoutMS=3000)
        client.admin.command("ping")
    except Exception as e:
        sys.exit(
            f"\n  Can't reach MongoDB at {uri}: {e}\n"
            f"  Start one locally with Docker:\n"
            f"    docker run -d --name fbmongo -p 27017:27017 -v fbmongo:/data/db mongo:7\n"
        )
    return client[db_name]


async def cmd_scrape(args: argparse.Namespace) -> None:
    tz = datetime.now().astimezone().tzinfo
    if args.days:
        until = datetime.now(tz)
        since = until - timedelta(days=args.days)
    else:
        since = datetime.fromisoformat(args.since).replace(tzinfo=tz)
        until = (datetime.fromisoformat(args.until).replace(tzinfo=tz)
                 if args.until else datetime.now(tz))

    if not SESSION_DIR.exists():
        sys.exit("No session found. Run:  python fb_scraper.py login")

    mongo_db = None
    if args.mongo_uri:
        mongo_db = connect_mongo_db(args.mongo_uri, args.mongo_db)

    run_started = datetime.now().astimezone()
    run_id = make_run_id(run_started)
    t0 = time.perf_counter()
    profile = re.sub(r"/+$", "", args.url).split("/")[-1].split("?")[0]

    # Whatever fb_doctor last proved works for this leader's page layout. Keyed
    # on the registry key rather than the URL slug, because the slug is whatever
    # the owner last renamed themselves to.
    selector_overrides.apply_to(SELECTORS, getattr(args, "profile_key", None))

    out = Path(args.out)
    store = Phase1Store(out, mongo_db)
    store.ensure_indexes()
    errors: list[str] = []

    print(f"\n  target : {args.url}")
    print(f"  window : {since:%Y-%m-%d %H:%M} -> {until:%Y-%m-%d %H:%M}")
    print(f"  workers: {args.workers}")
    print(f"  run_id : {run_id}")
    if mongo_db is not None:
        print(f"  mongo  : {args.mongo_uri} db={args.mongo_db}")
    print()

    async with async_playwright() as p:
        ctx = await launch_ctx(p, headless=not args.headed, chrome_path=args.chrome_path)
        ctx.set_default_navigation_timeout(NAV_TIMEOUT_MS)

        if not await is_logged_in(ctx):
            await ctx.close()
            sys.exit(
                "\n  Not logged in -- no Facebook session cookies found.\n\n"
                "  Logged-out Facebook serves ~4 stub posts behind a login wall and\n"
                "  no comments or reactions at all, so there is nothing to scrape.\n\n"
                "  Run:  python3 fb_scraper.py login\n"
                "  ...and log all the way through until your NEWS FEED is visible,\n"
                "  THEN press Enter in the terminal. Closing the browser early, or\n"
                "  stopping at a 2FA/checkpoint screen, saves no session.\n"
            )
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()

        n_posts = n_comments = 0
        meta = ProfileMeta(profile_url=args.url)

        try:
            print("  [1/2] walking the timeline...")
            urls, meta, feed_times = await collect_post_links(
                page, args.url, since, until, limit=args.limit)
            if args.limit:
                urls = urls[: args.limit]

            # Re-scraping a known post is the point (it refreshes last_seen and
            # detects deleted comments), so --skip-known is opt-in rather than
            # the default resume behaviour.
            if args.skip_known:
                before = len(urls)
                urls = [u for u in urls if not store.posts.get(extract_post_id(u))]
                print(f"  skip-known: {before - len(urls)} already stored, "
                      f"{len(urls)} new to scrape")

            # Keep this tab open: closing the last page in a headed persistent
            # context quits Chrome, which would kill the worker pages. Blank it
            # out to free the timeline's memory instead.
            try:
                await page.goto("about:blank", timeout=10_000)
            except Exception:
                pass

            if urls:
                if not args.no_comments and not args.headed:
                    print("\n  ! WARNING: comment pagination only works in a visible browser.")
                    print("    Headless caps at ~20 comments/post. For FULL depth (needed for")
                    print("    sentiment analysis) re-run with --headed.\n")
                print(f"  [2/2] scraping {len(urls)} posts with {args.workers} workers...")
                n_posts, n_comments = await worker_pool(
                    ctx, urls, since, until, args.workers,
                    not args.no_comments, not args.no_reactions,
                    store, run_id, profile, args.max_comments, errors,
                    feed_times,
                )
            else:
                print("\n  Nothing new to scrape in that window.")
        finally:
            # Always record the run, even on Ctrl-C, so what was already
            # collected stays accounted for.
            store.record_run({
                "run_id": run_id,
                "profile": profile,
                "profile_url": args.url,
                "platform": "facebook",
                "started_at": run_started.isoformat(timespec="seconds"),
                "finished_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                "duration_seconds": round(time.perf_counter() - t0, 1),
                "date_window": {"since": since.isoformat(timespec="seconds"),
                                "until": until.isoformat(timespec="seconds")},
                "mode": "headed" if args.headed else "headless",
                "workers": args.workers,
                "max_comments": args.max_comments,
                "posts_scanned": n_posts,
                "comments_new": store.stats["comments_new"],
                "comments_updated": store.stats["comments_updated"],
                "comments_disappeared": store.stats["comments_disappeared"],
                "followers": meta.followers,
                "followers_raw": meta.followers_raw,
                "errors": errors,
            })
            store.flush()
            try:
                await ctx.close()
            except Exception:
                pass  # context may already be dead; don't mask the real error

    dur = round(time.perf_counter() - t0, 1)
    mins, secs = divmod(dur, 60)
    print(f"\n  {meta.profile_name}: {meta.followers_raw} followers")
    print(f"  {n_posts} posts scanned, {n_comments} comments seen in {int(mins)}m {secs:.0f}s")
    print(f"  new={store.stats['comments_new']} updated={store.stats['comments_updated']} "
          f"disappeared={store.stats['comments_disappeared']}")
    print(f"  totals in store: {len(store.posts)} posts, {len(store.comments)} comments, "
          f"{len(store.users)} users")
    for name in ("posts", "comments", "users", "scrape_runs"):
        print(f"  -> {out/name}.jsonl  +  {out/name}.csv")
    print()


def cmd_mongo_load(args: argparse.Namespace) -> None:
    """Push the on-disk JSONL collections into MongoDB, unchanged."""
    out = Path(args.out)
    if not (out / "comments.jsonl").exists():
        sys.exit(f"  {out}/comments.jsonl not found -- run a scrape first.")
    db = connect_mongo_db(args.mongo_uri, args.mongo_db)
    store = Phase1Store(out, db)
    store.ensure_indexes()
    store.flush()
    print(f"  loaded {len(store.posts)} posts, {len(store.comments)} comments, "
          f"{len(store.users)} users, {len(store.runs)} runs into "
          f"{args.mongo_db} at {args.mongo_uri}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    lg = sub.add_parser("login", help="open a browser, log in by hand, save the session")
    lg.add_argument("--chrome-path", help="path to a Chrome/Chromium binary")

    s = sub.add_parser("scrape", help="scrape a page/profile")
    s.add_argument("--url", required=True, help="profile or page URL")
    s.add_argument("--profile-key", help="registry key, e.g. rahul_ghandhi -- "
                                         "selects this leader's selector "
                                         "overrides (see fb_doctor.py)")
    s.add_argument("--chrome-path", help="path to a Chrome/Chromium binary")
    s.add_argument("--days", type=int, help="look back N days (e.g. --days 2)")
    s.add_argument("--since", help="start date, YYYY-MM-DD")
    s.add_argument("--until", help="end date, YYYY-MM-DD (default: now)")
    s.add_argument("--workers", type=int, default=4,
                   help="concurrent post pages. 4 is safe; >6 risks a checkpoint.")
    s.add_argument("--limit", type=int, help="cap number of posts (for testing)")
    s.add_argument("--out", default=str(DEFAULT_OUT), help="output directory")
    s.add_argument("--headed", action="store_true", help="show the browser")
    s.add_argument("--no-comments", action="store_true", help="skip comment threads (much faster)")
    s.add_argument("--max-comments", type=int, default=0,
                   help="cap comments scraped per post (0 = all). Use with --headed; "
                        "high-traffic posts can have thousands.")
    s.add_argument("--mongo-uri", help="also store the four collections in MongoDB, "
                                       "e.g. mongodb://localhost:27017")
    s.add_argument("--mongo-db", default="facebook", help="MongoDB database name")
    s.add_argument("--no-reactions", action="store_true",
                   help="skip per-type reaction breakdown (faster, less block risk)")
    s.add_argument("--skip-known", action="store_true",
                   help="skip posts already in the store. Off by default: re-scraping "
                        "is what refreshes last_seen and detects deleted comments.")

    ml = sub.add_parser("mongo-load", help="load existing CSVs into MongoDB (nested)")
    ml.add_argument("--out", default=str(DEFAULT_OUT), help="directory holding the CSVs")
    ml.add_argument("--mongo-uri", default="mongodb://localhost:27017", help="MongoDB URI")
    ml.add_argument("--mongo-db", default="facebook", help="MongoDB database name")

    args = ap.parse_args()

    if args.cmd == "login":
        asyncio.run(cmd_login(args.chrome_path))
    elif args.cmd == "mongo-load":
        cmd_mongo_load(args)
    else:
        if not args.days and not args.since:
            ap.error("give either --days N or --since YYYY-MM-DD")
        asyncio.run(cmd_scrape(args))


if __name__ == "__main__":
    main()
