#!/usr/bin/env python3
"""
Extract YouTube/Google cookies from Firefox cookies.sqlite
and write Netscape cookies.txt for yt-dlp usage.

Windows-first helper. No browser extensions required.
"""

from __future__ import annotations

import argparse
import glob
import os
import shutil
import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path


FIREFOX_PROFILES_DIR = Path(os.environ.get("APPDATA", "")) / "Mozilla" / "Firefox" / "Profiles"
TARGET_HOST_PARTS = ("youtube.com", "google.com", "googlevideo.com")


def find_firefox_cookie_db() -> Path:
    pattern = str(FIREFOX_PROFILES_DIR / "*" / "cookies.sqlite")
    candidates = [Path(p) for p in glob.glob(pattern)]
    if not candidates:
        raise FileNotFoundError(
            f"Firefox cookies.sqlite not found in: {FIREFOX_PROFILES_DIR}"
        )
    return max(candidates, key=lambda p: p.stat().st_size)


def export_netscape_cookies(db_path: Path, out_path: Path) -> int:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".sqlite") as tmp:
        tmp_path = Path(tmp.name)
    try:
        shutil.copy2(db_path, tmp_path)
        conn = sqlite3.connect(tmp_path)
        try:
            query = """
                SELECT host, path, isSecure, expiry, name, value
                FROM moz_cookies
                WHERE
                    host LIKE '%youtube.com%'
                    OR host LIKE '%google.com%'
                    OR host LIKE '%googlevideo.com%'
                ORDER BY host, name
            """
            rows = conn.execute(query).fetchall()
        finally:
            conn.close()

        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("w", encoding="utf-8", newline="\n") as f:
            f.write("# Netscape HTTP Cookie File\n")
            f.write(f"# Exported from Firefox on {datetime.utcnow().isoformat()}Z\n")
            f.write("# This file is generated for yt-dlp authentication.\n\n")
            for host, path, is_secure, expiry, name, value in rows:
                include_subdomains = "TRUE" if str(host).startswith(".") else "FALSE"
                secure = "TRUE" if int(is_secure or 0) else "FALSE"
                expiry_ts = int(expiry or 0)
                # domain \t include_subdomains \t path \t secure \t expiry \t name \t value
                f.write(
                    f"{host}\t{include_subdomains}\t{path}\t{secure}\t{expiry_ts}\t{name}\t{value}\n"
                )
        return len(rows)
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export Firefox YouTube/Google cookies to Netscape cookies.txt"
    )
    parser.add_argument(
        "--output",
        default="cookies.txt",
        help="Output file path (default: cookies.txt)",
    )
    args = parser.parse_args()

    if os.name != "nt":
        print("Warning: this helper is optimized for Windows Firefox profile path.")

    db_path = find_firefox_cookie_db()
    out_path = Path(args.output).resolve()
    count = export_netscape_cookies(db_path, out_path)

    print(f"Firefox DB: {db_path}")
    print(f"Saved: {out_path}")
    print(f"Extracted cookies: {count}")
    if count == 0:
        print("No matching cookies found. Open YouTube in Firefox while logged in, then retry.")
    else:
        print("Done. Next step: convert file to base64 and set YOUTUBE_COOKIES_BASE64 in Railway.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
