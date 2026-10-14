# Accounts Lens

**Company accounts and standard credit ratios under IFRS 18.**

Reads a group's consolidated statements in the IFRS 18 layout (operating / investing / financing / income taxes), computes credit analysis ratios, and shows everything in a single-page UI.

Test case: **Air France-KLM**, condensed interim consolidated financial statements at 30 June 2026 (unaudited), which early adopt IFRS 18 with restated 2025 comparatives.

## What is in here

| Path | Purpose |
|---|---|
| `app/template.html` | The UI: statements, 17 credit ratios, waterfall, integrity checks, JSON import. No dependencies beyond two Google Fonts. |
| `build.py` | Inlines a dataset into the template and writes `docs/index.html` (serve with GitHub Pages). |
| `data/afklm_h1_2026.json` | Air France-KLM dataset: income statement, balance sheet, cash flow, management-defined measures. |
| `extractor/extract_ifrs18.py` | PDF or text to JSON for the income statement and key measures. |
| `tests/` | Dataset integrity tests and an extractor regression test. |

## Use

```bash
python3 build.py                                   # writes docs/index.html
python3 -m unittest discover -s tests              # run the tests
python3 extractor/extract_ifrs18.py report.pdf -o out.json --issuer "Name"
python3 build.py out.json docs/other.html          # UI for another issuer
```

The extractor needs poppler's `pdftotext`, or `pip install pypdf` as a fallback. In the UI, "Load another issuer (JSON)" accepts the same format.

## Ratios

Margins (operating, adjusted operating, adjusted EBITDA, net), interest cover, net debt / adjusted EBITDA, net debt / equity, lease share of gross debt, equity / assets, current ratio, short-term debt cover, liquidity including undrawn facilities, operating free cash flow margin, FFO / net debt, capex / amortization. Each ratio's formula is shown next to its value.

Adjusted EBITDA, adjusted operating profit, net debt and operating free cash flow are the issuer's management-defined measures, taken as reported. Net debt / adjusted EBITDA uses twice the half-year EBITDA unless a 12-month figure is entered; it is not the issuer's reported leverage (1.6x at 30 June 2026 per its Q2 2026 press release).

## XBRL

Every analysed report gets an XBRL check: the extractor writes `xbrl.available` and `xbrl.evidence` into its JSON, prints the result, and the UI shows it in the header. For Air France-KLM's June 2026 half-year PDF the result is **not available** (no embedded files, no XBRL markers). That is expected: ESEF tagging applies to annual financial reports only, so half-year reports are PDF-only. The check only sees the file it is given, not a separate package an issuer may publish.

Planned: read inline XBRL directly from annual reports once issuers file under IFRS 18. ESMA's 2025 ESEF taxonomy, released 21 April 2026, has an IFRS 18 entry point for 2026 statements. Reading tagged facts would replace label matching and make issuers comparable. Sources: [XBRL International](https://www.xbrl.org/news/esma-updates-esef-taxonomy-ahead-of-ifrs-18-transition/), [Arthur Cox summary of the ESEF scope](https://www.arthurcox.com/knowledge/single-electronic-reporting-format-reminder-for-issuers/).

## Status and limits

- The extractor covers the income statement and four key measures. It reproduces the Air France-KLM reference dataset exactly from the real PDF (28 of 28 lines, all subtotal checks pass). Balance sheet and cash flow are not extracted yet; they come from the reference dataset.
- Label matching is tuned to Air France-KLM's wording. Other issuers need new patterns in the `IS` table; unmatched lines are listed, never guessed.
- The source PDF is not committed (`*.pdf` is ignored). Download it from the issuer's investor site.
- No licence file is included: choose one before making the repository public.

## Sources

**Taken from the filing** (Air France-KLM, *Condensed Interim Consolidated Financial Statements (Unaudited), 1 January to 30 June 2026*): the income statement, balance sheet and cash flow statement; adjusted EBITDA, adjusted operating profit, operating free cash flow, net debt and cost of net debt (Note 6); the IFRS 18 transition and restatement (Note 4); undrawn facilities of EUR 3.5 billion and covenant definitions (Note 27).
https://www.airfranceklm.com/sites/default/files/2026-07/2026.06-air-france-klm-consolidated-financial-statements-and-notes-as-of-june-30-2026.pdf

**Taken from the issuer's press release:** the reported leverage of 1.6x (net debt / adjusted EBITDA, last 12 months), shown for comparison only. Air France-KLM, *Second quarter 2026*, 30 July 2026.
https://www.airfranceklm.com/sites/default/files/2026-07/20260729-2026-q2-afklm-press-release-1.pdf

**Computed here, not from any source:** every ratio on the Credit ratios tab, the waterfall, and the integrity checks. The formula is shown next to each ratio. The leverage ratio uses twice the half-year EBITDA unless a 12-month figure is entered, so it differs from the issuer's 1.6x.

**XBRL and ESEF background:** see the XBRL section above. Those two pages are secondary summaries, not the ESMA regulation itself.
