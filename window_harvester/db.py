"""High-throughput resumable SQLite WAL-mode store for 500,000+ deduplicated domains."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from window_harvester.models import CandidateRecord, VerifyStatus

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS domains (
    domain            TEXT PRIMARY KEY,
    url               TEXT NOT NULL,
    business_name     TEXT,
    categories        TEXT NOT NULL DEFAULT '[]',
    country           TEXT,
    region            TEXT,
    city              TEXT,
    postcode          TEXT,
    address           TEXT,
    phone             TEXT,
    lat               REAL,
    lon               REAL,
    sources           TEXT NOT NULL DEFAULT '[]',
    source_count      INTEGER NOT NULL DEFAULT 1,
    confidence        REAL NOT NULL DEFAULT 0.7,
    sample_query      TEXT,
    page_title        TEXT,
    meta_description  TEXT,
    http_status       INTEGER,
    verified          INTEGER NOT NULL DEFAULT 0,
    final_url         TEXT,
    discovered_at     TEXT NOT NULL,
    updated_at        TEXT NOT NULL,
    verified_at       TEXT
);

CREATE INDEX IF NOT EXISTS idx_domains_country    ON domains(country);
CREATE INDEX IF NOT EXISTS idx_domains_confidence ON domains(confidence DESC);
CREATE INDEX IF NOT EXISTS idx_domains_verified   ON domains(verified);
CREATE INDEX IF NOT EXISTS idx_domains_sources    ON domains(source_count DESC);

CREATE TABLE IF NOT EXISTS checkpoints (
    source       TEXT NOT NULL,
    task_key     TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'done',
    items_found  INTEGER NOT NULL DEFAULT 0,
    meta         TEXT,
    updated_at   TEXT NOT NULL,
    PRIMARY KEY (source, task_key)
);

CREATE TABLE IF NOT EXISTS company_queue (
    company_id    TEXT PRIMARY KEY,
    company_name  TEXT NOT NULL,
    country       TEXT NOT NULL,
    locality      TEXT,
    postcode      TEXT,
    sic_code      TEXT,
    category      TEXT,
    status        TEXT NOT NULL DEFAULT 'pending',
    resolved_domain TEXT,
    updated_at    TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_company_queue_status ON company_queue(status, country);
"""


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _merge_json_list(existing_json: str | None, additions: list[str]) -> list[str]:
    items: list[str] = []
    if existing_json:
        try:
            parsed = json.loads(existing_json)
            if isinstance(parsed, list):
                items.extend(str(x) for x in parsed if x)
        except json.JSONDecodeError:
            pass
    for item in additions:
        if item and item not in items:
            items.append(item)
    return sorted(items)


class HarvestDB:
    """Persistent, crash-safe SQLite database for deduplicating domains and tracking harvest state."""

    def __init__(self, db_path: str | Path = "data/window_websites.db") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path), timeout=60.0, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._configure_pragmas()
        self.conn.executescript(_SCHEMA_SQL)
        self.conn.commit()

    def _configure_pragmas(self) -> None:
        # Google Drive FUSE mounts (/content/drive) don't reliably support WAL's .db-shm mmap;
        # use classic DELETE journal there and fast WAL everywhere else.
        path_str = str(self.db_path)
        if path_str.startswith("/content/drive"):
            self.conn.execute("PRAGMA journal_mode=DELETE;")
        else:
            try:
                self.conn.execute("PRAGMA journal_mode=WAL;")
            except sqlite3.OperationalError:
                self.conn.execute("PRAGMA journal_mode=DELETE;")
        self.conn.execute("PRAGMA synchronous=NORMAL;")
        self.conn.execute("PRAGMA temp_store=MEMORY;")
        self.conn.execute("PRAGMA cache_size=-64000;")  # ~64 MB page cache
        self.conn.execute("PRAGMA busy_timeout=60000;")

    def close(self) -> None:
        try:
            self.conn.commit()
            self.conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
        except sqlite3.Error:
            pass
        self.conn.close()

    def __enter__(self) -> HarvestDB:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Domain upsert & deduplication
    # ------------------------------------------------------------------

    def upsert_record(self, rec: CandidateRecord) -> bool:
        """Insert or merge a single candidate domain. Returns True if newly discovered."""
        added, _ = self.upsert_batch([rec])
        return added == 1

    def upsert_batch(self, records: list[CandidateRecord]) -> tuple[int, int]:
        """Atomically insert or merge a batch of candidate domains.

        Returns `(new_domains_added, existing_domains_merged)`.
        """
        if not records:
            return (0, 0)

        # Collapse intra-batch duplicates first to minimize SQL work
        by_domain: dict[str, list[CandidateRecord]] = {}
        for r in records:
            if r.domain:
                by_domain.setdefault(r.domain.lower(), []).append(r)

        domains = list(by_domain.keys())
        existing: dict[str, sqlite3.Row] = {}
        # SQLite max variable count is typically 999–32766; chunk at 900 for complete safety
        for i in range(0, len(domains), 900):
            chunk = domains[i : i + 900]
            placeholders = ",".join("?" for _ in chunk)
            rows = self.conn.execute(
                f"SELECT domain, business_name, categories, country, region, city, postcode, "
                f"address, phone, lat, lon, sources, confidence, sample_query, page_title, meta_description "
                f"FROM domains WHERE domain IN ({placeholders})",
                chunk,
            ).fetchall()
            for row in rows:
                existing[row["domain"]] = row

        now = _utc_now()
        to_insert: list[tuple[Any, ...]] = []
        to_update: list[tuple[Any, ...]] = []

        for domain, group in by_domain.items():
            # Fold group into one merged record
            first = group[0]
            cats = sorted({c for g in group for c in g.categories if c})
            srcs = sorted({g.source for g in group if g.source})
            max_conf = max(g.confidence for g in group)

            def _pick(attr: str) -> Any:
                for g in group:
                    val = getattr(g, attr)
                    if val is not None and val != "":
                        return val
                return None

            bname = _pick("business_name")
            country = _pick("country")
            region = _pick("region")
            city = _pick("city")
            postcode = _pick("postcode")
            address = _pick("address")
            phone = _pick("phone")
            lat = _pick("lat")
            lon = _pick("lon")
            squery = _pick("sample_query")
            ptitle = _pick("page_title")
            mdesc = _pick("meta_description")

            prev = existing.get(domain)
            if prev is None:
                bonus = min(0.12, 0.04 * (len(srcs) - 1))
                final_conf = round(min(0.99, max_conf + bonus), 3)
                to_insert.append(
                    (
                        domain,
                        first.url,
                        bname,
                        json.dumps(cats),
                        country,
                        region,
                        city,
                        postcode,
                        address,
                        phone,
                        lat,
                        lon,
                        json.dumps(srcs),
                        len(srcs),
                        final_conf,
                        squery,
                        ptitle,
                        mdesc,
                        now,
                        now,
                    )
                )
            else:
                merged_cats = _merge_json_list(prev["categories"], cats)
                merged_srcs = _merge_json_list(prev["sources"], srcs)
                prev_src_count = len(json.loads(prev["sources"] or "[]"))
                new_src_bonus = 0.04 * max(0, len(merged_srcs) - prev_src_count)
                final_conf = round(min(0.99, max(float(prev["confidence"]), max_conf) + new_src_bonus), 3)

                to_update.append(
                    (
                        prev["business_name"] or bname,
                        json.dumps(merged_cats),
                        prev["country"] or country,
                        prev["region"] or region,
                        prev["city"] or city,
                        prev["postcode"] or postcode,
                        prev["address"] or address,
                        prev["phone"] or phone,
                        prev["lat"] if prev["lat"] is not None else lat,
                        prev["lon"] if prev["lon"] is not None else lon,
                        json.dumps(merged_srcs),
                        len(merged_srcs),
                        final_conf,
                        prev["sample_query"] or squery,
                        prev["page_title"] or ptitle,
                        prev["meta_description"] or mdesc,
                        now,
                        domain,
                    )
                )

        with self.conn:
            if to_insert:
                self.conn.executemany(
                    """
                    INSERT INTO domains (
                        domain, url, business_name, categories, country, region, city, postcode,
                        address, phone, lat, lon, sources, source_count, confidence,
                        sample_query, page_title, meta_description, discovered_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    to_insert,
                )
            if to_update:
                self.conn.executemany(
                    """
                    UPDATE domains SET
                        business_name = ?, categories = ?, country = ?, region = ?, city = ?,
                        postcode = ?, address = ?, phone = ?, lat = ?, lon = ?,
                        sources = ?, source_count = ?, confidence = ?, sample_query = ?,
                        page_title = ?, meta_description = ?, updated_at = ?
                    WHERE domain = ?
                    """,
                    to_update,
                )

        return (len(to_insert), len(to_update))

    def count_domains(self, *, active_only: bool = True) -> int:
        """Return total unique domain count (excluding rejected/dead if `active_only=True`)."""
        if active_only:
            row = self.conn.execute("SELECT COUNT(*) FROM domains WHERE verified >= 0").fetchone()
        else:
            row = self.conn.execute("SELECT COUNT(*) FROM domains").fetchone()
        return int(row[0]) if row else 0

    # ------------------------------------------------------------------
    # Resumable Checkpoints
    # ------------------------------------------------------------------

    def is_checkpoint_done(self, source: str, task_key: str) -> bool:
        row = self.conn.execute(
            "SELECT status FROM checkpoints WHERE source = ? AND task_key = ?",
            (source, task_key),
        ).fetchone()
        return bool(row and row["status"] == "done")

    def get_done_checkpoints(self, source: str) -> set[str]:
        """Bulk-load all completed checkpoint keys for a source (fast O(1) lookups)."""
        rows = self.conn.execute(
            "SELECT task_key FROM checkpoints WHERE source = ? AND status = 'done'",
            (source,),
        ).fetchall()
        return {row["task_key"] for row in rows}

    def save_checkpoint(
        self,
        source: str,
        task_key: str,
        *,
        status: str = "done",
        items_found: int = 0,
        meta: dict[str, Any] | None = None,
    ) -> None:
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO checkpoints (source, task_key, status, items_found, meta, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(source, task_key) DO UPDATE SET
                    status = excluded.status,
                    items_found = excluded.items_found,
                    meta = excluded.meta,
                    updated_at = excluded.updated_at
                """,
                (source, task_key, status, items_found, json.dumps(meta) if meta else None, _utc_now()),
            )

    def get_checkpoint_meta(self, source: str, task_key: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT meta FROM checkpoints WHERE source = ? AND task_key = ?",
            (source, task_key),
        ).fetchone()
        if row and row["meta"]:
            try:
                return json.loads(row["meta"])
            except json.JSONDecodeError:
                return None
        return None

    def clear_checkpoints(self, source: str | None = None) -> int:
        with self.conn:
            if source:
                cur = self.conn.execute("DELETE FROM checkpoints WHERE source = ?", (source,))
            else:
                cur = self.conn.execute("DELETE FROM checkpoints")
            return cur.rowcount

    # ------------------------------------------------------------------
    # Company-Name Resolution Queue (for UK Companies House SIC sweeps)
    # ------------------------------------------------------------------

    def enqueue_companies(self, items: list[dict[str, str]]) -> int:
        if not items:
            return 0
        now = _utc_now()
        rows = [
            (
                it["company_id"],
                it["company_name"],
                it.get("country", "GB"),
                it.get("locality", ""),
                it.get("postcode", ""),
                it.get("sic_code", ""),
                it.get("category", "general_windows"),
                now,
            )
            for it in items
        ]
        with self.conn:
            cur = self.conn.executemany(
                """
                INSERT OR IGNORE INTO company_queue
                    (company_id, company_name, country, locality, postcode, sic_code, category, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
            return cur.rowcount

    def fetch_pending_companies(self, country: str | None = None, limit: int = 1000) -> list[sqlite3.Row]:
        if country:
            return self.conn.execute(
                "SELECT * FROM company_queue WHERE status = 'pending' AND country = ? LIMIT ?",
                (country.upper(), limit),
            ).fetchall()
        return self.conn.execute(
            "SELECT * FROM company_queue WHERE status = 'pending' LIMIT ?",
            (limit,),
        ).fetchall()

    def mark_company_status(self, company_id: str, status: str, resolved_domain: str | None = None) -> None:
        with self.conn:
            self.conn.execute(
                "UPDATE company_queue SET status = ?, resolved_domain = ?, updated_at = ? WHERE company_id = ?",
                (status, resolved_domain, _utc_now(), company_id),
            )

    # ------------------------------------------------------------------
    # Live Verification Updates
    # ------------------------------------------------------------------

    def fetch_domains_for_verification(
        self,
        *,
        limit: int = 10_000,
        country: str | None = None,
        reverify_errors: bool = False,
        borderline_first: bool = True,
    ) -> list[sqlite3.Row]:
        statuses = (0, -1) if reverify_errors else (0,)
        placeholders = ",".join("?" for _ in statuses)
        params: list[Any] = list(statuses)
        where = f"verified IN ({placeholders})"
        if country:
            where += " AND country = ?"
            params.append(country.upper())
        order = "confidence ASC" if borderline_first else "confidence DESC"
        params.append(limit)
        return self.conn.execute(
            f"SELECT domain, url, categories, confidence FROM domains WHERE {where} ORDER BY {order} LIMIT ?",
            params,
        ).fetchall()

    def apply_verification_batch(self, updates: list[dict[str, Any]]) -> None:
        if not updates:
            return
        now = _utc_now()
        with self.conn:
            for u in updates:
                domain = u["domain"]
                status = int(u["verified"])
                http_status = u.get("http_status")
                final_url = u.get("final_url")
                title = u.get("page_title")
                desc = u.get("meta_description")
                new_cats = u.get("categories") or []
                new_conf = u.get("confidence")

                if new_cats:
                    prev = self.conn.execute(
                        "SELECT categories, confidence FROM domains WHERE domain = ?",
                        (domain,),
                    ).fetchone()
                    merged_cats = json.dumps(_merge_json_list(prev["categories"] if prev else "[]", new_cats))
                    conf_val = new_conf if new_conf is not None else (prev["confidence"] if prev else 0.7)
                    self.conn.execute(
                        """
                        UPDATE domains SET
                            verified = ?, http_status = ?, final_url = ?,
                            page_title = COALESCE(NULLIF(?, ''), page_title),
                            meta_description = COALESCE(NULLIF(?, ''), meta_description),
                            categories = ?, confidence = ?, verified_at = ?, updated_at = ?
                        WHERE domain = ?
                        """,
                        (status, http_status, final_url, title, desc, merged_cats, conf_val, now, now, domain),
                    )
                else:
                    self.conn.execute(
                        """
                        UPDATE domains SET
                            verified = ?, http_status = ?, final_url = ?,
                            page_title = COALESCE(NULLIF(?, ''), page_title),
                            meta_description = COALESCE(NULLIF(?, ''), meta_description),
                            confidence = COALESCE(?, confidence),
                            verified_at = ?, updated_at = ?
                        WHERE domain = ?
                        """,
                        (status, http_status, final_url, title, desc, new_conf, now, now, domain),
                    )

    # ------------------------------------------------------------------
    # Streaming Query & Analytics
    # ------------------------------------------------------------------

    def iter_domains(
        self,
        *,
        min_confidence: float = 0.0,
        countries: list[str] | None = None,
        categories: list[str] | None = None,
        sources: list[str] | None = None,
        verified_only: bool = False,
        include_rejected: bool = False,
        limit: int | None = None,
    ) -> Iterator[dict[str, Any]]:
        """Stream matching domain rows with constant memory usage (safe for 1M+ rows)."""
        clauses: list[str] = ["confidence >= ?"]
        params: list[Any] = [min_confidence]

        if verified_only:
            clauses.append(f"verified = {int(VerifyStatus.LIVE_RELEVANT)}")
        elif not include_rejected:
            clauses.append("verified >= 0")

        if countries:
            ccs = [c.upper() for c in countries]
            clauses.append(f"country IN ({','.join('?' for _ in ccs)})")
            params.extend(ccs)

        where_sql = " AND ".join(clauses)
        sql = f"SELECT * FROM domains WHERE {where_sql} ORDER BY confidence DESC, source_count DESC, domain ASC"
        if limit:
            sql += f" LIMIT {int(limit)}"

        cat_filter = {c.strip().lower() for c in categories if c.strip()} if categories else None
        src_filter = {s.strip().lower() for s in sources if s.strip()} if sources else None

        cur = self.conn.execute(sql, params)
        while True:
            rows = cur.fetchmany(2000)
            if not rows:
                break
            for row in rows:
                cats = json.loads(row["categories"] or "[]")
                srcs = json.loads(row["sources"] or "[]")
                if cat_filter and not (cat_filter & {c.lower() for c in cats}):
                    continue
                if src_filter and not (src_filter & {s.lower() for s in srcs}):
                    continue
                d = dict(row)
                d["categories"] = cats
                d["sources"] = srcs
                yield d

    def get_stats(self) -> dict[str, Any]:
        """Compute aggregate dashboard statistics across the entire domain store."""
        total_all = self.conn.execute("SELECT COUNT(*) FROM domains").fetchone()[0]
        total_active = self.conn.execute("SELECT COUNT(*) FROM domains WHERE verified >= 0").fetchone()[0]
        multi_source = self.conn.execute(
            "SELECT COUNT(*) FROM domains WHERE verified >= 0 AND source_count >= 2"
        ).fetchone()[0]
        high_conf = self.conn.execute(
            "SELECT COUNT(*) FROM domains WHERE verified >= 0 AND confidence >= 0.80"
        ).fetchone()[0]

        ver_rows = self.conn.execute(
            "SELECT verified, COUNT(*) AS cnt FROM domains GROUP BY verified"
        ).fetchall()
        ver_map = {int(r["verified"]): int(r["cnt"]) for r in ver_rows}

        country_rows = self.conn.execute(
            """
            SELECT COALESCE(country, 'UNKNOWN') AS cc, COUNT(*) AS cnt
            FROM domains WHERE verified >= 0
            GROUP BY cc ORDER BY cnt DESC LIMIT 30
            """
        ).fetchall()

        # Aggregate categories & sources via SQLite json_each
        cat_counts: dict[str, int] = {}
        src_counts: dict[str, int] = {}
        try:
            for r in self.conn.execute(
                """
                SELECT j.value AS cat, COUNT(*) AS cnt
                FROM domains, json_each(domains.categories) AS j
                WHERE domains.verified >= 0
                GROUP BY j.value ORDER BY cnt DESC
                """
            ):
                cat_counts[str(r["cat"])] = int(r["cnt"])
            for r in self.conn.execute(
                """
                SELECT j.value AS src, COUNT(*) AS cnt
                FROM domains, json_each(domains.sources) AS j
                WHERE domains.verified >= 0
                GROUP BY j.value ORDER BY cnt DESC
                """
            ):
                src_counts[str(r["src"])] = int(r["cnt"])
        except sqlite3.OperationalError:
            # Fallback if a minimal SQLite build lacks json_each
            for r in self.conn.execute("SELECT categories, sources FROM domains WHERE verified >= 0"):
                for c in json.loads(r["categories"] or "[]"):
                    cat_counts[c] = cat_counts.get(c, 0) + 1
                for s in json.loads(r["sources"] or "[]"):
                    src_counts[s] = src_counts.get(s, 0) + 1

        cp_rows = self.conn.execute(
            "SELECT source, status, COUNT(*) AS cnt FROM checkpoints GROUP BY source, status"
        ).fetchall()
        checkpoints: dict[str, dict[str, int]] = {}
        for r in cp_rows:
            checkpoints.setdefault(str(r["source"]), {})[str(r["status"])] = int(r["cnt"])

        pending_companies = self.conn.execute(
            "SELECT COUNT(*) FROM company_queue WHERE status = 'pending'"
        ).fetchone()[0]

        return {
            "db_path": str(self.db_path),
            "total_active_domains": int(total_active),
            "total_all_rows": int(total_all),
            "high_confidence_domains": int(high_conf),
            "multi_source_confirmed": int(multi_source),
            "verification": {
                "unverified": ver_map.get(int(VerifyStatus.UNVERIFIED), 0),
                "verified_live": ver_map.get(int(VerifyStatus.LIVE_RELEVANT), 0),
                "dead_or_error": ver_map.get(int(VerifyStatus.DEAD_OR_ERROR), 0),
                "parked": ver_map.get(int(VerifyStatus.PARKED), 0),
                "rejected_irrelevant": ver_map.get(int(VerifyStatus.IRRELEVANT), 0),
            },
            "by_source": dict(sorted(src_counts.items(), key=lambda kv: kv[1], reverse=True)),
            "by_category": dict(sorted(cat_counts.items(), key=lambda kv: kv[1], reverse=True)),
            "by_country": {str(r["cc"]): int(r["cnt"]) for r in country_rows},
            "checkpoints": checkpoints,
            "pending_company_queue": int(pending_companies),
        }
