"""
Проверка доступности YouTube cookies для yt-dlp.

Использование:
  - Локально: убедитесь, что экспортировали cookies.txt (Netscape) рядом с проектом.
  - На сервере: чаще всего используйте YOUTUBE_COOKIES_BASE64.
"""

import base64
import os
import sys


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
COOKIES_PATH = os.path.join(BASE_DIR, "cookies.txt")


def _looks_like_netscape(cookies_content: str) -> bool:
    if not cookies_content:
        return False
    head = cookies_content[:2000]
    return head.startswith("# Netscape") or ("\tyoutube.com\t" in head) or ("youtube.com\t" in head)


def _validate(cookies_content: str) -> tuple[bool, str]:
    if not cookies_content.strip():
        return False, "Empty cookies content"

    if not _looks_like_netscape(cookies_content):
        return False, "Does not look like Netscape cookies format or does not mention youtube.com"

    # Грубая проверка: строки не должны быть совсем пустыми
    lines = [ln for ln in cookies_content.splitlines() if ln.strip() and not ln.startswith("#")]
    if len(lines) < 5:
        return False, f"Too few cookie lines (only {len(lines)})"

    return True, f"OK (cookie lines: {len(lines)})"


def main() -> int:
    env_b64 = os.getenv("YOUTUBE_COOKIES_BASE64", "").strip()

    source = None
    content = None

    if env_b64:
        source = "YOUTUBE_COOKIES_BASE64"
        try:
            decoded = base64.b64decode(env_b64).decode("utf-8", errors="replace")
            content = decoded
        except Exception as e:
            print(f"❌ Failed to decode YOUTUBE_COOKIES_BASE64: {e}")
            return 1
    elif os.path.exists(COOKIES_PATH):
        source = "cookies.txt"
        try:
            with open(COOKIES_PATH, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except Exception as e:
            print(f"❌ Failed to read cookies.txt: {e}")
            return 1
    else:
        print("❌ Neither YOUTUBE_COOKIES_BASE64 is set nor cookies.txt exists.")
        return 1

    ok, msg = _validate(content)
    if ok:
        print(f"✅ YouTube cookies validation succeeded. Source: {source}. {msg}")
        return 0
    else:
        print(f"❌ YouTube cookies validation failed. Source: {source}. {msg}")
        print("Tip: export fresh Netscape cookies for youtube.com and update YOUTUBE_COOKIES_BASE64.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

