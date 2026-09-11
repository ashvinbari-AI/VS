#!/usr/bin/env python3
"""
Shared storage for Phase 1 of the pipeline.

Both fb_scraper.py and ig_scraper.py code against this exact contract:
`Phase1Store(out[, mongo_db])` with `upsert_post` / `upsert_comment` /
`upsert_user` / `mark_missing` / `record_run` / `flush` / `ensure_indexes`,
plus the module-level helpers `make_run_id` / `local_iso` / `utc_now` /
`resolve_threads`.

Four flat collections -- posts, comments, users, scrape_runs -- are kept in
memory as {id: doc} dicts and mirrored on every flush() to:
  * <out>/<name>.jsonl -- one JSON object per line, authoritative, and what
    a re-run reloads on the next construction so upserts merge instead of
    starting over.
  * <out>/<name>.csv -- the same rows flattened for a spreadsheet; any
    dict/list field (reactions, media_urls, errors, ...) is JSON-encoded
    into its cell rather than dropped.

A pymongo Database passed as `mongo_db` gets the same four collections
upserted into it on flush(), keyed the same way as the JSONL files.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def make_run_id(dt: datetime | None = None) -> str:
    dt = dt or datetime.now().astimezone()
    return dt.strftime("run_%Y%m%dT%H%M%S")


def local_iso(unix_ts: int) -> str:
    """Unix timestamp -> local-timezone ISO string, seconds precision."""
    return datetime.fromtimestamp(int(unix_ts)).astimezone().isoformat(timespec="seconds")


def resolve_threads(comments: list[dict]) -> None:
    """Fill thread_root_id / depth from parent_comment_id, in place.

    A root comment (no parent, or a parent that isn't in this batch) is its
    own thread root at depth 0. A reply's root is its parent's root, one
    level deeper -- walked iteratively per comment so a long reply chain
    never recurses, and a parent/child cycle (shouldn't happen, but the data
    is scraped off a live DOM) can't spin forever either.
    """
    by_id = {str(c["comment_id"]): c for c in comments}
    for c in comments:
        chain = []
        cur = c
        seen: set[str] = set()
        while cur.get("parent_comment_id") and str(cur["comment_id"]) not in seen:
            seen.add(str(cur["comment_id"]))
            parent = by_id.get(str(cur["parent_comment_id"]))
            if not parent:
                break
            chain.append(cur)
            cur = parent
        c["thread_root_id"] = str(cur["comment_id"])
        c["depth"] = len(chain)


class Phase1Store:
    """In-memory posts/comments/users/scrape_runs, mirrored to JSONL + CSV."""

    _KEY = {"posts": "post_id", "comments": "comment_id",
            "users": "user_id", "scrape_runs": "run_id"}

    def __init__(self, out: str | Path, mongo_db=None):
        self.out = Path(out)
        self.out.mkdir(parents=True, exist_ok=True)
        self.mongo_db = mongo_db
        self.posts: dict[str, dict] = {}
        self.comments: dict[str, dict] = {}
        self.users: dict[str, dict] = {}
        self.runs: dict[str, dict] = {}
        self.stats = {"comments_new": 0, "comments_updated": 0, "comments_disappeared": 0}
        for name, store in (("posts", self.posts), ("comments", self.comments),
                            ("users", self.users), ("scrape_runs", self.runs)):
            self._load(name, store)

    def _load(self, name: str, into: dict) -> None:
        """Reload a previous run's JSONL so upserts merge instead of starting over."""
        path = self.out / f"{name}.jsonl"
        if not path.exists():
            return
        key = self._KEY[name]
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    doc = json.loads(line)
                except json.JSONDecodeError:
                    continue
                k = doc.get(key)
                if k:
                    into[str(k)] = doc

    def ensure_indexes(self) -> None:
        """Mongo-only: unique indexes on each collection's id field."""
        if self.mongo_db is None:
            return
        for name, key in self._KEY.items():
            self.mongo_db[name].create_index(key, unique=True)

    def upsert_post(self, post: dict, run_id: str) -> None:
        pid = str(post["post_id"])
        now = utc_now().isoformat(timespec="seconds")
        existing = self.posts.get(pid)
        doc = dict(post)
        doc["first_seen_at"] = existing.get("first_seen_at", now) if existing else now
        doc["last_seen_at"] = now
        doc["last_run_id"] = run_id
        self.posts[pid] = doc

    def upsert_comment(self, comment: dict, run_id: str) -> None:
        cid = str(comment["comment_id"])
        now = utc_now().isoformat(timespec="seconds")
        existing = self.comments.get(cid)
        doc = dict(comment)
        doc["first_seen_at"] = existing.get("first_seen_at", now) if existing else now
        doc["last_seen_at"] = now
        doc["last_run_id"] = run_id
        doc["status"] = "active"
        self.comments[cid] = doc
        self.stats["comments_updated" if existing else "comments_new"] += 1

    def upsert_user(self, user_id: str, user_name: str = "", user_profile_url: str = "") -> None:
        if not user_id:
            return
        uid = str(user_id)
        now = utc_now().isoformat(timespec="seconds")
        existing = self.users.get(uid)
        doc = dict(existing) if existing else {"user_id": uid, "first_seen_at": now}
        doc["user_name"] = user_name or doc.get("user_name", "")
        doc["user_profile_url"] = user_profile_url or doc.get("user_profile_url", "")
        doc["last_seen_at"] = now
        self.users[uid] = doc

    def mark_missing(self, post_id: str, seen_ids: set, run_id: str) -> None:
        """A comment on this post that was seen before but not in this run's
        harvest is presumed deleted -- its status flips rather than being
        removed, so the history (and who said what) stays intact."""
        pid = str(post_id)
        seen = {str(s) for s in seen_ids}
        for cid, doc in self.comments.items():
            if str(doc.get("post_id")) != pid or cid in seen:
                continue
            if doc.get("status") == "disappeared":
                continue
            doc["status"] = "disappeared"
            doc["last_run_id"] = run_id
            self.stats["comments_disappeared"] += 1

    def record_run(self, run: dict) -> None:
        rid = str(run.get("run_id") or make_run_id())
        self.runs[rid] = run

    def flush(self) -> None:
        for name, store in (("posts", self.posts), ("comments", self.comments),
                            ("users", self.users), ("scrape_runs", self.runs)):
            self._write_jsonl(name, store)
            self._write_csv(name, store)
            if self.mongo_db is not None and store:
                self._mongo_upsert(name, store)

    def _write_jsonl(self, name: str, store: dict) -> None:
        path = self.out / f"{name}.jsonl"
        with path.open("w", encoding="utf-8") as fh:
            for doc in store.values():
                fh.write(json.dumps(doc, ensure_ascii=False, default=str) + "\n")

    def _write_csv(self, name: str, store: dict) -> None:
        path = self.out / f"{name}.csv"
        rows = list(store.values())
        if not rows:
            path.write_text("", encoding="utf-8")
            return
        fields: list[str] = []
        for row in rows:
            for k in row:
                if k not in fields:
                    fields.append(k)
        with path.open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
            w.writeheader()
            for row in rows:
                flat = {k: (json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v)
                        for k, v in row.items()}
                w.writerow(flat)

    def _mongo_upsert(self, name: str, store: dict) -> None:
        key = self._KEY[name]
        coll = self.mongo_db[name]
        for doc in store.values():
            coll.update_one({key: doc.get(key)}, {"$set": doc}, upsert=True)
