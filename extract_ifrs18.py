#!/usr/bin/env python3
"""Extract IFRS 18 primary statements from an issuer's consolidated-statements PDF (or text)
into the JSON schema used by the app (see data_afklm.json).

Usage:  python3 extract_ifrs18.py report.pdf  -o out.json  [--issuer "Name"]
        python3 extract_ifrs18.py report.txt  -o out.json
PDF text comes from `pdftotext -layout` (poppler) or, failing that, pypdf.

Scope: income statement and the MPM / net-debt figures. Balance sheet and cash flow are not
extracted yet (the reference dataset carries them). Tested on a text fixture of the AF-KLM H1 2026
income statement, not yet on the PDF itself.

Method: label-driven. Each statement line is "label  n1  n2" where numbers use
thousands separators and parentheses for negatives. Labels are matched to schema keys
with the regexes below, tuned on Air France-KLM's H1 2026 layout. Another issuer will
use other wording: add patterns to LABELS. Unmatched lines are reported, never guessed.
Every extraction is followed by the IFRS 18 integrity checks; a failed check means a
line was missed or mis-read.
"""
import argparse, json, re, subprocess, sys

NUM = r"\(?-?(?:\d{1,3}(?:,\d{3})+|\d+)\)?|–|—"
LINE = re.compile(rf"^(?P<label>.*?[A-Za-z\)].*?)\s+(?:\d{{1,2}}(?:\.\d)?\s+)?(?P<a>{NUM})\s+(?P<b>{NUM})\s*$")

def to_num(s):
    s = s.strip()
    if s in ("–", "—", ""): return 0
    neg = s.startswith("(") or s.startswith("-")
    n = int(re.sub(r"[^\d]", "", s) or 0)
    return -n if neg else n

# (key, cat/subtotal info, regex on the label)   first match wins, order matters
IS = [
 ("traffic_sales", {"cat":"operating","memo":True}, r"^traffic sales"),
 ("other_sales", {"cat":"operating","memo":True}, r"^sales . other business"),
 ("revenues", {"cat":"operating"}, r"^revenues?$"),
 ("fuel", {"cat":"operating"}, r"^fuel"),
 ("external", {"cat":"operating"}, r"^external expenses"),
 ("salaries", {"cat":"operating"}, r"^salaries"),
 ("taxes_other", {"cat":"operating"}, r"^taxes other than income"),
 ("capitalized", {"cat":"operating"}, r"^capitali[sz]ed production"),
 ("other_opex", {"cat":"operating"}, r"^other operating expenses"),
 ("amortization", {"cat":"operating"}, r"^amorti[sz]ation$"),
 ("provisions", {"cat":"operating"}, r"^reversals \(additions\) to provisions"),
 ("fx_operating", {"cat":"operating"}, r"^foreign exchange \(operating\)"),
 ("sales_aircraft", {"cat":"operating"}, r"^sales of aircraft"),
 ("non_recurring", {"cat":"operating"}, r"^non-recurring"),
 ("op_profit", {"subtotal":"operating"}, r"^operating profit"),
 ("associates", {"cat":"investing"}, r"^share of profits"),
 ("cash_income", {"cat":"investing"}, r"^income from cash"),
 ("pbfit", {"subtotal":"investing"}, r"^profit or loss before financing"),
 ("int_fin", {"cat":"financing"}, r"^interests? expenses? (on|of) financial"),
 ("int_lease", {"cat":"financing"}, r"^interests? expenses? of lease"),
 ("undiscount", {"cat":"financing"}, r"^undiscounting"),
 ("pbt", {"subtotal":"financing"}, r"^profit or loss before income tax"),
 ("tax", {"cat":"tax"}, r"^income taxes$"),
 ("net", {"subtotal":"tax"}, r"^profit or loss$"),
 ("nci", {"cat":"split"}, r"^net income . non-controlling"),
 ("group", {"cat":"split"}, r"^net income . group"),
]
FX = r"^foreign exchange gains \(losses\),? (on )?derivatives and other"

XBRL_MARKERS = re.compile(rb"ix:nonfraction|ix:header|xbrli:|ifrs-full|\bxbrl\b", re.I)

def detect_xbrl(path):
    """Report whether the input file itself carries XBRL. Evidence is limited to the file given:
    a PDF cannot hold inline XBRL, so only embedded attachments or tag markers count. A separate
    ESEF package published by the issuer is not visible from here."""
    raw = open(path, "rb").read()
    hits = len(XBRL_MARKERS.findall(raw))
    if path.lower().endswith((".xhtml", ".html", ".htm", ".xml")):
        return {"available": hits > 0, "evidence": f"{hits} XBRL tag markers in the file" if hits else "no XBRL tag markers in the file"}
    attach = ""
    try:
        attach = subprocess.run(["pdfdetach", "-list", path], capture_output=True, text=True).stdout
    except Exception:
        pass
    n = int(re.match(r"\s*(\d+)", attach).group(1)) if re.match(r"\s*(\d+)", attach) else None
    found = hits > 0 or bool(n)
    return {"available": found, "evidence": f"{n if n is not None else 'unknown number of'} embedded files, {hits} XBRL markers in the PDF"}

def read_text(path):
    if not path.lower().endswith(".pdf"):
        return open(path, encoding="utf-8").read()
    try:
        return subprocess.run(["pdftotext", "-layout", path, "-"], capture_output=True, text=True, check=True).stdout
    except Exception:
        from pypdf import PdfReader
        return "\n".join(p.extract_text() or "" for p in PdfReader(path).pages)

def income_statement(text):
    start = text.find("Period from January 1 to June 30")
    block = text[start: text.find("CONSOLIDATED STATEMENT OF COMPREHENSIVE", start + 10)]
    rows, fx_seen, unmatched, pending = [], 0, [], ""
    for raw in block.splitlines():
        raw = raw.strip()
        if raw.startswith(("Period from", "(in €", "The accompanying", "(1)")): pending = ""; continue
        if raw[:1].islower() and not LINE.match(raw):   # wrapped tail of the previous label, e.g. "provisions)"
            continue
        line = (pending + " " + raw).strip()
        m = LINE.match(line)
        if not m:
            pending = line if raw and len(line) < 160 else ""
            continue
        pending = ""
        label = re.sub(r"\s+", " ", m["label"]).strip(" •")
        low = label.lower()
        v = [to_num(m["a"]), to_num(m["b"])]
        if re.match(FX, low):                      # three FX lines: operating is matched above
            fx_seen += 1
            key, info = ("fx_investing", {"cat":"investing"}) if fx_seen == 1 else ("fx_financing", {"cat":"financing"})
        else:
            hit = next(((k, i) for k, i, rx in IS if re.search(rx, low)), None)
            if not hit: unmatched.append(label); continue
            key, info = hit
        if not any(r["key"] == key for r in rows):
            rows.append({"key": key, "label": label, **info, "v": v})
    return rows, unmatched

def mpm(text, rows=()):
    def grab(rx):
        m = re.search(rx + rf"[^\n\d\(]*?\s+(?P<a>{NUM})\s+(?P<b>{NUM})", text, re.I | re.M)
        return [to_num(m["a"]), to_num(m["b"])] if m else None
    out = {
        "adjusted_ebitda": grab(r"^\s*Adjusted EBITDA"),
        "adjusted_operating_profit": grab(r"^\s*Adjusted operating profit"),
        "operating_fcf": grab(r"^\s*Operating free cash flow"),
    }
    nd = re.search(r"NET DEBT \(I-II\)\s+(" + NUM + r")\s+(" + NUM + r")", text)
    if nd: out["net_debt"] = [to_num(nd[1]), to_num(nd[2])]
    # Cost of net debt (Note 6.3) = income from cash less interest on financial and lease debt.
    # Derived from the income statement: the phrase also appears in a restatement table with other values.
    by = {r["key"]: r["v"] for r in rows}
    if all(k in by for k in ("cash_income", "int_fin", "int_lease")):
        out["cost_of_net_debt"] = [-(by["cash_income"][i] + by["int_fin"][i] + by["int_lease"][i]) for i in (0, 1)]
    return {k: v for k, v in out.items() if v}

def checks(rows):
    by = {r["key"]: r["v"] for r in rows}
    def s(cat, i): return sum(r["v"][i] for r in rows if r.get("cat") == cat and not r.get("memo"))
    res = []
    for i in (0, 1):
        try:
            ops = s("operating", i); res.append((f"operating lines = operating profit [{i}]", ops, by["op_profit"][i]))
            res.append((f"+ investing = profit before financing & tax [{i}]", by["op_profit"][i] + s("investing", i), by["pbfit"][i]))
            res.append((f"+ financing = profit before tax [{i}]", by["pbfit"][i] + s("financing", i), by["pbt"][i]))
            res.append((f"+ income taxes = profit or loss [{i}]", by["pbt"][i] + by["tax"][i], by["net"][i]))
        except KeyError as e:
            res.append((f"missing line {e} [{i}]", None, None))
    return res

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("source"); ap.add_argument("-o", "--out", default="extracted.json")
    ap.add_argument("--issuer", default="Unknown issuer"); a = ap.parse_args()
    text = read_text(a.source)
    xbrl = detect_xbrl(a.source)
    if not re.search(r"profit or loss before financing and income tax", text, re.I):
        sys.exit("No IFRS 18 income statement found (no 'Profit or loss before financing and income taxes' subtotal).")
    rows, unmatched = income_statement(text)
    ck = checks(rows)
    data = {"issuer": a.issuer, "currency": "EUR", "unit": "millions", "standard": "IFRS 18",
            "periods": {"flow": ["Current", "Comparative"], "stock": ["Current", "Comparative"]},
            "income_statement": rows, "balance_sheet": [], "cash_flow": [], "mpm": mpm(text, rows), "xbrl": xbrl}
    json.dump(data, open(a.out, "w"), indent=1)
    for name, got, want in ck: print(("OK  " if got == want else "FAIL"), name, got, want)
    if unmatched: print("Unmatched lines:", *unmatched, sep="\n  ")
    print("XBRL:", "available" if xbrl["available"] else "not available", "-", xbrl["evidence"])
    print(f"wrote {a.out}: {len(rows)} income-statement lines, MPM keys {sorted(data['mpm'])}")
