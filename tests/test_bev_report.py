"""bench/bev_report.py on fixture test folders made from real mock runs."""
import gzip
import json
from pathlib import Path

import pytest

from bench import bev_report
from bench.board_sampler import parse
from tests.test_bev_ideas import DEV, cfg_with, run
from tests.test_board_sampler import SAMPLE

EP = "dev_A03_bfp_suction"


def _folder(root: Path, name: str, cfg, resources=None) -> Path:
    from bench.evaluator import evaluate
    d = root / name
    d.mkdir(parents=True)
    r = run(cfg, EP)
    (d / "test.json").write_text(json.dumps({"params": {"overlay": "x", "mode": "lockstep",
                                                        "backend": "mock", "bev": name}}))
    stem = f"{EP}_multi"
    (d / f"{stem}.summary.json").write_text(json.dumps({"meta": {"episode": EP}, "evaluation": evaluate(r)}))
    with gzip.open(d / f"{stem}.run.json.gz", "wt") as f:
        json.dump(r, f)
    if resources:
        (d / f"{stem}.resources.json").write_text(json.dumps(resources))
    return d


@pytest.fixture(scope="module")
def folders(tmp_path_factory):
    if not (DEV / EP).exists():
        pytest.skip("dev episodes not generated")
    root = tmp_path_factory.mktemp("bench")
    return {"A": _folder(root, "A", cfg_with()),
            "A2": _folder(root, "A2", cfg_with()),
            "B": _folder(root, "B", cfg_with(explain="on", verifier="on"), resources=parse(SAMPLE))}


def test_report_totals_match_the_envelopes_own_token_fields(folders):
    for k in ("A", "B"):
        t = bev_report.load(folders[k])
        m = bev_report.metrics(t, [EP])
        r = t["episodes"][EP]["run"]
        # a different record than the per-call lists the report sums
        direct = sum((e.get("tokens") or {}).get("decode") or 0
                     for a in r["assessments"] for e in a["envelopes"])
        assert m["decode_tokens"] == direct
        assert m["decode_per_tick"] == round(direct / r["n_ticks"], 2)
    mb = bev_report.metrics(bev_report.load(folders["B"]), [EP])
    assert mb["calls"]["verifier@bev"]["stand_ins"] == mb["calls"]["verifier@bev"]["answers"] > 0
    assert mb["calls"]["verifier@bev"].get("calls", 0) == 0
    assert mb["board"]["processes"]["npu"]["cpu_s"] == 4.0          # from the sampler fixture


def test_report_writes_md_and_html_with_the_mock_banner_and_the_spread(folders, tmp_path):
    bev_report.main([str(folders["A"]), str(folders["B"]), "--a2", str(folders["A2"]), "--out", str(tmp_path)])
    md = (tmp_path / "COMPARE_A.md").read_text()
    page = (tmp_path / "COMPARE_A.html").read_text()
    assert "MOCK backend: plumbing only" in md and "Run-to-run spread" in md
    assert "explain=on" in md and "verifier=on" in md
    assert page.startswith("<!doctype html>") and "<svg" in page and "Decode tokens per tick" in page


def test_calibrate_refuses_reporting_episodes_and_tabulates_dev_shadow(folders, tmp_path):
    from bench import bev_calibrate
    t = bev_report.load(folders["A"])
    t["episodes"] = {"ep_A01_fcv_seize": t["episodes"][EP]}
    with pytest.raises(SystemExit, match="not a dev episode"):
        bev_calibrate.rows([t])
    cfg = cfg_with(first="shadow")
    d = _folder(tmp_path, "S", cfg)
    rs = bev_calibrate.rows([bev_report.load(d)])
    assert rs and all(0 <= r["p"] <= 1 for r in rs)
    tab = bev_calibrate.table(rs).splitlines()
    covered = [int(l.split("|")[2]) for l in tab[2:]]
    assert covered == sorted(covered, reverse=True) and covered[0] <= len(rs)
