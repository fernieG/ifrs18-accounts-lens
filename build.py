#!/usr/bin/env python3
"""Inline a dataset into the app template and write a standalone page (default: docs/index.html,
which GitHub Pages can serve). Usage: python3 build.py [data.json] [out.html]"""
import json, sys, pathlib
root = pathlib.Path(__file__).parent
data = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else root / "data" / "afklm_h1_2026.json"
out = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else root / "docs" / "index.html"
html = (root / "app" / "template.html").read_text(encoding="utf-8")
assert "/*__DATA__*/null" in html, "placeholder missing from template"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(html.replace("/*__DATA__*/null", json.dumps(json.load(open(data, encoding="utf-8")), ensure_ascii=False)), encoding="utf-8")
print("wrote", out)
