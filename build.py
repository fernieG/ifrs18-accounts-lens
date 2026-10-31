#!/usr/bin/env python3
"""Build standalone Accounts Lens HTML from a dataset.

Usage: python3 build.py [data.json] [out.html]
Defaults: afklm_h1_2026.json -> index.html (served by GitHub Pages).
"""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
MARKER = "/*__DATA__*/null"


def main():
    data_path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "afklm_h1_2026.json"
    out_path = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "index.html"
    template = (ROOT / "template.html").read_text(encoding="utf-8")
    if template.count(MARKER) != 1:
        raise ValueError("Expected exactly one dataset placeholder in template.html")

    dataset = json.loads(data_path.read_text(encoding="utf-8"))
    html = template.replace(MARKER, json.dumps(dataset, ensure_ascii=False))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    print("wrote", out_path)


if __name__ == "__main__":
    main()
