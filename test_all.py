"""python3 -m unittest discover -s tests   (run from the repo root)"""
import json, pathlib, subprocess, sys, tempfile, unittest
ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = json.load(open(ROOT / "data" / "afklm_h1_2026.json", encoding="utf-8"))

def tot(rows, pred, i): return sum(r["v"][i] for r in rows if pred(r))
def g(rows, k, i): return next(r for r in rows if r["key"] == k)["v"][i]

class Dataset(unittest.TestCase):
    def test_income_statement_subtotals(self):
        is_ = DATA["income_statement"]
        for i in (0, 1):
            self.assertEqual(tot(is_, lambda r: r.get("cat") == "operating" and not r.get("memo"), i), g(is_, "op_profit", i))
            self.assertEqual(g(is_, "op_profit", i) + tot(is_, lambda r: r.get("cat") == "investing", i), g(is_, "pbfit", i))
            self.assertEqual(g(is_, "pbfit", i) + tot(is_, lambda r: r.get("cat") == "financing", i), g(is_, "pbt", i))
            self.assertEqual(g(is_, "pbt", i) + g(is_, "tax", i), g(is_, "net", i))
    def test_balance_sheet(self):
        bs = DATA["balance_sheet"]
        for i in (0, 1):
            for sec, total in (("nca", "total_nca"), ("ca", "total_ca"), ("ncl", "total_ncl"), ("cl", "total_cl")):
                self.assertEqual(tot(bs, lambda r: r.get("sec") == sec, i), g(bs, total, i), (sec, i))
            self.assertEqual(g(bs, "total_assets", i), g(bs, "total_ncl", i) + g(bs, "total_cl", i) + g(bs, "equity", i))
    def test_cash_flow(self):
        cf = DATA["cash_flow"]
        for i in (0, 1):
            self.assertEqual(g(cf, "cfo", i) + g(cf, "cfi", i) + g(cf, "cff", i) + g(cf, "fx_cash", i), g(cf, "cash_change", i))
    def test_net_debt_bridge(self):
        m = DATA["mpm"]
        for i in (0, 1): self.assertEqual(m["gross_financial_liabilities"][i] - m["net_cash"][i], m["net_debt"][i])

class Extractor(unittest.TestCase):
    def test_fixture_matches_reference_income_statement(self):
        out = pathlib.Path(tempfile.mkdtemp()) / "o.json"
        subprocess.run([sys.executable, str(ROOT / "extractor" / "extract_ifrs18.py"), str(ROOT / "tests" / "fixture_afklm_income_statement.txt"), "-o", str(out)], check=True, capture_output=True)
        got = {r["key"]: r["v"] for r in json.load(open(out))["income_statement"]}
        ref = {r["key"]: r["v"] for r in DATA["income_statement"]}
        self.assertEqual(got, ref)
        self.assertEqual(json.load(open(out))["mpm"]["cost_of_net_debt"], DATA["mpm"]["cost_of_net_debt"])

class Xbrl(unittest.TestCase):
    def _run(self, name, content):
        d = pathlib.Path(tempfile.mkdtemp()); f = d / name; f.write_text(content)
        subprocess.run([sys.executable, str(ROOT / "extractor" / "extract_ifrs18.py"), str(f), "-o", str(d / "o.json")], check=True, capture_output=True)
        return json.load(open(d / "o.json"))["xbrl"]
    def test_plain_report_has_no_xbrl(self):
        self.assertFalse(self._run("r.txt", open(ROOT / "tests" / "fixture_afklm_income_statement.txt").read())["available"])
    def test_tagged_report_is_detected(self):
        body = open(ROOT / "tests" / "fixture_afklm_income_statement.txt").read()
        self.assertTrue(self._run("r.xhtml", '<html xmlns:ix="http://www.xbrl.org/2013/inlineXBRL"><ix:nonFraction name="ifrs-full:Revenue">1</ix:nonFraction><pre>' + body + "</pre></html>")["available"])
    def test_dataset_records_check(self):
        self.assertIn("available", DATA["xbrl"])

if __name__ == "__main__": unittest.main()
