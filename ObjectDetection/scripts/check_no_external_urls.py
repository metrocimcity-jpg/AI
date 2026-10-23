"""Fail if the built UI references a remote host."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN = ("fonts.googleapis.com", "fonts.gstatic.com", "cdn.jsdelivr", "unpkg.com", "cdnjs.cloudflare.com")


def main() -> int:
    roots = [ROOT / "frontend" / "src", ROOT / "frontend" / "index.html", ROOT / "frontend" / "dist"]
    bad: list[str] = []
    for root in roots:
        files = [root] if root.is_file() else list(root.rglob("*")) if root.exists() else []
        for path in files:
            if not path.is_file() or path.suffix.lower() not in {".html", ".js", ".css", ".tsx", ".ts"}:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            for host in FORBIDDEN:
                if host in text:
                    bad.append(f"{path}: {host}")
    if bad:
        print("\n".join(bad))
        return 1
    print("no external UI hosts found")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
