#!/usr/bin/env python3
"""
Instagram profile scraper -- the second source for Phase 1 of the pipeline.

Same contract as fb_scraper.py, deliberately: `login` once, then `scrape --url
--out --days/--since/--until`, and the output is the four collections of
scrape_schema.md (posts / comments / users / scrape_runs) written by the shared
schema_store.py. Phase 1 flattens either scraper's `comments.csv` + `posts.csv`
with the same code, so everything downstream is platform-blind.

Usage
-----
  # 1. one-time: log in by hand, cookies are saved to ./ig_session/cookies.pkl
  python pipeline/vendor/ig_scraper.py login

  # 2. confirm the saved session still authenticates
  python pipeline/vendor/ig_scraper.py check

  # 3. scrape
  python pipeline/vendor/ig_scraper.py scrape \
        --url https://www.instagram.com/narendramodi/ --days 7 --out data/raw/scrape/instagram
  python pipeline/vendor/ig_scraper.py scrape \
        --url https://www.instagram.com/narendramodi/ \
        --since 2026-07-19 --until 2026-07-21 --headed --excel comments.xlsx

Three things differ from Facebook, and they shape everything below.

  * **Selenium, not Playwright.** This is the working scraper for this target;
    porting selectors that cannot be tested against a logged-in Instagram would
    trade a scraper that runs for one that reads more consistently. Needs
    `pip install selenium webdriver-manager`.
  * **No comment ids and no per-comment timestamps.** Instagram's DOM gives a
    column of text, not a thread of documents. Comments are cut out of that
    text (see parse_comment_blocks) and keyed by a hash of post + author + text,
    which is stable across runs -- so first_seen / last_seen / deletion tracking
    in schema_store still work, and re-scraping a post does not duplicate it.
    `comment_timestamp` is genuinely unavailable and is left empty rather than
    guessed at; `post_timestamp` is exact, and is what the time window filters on.
  * **The grid carries no dates.** A profile's post list must be walked
    newest-first and stopped when a post falls out of the window, which is why
    posts are opened one at a time rather than collected up front. Pinned posts
    are old by definition, so they are skipped instead of ending the walk.

Instagram's class names are generated and change often. Every selector lives in
the SELECTORS block below -- when something silently returns empty, look there
first, and run with --headed to watch it work.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import pickle
import random
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Some environments export a CA bundle path that no longer exists, which turns
# every webdriver_manager download into an opaque TLS error. Unset rather than
# repair: the driver download is the only thing here that talks TLS from python.
for _var in ("CURL_CA_BUNDLE", "REQUESTS_CA_BUNDLE", "SSL_CERT_FILE"):
    os.environ.pop(_var, None)

from schema_store import Phase1Store, make_run_id   # noqa: E402

# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------

SESSION_DIR = Path("ig_session")
COOKIES_FILE = SESSION_DIR / "cookies.pkl"
DEFAULT_OUT = Path("output")

# How to spell this script back to whoever has to re-run it, from where they are.
try:
    SELF = Path(__file__).resolve().relative_to(Path.cwd())
except ValueError:
    SELF = Path(__file__).name

PAGE_PAUSE = (3.0, 5.0)        # random.uniform range, seconds -- after a profile load
POST_PAUSE = (1.5, 2.5)        # before opening a post tab
SCROLL_PAUSE = 1.0             # inside the comment column
MAX_COMMENT_SCROLLS = 100
NO_GROWTH_ROUNDS = 4           # stop scrolling after this many static rounds
NAV_TIMEOUT_S = 15

SELECTORS = {
    # The comment column and the caption share this class; the caption is the
    # first block, which parse_comment_blocks strips back off.
    "comment_block": '//div[@class="x5yr21d xw2csxc x1odjw0f x1n2onr6"]',
    "caption": '(//div[@class="x5yr21d xw2csxc x1odjw0f x1n2onr6"]//following::span)[1]',
    "caption_fallback": '(//h1/following::span)[1]',
    "time": "//time",
    "likes": [
        '(//section[@class="x6s0dn4 xrvj5dj x1o61qjw"]//child::span[@role="button"])[1]',
        '//a[contains(@href, "/liked_by/")]//span',
        '//span[contains(text(), "likes")]',
    ],
    "comment_count": ('(//section[@class="x6s0dn4 xrvj5dj x1o61qjw"]'
                      '//child::span[@role="button"])[2]'
                      ' | //span[contains(text(), "comments")]'),
    "post_links": "//a[contains(@href, '/p/') or contains(@href, '/reel/')]",
    "username": ["//header//h2", "//h2", "//h1"],
    "bio": ('//div[@class="_ap3a _aaco _aacw _aacz _aada _aade"]'
            ' | //header//section//div[contains(@class, "ap3a")]'),
    "pinned": [
        ".//*[local-name()='svg' and @aria-label='Pinned']",
        ".//*[local-name()='svg']/*[local-name()='title' and contains(text(), 'Pinned')]",
        ".//span[contains(@class, 'pinned')]",
        ".//*[contains(@aria-label, 'Pinned')]",
    ],
    "login_inputs": "//input[@name='username' or @name='password']",
    "login_links": "//a[contains(@href, '/accounts/login')]",
}

# The one JS that has to exist: Instagram's comment list is a scroll container
# with no stable class, found by its overflow style and height instead.
FIND_SCROLL_BOX = """
let s = null;
document.querySelectorAll('div, ul').forEach(el => {
  const oy = window.getComputedStyle(el).overflowY;
  if ((oy === 'auto' || oy === 'scroll') && el.clientHeight > 200) s = el;
});
return s;
"""

LOAD_MORE = ("//li//div[@role='button']//span[contains(text(), 'View all') or "
             "contains(text(), 'View more') or @aria-label='Load more comments']")


_sel = None


def _selenium():
    """Import selenium lazily, with an error an operator can act on.

    Lazy so that `has_session_cookie()` -- which the control API calls on every
    health check -- costs nothing on a machine where selenium is not installed.
    """
    global _sel
    if _sel is not None:
        return _sel
    from types import SimpleNamespace
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.support.ui import WebDriverWait
        from webdriver_manager.chrome import ChromeDriverManager
    except ImportError as e:
        sys.exit(
            f"\n  {e.name} is not installed -- the Instagram scraper needs it.\n"
            f"    pip install selenium webdriver-manager\n"
            f"  (The Facebook scraper uses Playwright and is unaffected.)\n")
    _sel = SimpleNamespace(webdriver=webdriver, Options=Options, Service=Service,
                           By=By, EC=EC, Wait=WebDriverWait,
                           driver_manager=ChromeDriverManager)
    return _sel


def jitter(rng: tuple[float, float]) -> None:
    time.sleep(random.uniform(*rng))


# --------------------------------------------------------------------------
# Session
# --------------------------------------------------------------------------


def _driver(headed: bool, chrome_path: str | None = None):
    s = _selenium()
    opts = s.Options()
    opts.add_argument("--incognito")          # cookies come from the pickle, not a profile dir
    opts.add_argument("--disable-blink-features=AutomationControlled")
    if headed:
        opts.add_argument("--start-maximized")
    else:
        opts.add_argument("--headless=new")
        opts.add_argument("--disable-gpu")
        opts.add_argument("--window-size=1920,1080")
    # CHROME_PATH is how the docker image points this at a wrapper that adds
    # --no-sandbox: chrome's sandbox unshares a user namespace, which docker's
    # seccomp profile denies, so Chrome aborts before it opens a window. An
    # explicit --chrome-path still wins, and outside a container the variable
    # is unset and chromedriver finds Chrome the way it always did.
    chrome_path = chrome_path or os.environ.get("CHROME_PATH")
    if chrome_path:
        opts.binary_location = chrome_path

    try:
        drv = s.webdriver.Chrome(
            service=s.Service(s.driver_manager().install()), options=opts)
    except Exception as e:
        sys.exit(f"\n  Could not start Chrome: {str(e).splitlines()[0]}\n"
                 f"  Point at a browser explicitly, e.g.:\n"
                 f"    --chrome-path /usr/bin/google-chrome\n")
    drv.execute_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return drv


def save_cookies(driver) -> int:
    SESSION_DIR.mkdir(parents=True, exist_ok=True)
    cookies = driver.get_cookies()
    with COOKIES_FILE.open("wb") as f:
        pickle.dump(cookies, f)
    return len(cookies)


def load_cookies(driver) -> bool:
    """Replay the saved cookies into a driver already sitting on instagram.com."""
    if not COOKIES_FILE.exists():
        return False
    try:
        with COOKIES_FILE.open("rb") as f:
            cookies = pickle.load(f)
    except (OSError, pickle.UnpicklingError):
        return False
    if not isinstance(cookies, list):
        return False
    for c in cookies:
        try:
            driver.add_cookie(c)
        except Exception:
            pass          # one stale/foreign-domain cookie must not sink the rest
    return True


def has_session_cookie() -> bool:
    """`sessionid` is the one cookie that makes a session authenticated.

    A cheap file-level check -- what /api/health calls -- as opposed to `check`,
    which actually opens a browser and asks Instagram.
    """
    if not COOKIES_FILE.exists():
        return False
    try:
        with COOKIES_FILE.open("rb") as f:
            cookies = pickle.load(f)
    except (OSError, pickle.UnpicklingError):
        return False
    return isinstance(cookies, list) and any(
        isinstance(c, dict) and c.get("name") == "sessionid"
        and str(c.get("value", "")).strip() for c in cookies)


def cmd_login(args) -> None:
    driver = _driver(headed=True, chrome_path=args.chrome_path)
    try:
        driver.get("https://www.instagram.com/accounts/login/")
        print("\n  A browser window is open.")
        print("  Log in to Instagram there (solve any captcha / 2FA).")
        print("  Wait until your FEED is actually visible, then come back here")
        print("  and press Enter.\n")
        input("  Press Enter when logged in... ")
        n = save_cookies(driver)
    finally:
        try:
            driver.quit()
        except Exception:
            pass

    if has_session_cookie():
        print(f"\n  Login confirmed. {n} cookies saved to {COOKIES_FILE} -- "
              f"you can now run `scrape`.\n")
    else:
        sys.exit("\n  Login NOT saved -- no `sessionid` cookie was set.\n"
                 "  You probably pressed Enter before the feed finished loading,\n"
                 "  or the login stopped at a checkpoint. Run `login` again.\n")


def session_is_live(headed: bool = False, chrome_path: str | None = None) -> bool:
    """Do the saved cookies still produce a logged-in session?

    Loads a page that only exists behind the login wall; anything that smells of
    the login form means no.
    """
    if not has_session_cookie():
        return False
    By = _selenium().By
    driver = _driver(headed=headed, chrome_path=chrome_path)
    try:
        driver.get("https://www.instagram.com/")
        jitter((2, 3))
        load_cookies(driver)
        driver.refresh()
        jitter(PAGE_PAUSE)

        driver.get("https://www.instagram.com/accounts/edit/")
        jitter((2, 4))

        if "accounts/login" in (driver.current_url or "").lower():
            return False
        if driver.find_elements(By.XPATH, SELECTORS["login_inputs"]):
            return False
        if driver.find_elements(By.XPATH, SELECTORS["login_links"]):
            return False
        return True
    except Exception:
        return False
    finally:
        try:
            driver.quit()
        except Exception:
            pass


def cmd_check(args) -> None:
    if not COOKIES_FILE.exists():
        sys.exit(f"\n  No session at {COOKIES_FILE}.\n"
                 f"  Run:  python {SELF} login\n")
    ok = session_is_live(headed=args.headed, chrome_path=args.chrome_path)
    print(f"\n  {COOKIES_FILE}: "
          f"{'session is live' if ok else 'cookies are stale -- log in again'}\n")
    if not ok:
        sys.exit(1)


# --------------------------------------------------------------------------
# Parsing helpers
# --------------------------------------------------------------------------


def parse_count(text: str) -> int:
    """'3.3K' / '1,234 likes' / '1.2M' -> int. 0 when there is no number."""
    m = re.search(r"([\d,.]+)\s*([KkMm])?", str(text or ""))
    if not m:
        return 0
    num = m.group(1)
    mult = {"k": 1_000, "m": 1_000_000}.get((m.group(2) or "").lower(), 1)
    try:
        return int(float(num.replace(",", "")) * mult)
    except ValueError:
        return 0


def shortcode(url: str) -> str:
    m = re.search(r"/(?:p|reel|tv)/([^/?#]+)", str(url or ""))
    return m.group(1) if m else ""


def post_id_for(url: str) -> str:
    """`ig_<shortcode>`. Prefixed so a Facebook and an Instagram scrape can be
    concatenated in one frame without two different posts sharing an id."""
    return f"ig_{shortcode(url) or hashlib.sha1(url.encode()).hexdigest()[:11]}"


def comment_id_for(post_id: str, user: str, text: str) -> str:
    """Instagram publishes no comment id, so make one that is stable across runs.

    Author + text under one post: the same comment hashes to the same id next
    week, which is what lets schema_store recognise it rather than store a
    duplicate -- and lets a deleted comment be noticed by its absence.
    """
    h = hashlib.sha1(f"{user}\x00{text}".encode("utf-8")).hexdigest()[:16]
    return f"{post_id}_c{h}"


def user_id_for(username: str) -> str:
    return f"ig_{username}" if username else ""


def normalise_url(href: str) -> str:
    """One canonical permalink per post: no query string, reels as /p/."""
    return str(href or "").split("?")[0].replace("/reel/", "/p/").rstrip("/") + "/"


def is_meta_line(line: str) -> bool:
    """Chrome, not content: 'Reply', '2 likes', 'View all 5 replies', '3h'."""
    text = line.strip().lower()
    if not text:
        return True
    if text in {"reply", "see translation", "translate", "verified"}:
        return True
    if re.fullmatch(r"\d+\s*(like|likes)", text):
        return True
    if re.fullmatch(r"(view all\s+\d+\s+replies|view replies|view more comments)", text):
        return True
    if re.fullmatch(r"\d+\s*(s|m|h|d|w)", text):
        return True
    if "comments from facebook" in text:
        return True
    return False


def looks_like_username(line: str) -> bool:
    return bool(re.fullmatch(r"[a-zA-Z0-9._]{2,40}", line.strip()))


def clean_caption(caption: str) -> str:
    """Drop the 'username / 3d' header Instagram prefixes onto the caption."""
    lines = [x.strip() for x in (caption or "").splitlines() if x.strip()]
    if lines and looks_like_username(lines[0]):
        lines = lines[1:]
    if lines and re.fullmatch(r"\d+\s*(s|m|h|d|w)", lines[0].lower()):
        lines = lines[1:]
    return "\n".join(lines).strip()


def parse_comment_blocks(blocks: list[str], caption: str) -> list[dict]:
    """Turn the comment column's text into {user, text} records.

    Instagram renders a comment as a run of lines -- author, then the comment,
    then a timestamp, a like count and 'Reply'. There is no element boundary to
    key on inside a block, so the author line is the delimiter: a line that is
    only a username ends the previous comment and starts the next. Block
    boundaries flush too, which is what keeps two short comments from merging
    when the DOM does give one element per comment.

    The caption shares the comment column's class and so arrives as a block of
    its own. It is dropped by comparing text, not by dropping the first block: a
    post with no comments has no other block, and Instagram truncates a long
    caption there ("... more"), which is why a prefix counts as a match.
    """
    rows: list[dict] = []
    user = ""
    buf: list[str] = []

    def flush() -> None:
        nonlocal buf
        text = " ".join(buf).strip()
        buf = []
        if text and text not in {c["text"] for c in rows if c["user"] == user}:
            rows.append({"user": user, "text": text})

    for block in blocks:
        flush()
        for line in [x.strip() for x in block.splitlines() if x.strip()]:
            if is_meta_line(line):
                continue
            if looks_like_username(line):
                flush()
                user = line
                continue
            buf.append(line)
    flush()

    cap = _squash(caption)
    return [r for r in rows if r["text"] and not _is_caption(r["text"], cap)]


def _squash(text: str) -> str:
    return " ".join(str(text or "").split())


def _is_caption(text: str, caption: str) -> bool:
    t = _squash(text)
    if not caption or not t:
        return False
    # Exact, or the truncated head of it. The length floor keeps a two-word
    # comment that happens to open the caption ("Jai Hind") from being dropped.
    return t == caption or (len(t) >= 30 and caption.startswith(t))


def parse_window(args) -> tuple[datetime, datetime]:
    """--days N, or --since/--until, as an aware [since, until] pair.

    UTC because that is what Instagram stamps its <time datetime> with; the
    comparison is against that attribute and nothing else.
    """
    now = datetime.now(timezone.utc)
    if args.days:
        return now - timedelta(days=args.days), now
    since = (datetime.fromisoformat(args.since).replace(tzinfo=timezone.utc)
             if args.since else now - timedelta(days=7))
    until = (datetime.fromisoformat(args.until).replace(
                 hour=23, minute=59, second=59, tzinfo=timezone.utc)
             if args.until else now)
    return since, until


# --------------------------------------------------------------------------
# Extraction
# --------------------------------------------------------------------------


def extract_post_meta(driver, url: str) -> dict:
    """Caption, timestamp and counts off an open post page. Fast: no scrolling."""
    s = _selenium()
    By = s.By
    out = {"post_url": url, "caption": "", "likes": 0, "comment_count": 0,
           "timestamp": "", "author": ""}
    try:
        s.Wait(driver, NAV_TIMEOUT_S).until(
            s.EC.presence_of_element_located((By.XPATH, SELECTORS["time"])))
        out["timestamp"] = driver.find_element(
            By.XPATH, SELECTORS["time"]).get_attribute("datetime") or ""
    except Exception:
        return out          # no timestamp means no window decision -- caller skips

    raw_caption = ""
    for xp in (SELECTORS["caption"], SELECTORS["caption_fallback"]):
        try:
            raw_caption = driver.find_element(By.XPATH, xp).text
            if raw_caption:
                break
        except Exception:
            continue
    out["caption"] = clean_caption(raw_caption)
    # The line clean_caption just stripped is the post's author.
    first = [x.strip() for x in (raw_caption or "").splitlines() if x.strip()]
    if first and looks_like_username(first[0]):
        out["author"] = first[0]

    for xp in SELECTORS["likes"]:
        try:
            n = parse_count(driver.find_element(By.XPATH, xp).text)
            if n:
                out["likes"] = n
                break
        except Exception:
            continue

    try:
        out["comment_count"] = parse_count(
            driver.find_element(By.XPATH, SELECTORS["comment_count"]).text)
    except Exception:
        pass
    return out


def harvest_comments(driver, max_comments: int = 0) -> list[str]:
    """Scroll the comment column to the end, then read every block of text.

    Returns raw block texts; parse_comment_blocks turns them into comments. The
    scroll stops when the container has not grown for NO_GROWTH_ROUNDS rounds --
    Instagram lazy-loads, so one static round means nothing.
    """
    By = _selenium().By
    try:
        box = driver.execute_script(FIND_SCROLL_BOX)
        if box:
            last_h = driver.execute_script("return arguments[0].scrollHeight", box)
            static = 0
            for _ in range(MAX_COMMENT_SCROLLS):
                driver.execute_script(
                    "arguments[0].scrollTo(0, arguments[0].scrollHeight);", box)
                time.sleep(SCROLL_PAUSE)
                try:
                    for btn in driver.find_elements(By.XPATH, LOAD_MORE):
                        driver.execute_script("arguments[0].click();", btn)
                except Exception:
                    pass
                new_h = driver.execute_script("return arguments[0].scrollHeight", box)
                if new_h == last_h:
                    static += 1
                    if static >= NO_GROWTH_ROUNDS:
                        break
                else:
                    static = 0
                last_h = new_h
                if max_comments:
                    seen = len(driver.find_elements(By.XPATH,
                                                    SELECTORS["comment_block"]))
                    if seen >= max_comments + 1:      # +1: the caption block
                        break

        blocks = []
        for el in driver.find_elements(By.XPATH, SELECTORS["comment_block"]):
            try:
                t = el.text.strip()
            except Exception:
                continue
            if t:
                blocks.append(t)
        return blocks
    except Exception as e:
        print(f"  ! comment error: {type(e).__name__}: {e}")
        return []


def is_pinned(el) -> bool:
    By = _selenium().By
    for xp in SELECTORS["pinned"]:
        try:
            if el.find_elements(By.XPATH, xp):
                return True
        except Exception:
            continue
    return False


def profile_header(driver, profile_url: str) -> dict:
    """Username, bio and the follower/post counts, off the profile page."""
    By = _selenium().By
    slug = re.sub(r"/+$", "", profile_url).split("/")[-1].split("?")[0]
    out = {"username": slug, "bio": "", "followers": 0, "followers_raw": "",
           "posts_count": 0}
    try:
        text = (driver.execute_script("return document.body.innerText") or "").lower()
    except Exception:
        text = ""

    for xp in SELECTORS["username"]:
        try:
            el = driver.find_element(By.XPATH, xp)
            if el.is_displayed() and el.text.strip():
                out["username"] = el.text.strip()
                break
        except Exception:
            continue

    f = re.search(r"([\d,.]+[KMkm]?)\s*follower", text)
    p = re.search(r"([\d,.]+[KMkm]?)\s*post", text)
    if f:
        out["followers_raw"] = f.group(1).upper()
        out["followers"] = parse_count(f.group(1))
    if p:
        out["posts_count"] = parse_count(p.group(1))

    try:
        out["bio"] = driver.find_element(By.XPATH, SELECTORS["bio"]).text.strip()
    except Exception:
        pass
    return out


# --------------------------------------------------------------------------
# Documents
# --------------------------------------------------------------------------


def build_post(meta: dict, url: str, profile: str, header: dict,
               n_comments: int, post_type: str = "post") -> dict:
    """The posts document, field-for-field what fb_scraper writes."""
    return {
        "post_id": post_id_for(url),
        "profile": profile,
        "page_id": header.get("username", ""),
        "platform": "instagram",
        "post_url": url,
        # Passed in, not read off `url`: normalise_url has already rewritten
        # /reel/ to /p/ so that one post has one permalink.
        "post_type": post_type,
        "caption": meta.get("caption", ""),
        "post_timestamp": meta.get("timestamp", ""),
        "post_timestamp_raw": meta.get("timestamp", ""),
        "author": meta.get("author") or header.get("username", ""),
        # Instagram publishes one number, not a breakdown; `total` is the field
        # every consumer reads, and inventing per-type counts would be a lie.
        "reactions": {"like": meta.get("likes", 0), "total": meta.get("likes", 0)},
        "comment_count": meta.get("comment_count", 0) or n_comments,
        "share_count": 0,
        "view_count": 0,
        "media_urls": [],
        "scrape_url": url,
        "comments_captured": n_comments,
    }


def build_comment(row: dict, post_id: str, post_url: str) -> dict:
    user = row["user"]
    text = row["text"]
    cid = comment_id_for(post_id, user, text)
    return {
        "comment_id": cid,
        "post_id": post_id,
        "parent_comment_id": None,
        # Replies are rendered inline in the same column with no marker this
        # scraper can see, so every comment is its own root at depth 0.
        "thread_root_id": cid,
        "depth": 0,
        "user_id": user_id_for(user),
        "user_id_raw": "",
        "user_name": user,
        "user_profile_url": f"https://www.instagram.com/{user}/" if user else "",
        "comment_text": text,
        "comment_timestamp": "",          # not exposed per comment -- see module docstring
        "like_count": 0,
        "reply_count": 0,
        "media_url": "",
        "comment_url": post_url,
        "is_edited": False,
        "is_pinned": False,
        "author_liked": False,
        "source_dialect": "",
    }


def write_excel(store: Phase1Store, path: Path) -> None:
    """The flat one-row-per-comment sheet, for eyeballing outside the pipeline."""
    try:
        import pandas as pd
    except ImportError:
        print("  ! pandas not installed -- skipping --excel")
        return
    posts = {str(p["post_id"]): p for p in store.posts.values()}
    rows = []
    for c in store.comments.values():
        p = posts.get(str(c.get("post_id")), {})
        rows.append({
            "post_url": p.get("post_url", ""),
            "caption": p.get("caption", ""),
            "post_timestamp": p.get("post_timestamp", ""),
            "likes_count": (p.get("reactions") or {}).get("total", 0),
            "comments_count": p.get("comment_count", 0),
            "comment_username": c.get("user_name", ""),
            "comment_text": c.get("comment_text", ""),
            "status": c.get("status", ""),
        })
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_excel(path, index=False)
    print(f"  -> {path}  ({len(rows)} comment rows)")


# --------------------------------------------------------------------------
# The walk
# --------------------------------------------------------------------------


def cmd_scrape(args) -> None:
    s = _selenium()
    By = s.By
    since, until = parse_window(args)

    if not has_session_cookie():
        sys.exit(f"\n  No Instagram session at {COOKIES_FILE}.\n\n"
                 f"  Logged out, Instagram serves a login wall and no comments at\n"
                 f"  all, so there is nothing to scrape.\n\n"
                 f"  Run:  python {SELF} login\n")

    run_started = datetime.now().astimezone()
    run_id = make_run_id(run_started)
    t0 = time.perf_counter()
    profile = re.sub(r"/+$", "", args.url).split("/")[-1].split("?")[0]

    out = Path(args.out)
    store = Phase1Store(out)
    store.ensure_indexes()
    errors: list[str] = []

    print(f"\n  target : {args.url}")
    print(f"  window : {since:%Y-%m-%d %H:%M} -> {until:%Y-%m-%d %H:%M}")
    print(f"  run_id : {run_id}")
    print()

    driver = _driver(headed=args.headed, chrome_path=args.chrome_path)
    n_posts = n_comments = 0
    header = {"username": profile, "followers": 0, "followers_raw": "", "bio": ""}

    try:
        driver.get("https://www.instagram.com/")
        jitter((3, 5))
        load_cookies(driver)
        driver.refresh()
        jitter(PAGE_PAUSE)

        print("  [1/2] opening the profile...")
        driver.get(args.url)
        try:
            s.Wait(driver, NAV_TIMEOUT_S).until(
                lambda d: d.execute_script("return document.readyState") == "complete")
        except Exception:
            pass
        jitter((4, 6))

        if driver.find_elements(By.XPATH, SELECTORS["login_inputs"]):
            sys.exit("\n  Instagram served the login form -- the saved session is\n"
                     f"  stale. Run:  python {SELF} login\n")

        header = profile_header(driver, args.url)
        print(f"  {header['username']}: {header['followers_raw'] or '?'} followers, "
              f"{header['posts_count'] or '?'} posts")

        print("  [2/2] walking the grid, newest first...")
        seen_urls: set[str] = set()
        stop = False
        last_height = driver.execute_script("return document.body.scrollHeight")

        while not stop:
            links = driver.find_elements(By.XPATH, SELECTORS["post_links"])
            fresh = []
            for el in links:
                try:
                    raw = el.get_attribute("href") or ""
                except Exception:
                    continue
                href = normalise_url(raw)
                if href and "/p/" in href and href not in seen_urls:
                    seen_urls.add(href)
                    fresh.append((href, is_pinned(el),
                                  "reel" if "/reel/" in raw else "post"))

            for url, pinned, post_type in fresh:
                if args.limit and n_posts >= args.limit:
                    print(f"  limit of {args.limit} posts reached.")
                    stop = True
                    break

                got = scrape_one_post(driver, url, pinned, post_type, since, until,
                                      store, run_id, profile, header, args, errors)
                if got is None:                 # older than the window, not pinned
                    stop = True
                    break
                if got >= 0:
                    n_posts += 1
                    n_comments += got

            if stop:
                break

            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            jitter(PAGE_PAUSE)
            height = driver.execute_script("return document.body.scrollHeight")
            if height == last_height:
                break                            # the grid has stopped growing
            last_height = height

    except KeyboardInterrupt:
        print("\n  interrupted -- keeping what was already collected.")
    finally:
        store.record_run({
            "run_id": run_id,
            "profile": profile,
            "profile_url": args.url,
            "platform": "instagram",
            "started_at": run_started.isoformat(timespec="seconds"),
            "finished_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "duration_seconds": round(time.perf_counter() - t0, 1),
            "date_window": {"since": since.isoformat(timespec="seconds"),
                            "until": until.isoformat(timespec="seconds")},
            "mode": "headed" if args.headed else "headless",
            "workers": 1,
            "max_comments": args.max_comments,
            "posts_scanned": n_posts,
            "comments_new": store.stats["comments_new"],
            "comments_updated": store.stats["comments_updated"],
            "comments_disappeared": store.stats["comments_disappeared"],
            "followers": header.get("followers", 0),
            "followers_raw": header.get("followers_raw", ""),
            "errors": errors,
        })
        store.flush()
        try:
            driver.quit()
        except Exception:
            pass

    if args.excel:
        write_excel(store, Path(args.excel))

    mins, secs = divmod(round(time.perf_counter() - t0, 1), 60)
    print(f"\n  {header.get('username', profile)}: "
          f"{header.get('followers_raw') or '?'} followers")
    print(f"  {n_posts} posts scanned, {n_comments} comments seen in "
          f"{int(mins)}m {secs:.0f}s")
    print(f"  new={store.stats['comments_new']} "
          f"updated={store.stats['comments_updated']} "
          f"disappeared={store.stats['comments_disappeared']}")
    print(f"  totals in store: {len(store.posts)} posts, "
          f"{len(store.comments)} comments, {len(store.users)} users")
    for name in ("posts", "comments", "users", "scrape_runs"):
        print(f"  -> {out/name}.jsonl  +  {out/name}.csv")
    print()


def scrape_one_post(driver, url, pinned, post_type, since, until, store, run_id,
                    profile, header, args, errors) -> int | None:
    """Scrape one post in a background tab and commit it.

    Returns the comment count, -1 for a post skipped inside the window, or None
    for "this post is older than the window" -- which ends the walk, because the
    grid is in date order and everything after it is older still.
    """
    main = driver.current_window_handle
    jitter(POST_PAUSE)
    driver.execute_script("window.open(arguments[0], '_blank');", url)
    driver.switch_to.window(driver.window_handles[-1])

    def back(value):
        if len(driver.window_handles) > 1:
            driver.close()
        driver.switch_to.window(main)
        return value

    try:
        meta = extract_post_meta(driver, url)
        if not meta["timestamp"]:
            errors.append(f"unreadable: {url}")
            print(f"  ! no timestamp on {url} -- skipped")
            return back(-1)

        ts = datetime.fromisoformat(meta["timestamp"].replace("Z", "+00:00"))
        if ts > until:
            print(f"  · {ts:%Y-%m-%d} newer than the window -- skipped")
            return back(-1)
        if ts < since:
            # Pinned posts sit at the top of the grid regardless of age, so one
            # of them being old says nothing about the posts below it.
            if pinned:
                print(f"  · {ts:%Y-%m-%d} pinned and older than the window -- skipped")
                return back(-1)
            print(f"  · {ts:%Y-%m-%d} older than the window -- stopping.")
            return back(None)

        blocks = [] if args.no_comments else harvest_comments(driver, args.max_comments)
        rows = parse_comment_blocks(blocks, meta["caption"])
        if args.max_comments:
            rows = rows[:args.max_comments]

        post_id = post_id_for(url)
        comments = [build_comment(r, post_id, url) for r in rows]
        store.upsert_post(
            build_post(meta, url, profile, header, len(comments), post_type),
            run_id)
        seen_ids = set()
        for c in comments:
            store.upsert_comment(c, run_id)
            seen_ids.add(c["comment_id"])
            store.upsert_user(c["user_id"], c["user_name"], c["user_profile_url"])
        store.mark_missing(post_id, seen_ids, run_id)
        store.flush()      # commit per post: an interrupt keeps what was collected

        claimed = meta.get("comment_count") or 0
        pct = f"{100 * len(comments) / claimed:.0f}%" if claimed else "n/a"
        print(f"  · {ts:%Y-%m-%d %H:%M}  {meta['likes']} likes, "
              f"{len(comments)}/{claimed or len(comments)} comments ({pct})  (saved)")
        return back(len(comments))

    except Exception as e:
        errors.append(f"{type(e).__name__} on {url}: {e}")
        print(f"  ! error on {url}: {type(e).__name__}: {e}")
        return back(-1)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")

    lg = sub.add_parser("login", help="open a browser, log in by hand, save cookies")
    lg.add_argument("--chrome-path", help="path to a Chrome/Chromium binary")
    lg.set_defaults(func=cmd_login)

    ck = sub.add_parser("check", help="do the saved cookies still authenticate?")
    ck.add_argument("--chrome-path", help="path to a Chrome/Chromium binary")
    ck.add_argument("--headed", action="store_true", help="show the browser")
    ck.set_defaults(func=cmd_check)

    s = sub.add_parser("scrape", help="scrape an Instagram profile")
    s.add_argument("--url", required=True, help="profile URL")
    s.add_argument("--chrome-path", help="path to a Chrome/Chromium binary")
    s.add_argument("--days", type=int, help="look back N days (e.g. --days 7)")
    s.add_argument("--since", help="start date, YYYY-MM-DD")
    s.add_argument("--until", help="end date, YYYY-MM-DD (default: now)")
    s.add_argument("--limit", type=int, help="cap number of posts (for testing)")
    s.add_argument("--out", default=str(DEFAULT_OUT), help="output directory")
    s.add_argument("--headed", action="store_true", help="show the browser")
    s.add_argument("--no-comments", action="store_true",
                   help="posts only, no comment threads (much faster)")
    s.add_argument("--max-comments", type=int, default=0,
                   help="stop after N comments per post (0 = all)")
    s.add_argument("--excel", help="also write a flat one-row-per-comment .xlsx here")
    s.set_defaults(func=cmd_scrape)

    args = ap.parse_args()
    if not getattr(args, "func", None):
        ap.print_help()
        return
    args.func(args)


if __name__ == "__main__":
    main()
