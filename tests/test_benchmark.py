"""bench/benchmark.py (scripts/benchmark.sh) and the monitor's new columns.
Outcome-based: assertions on the folders and files a run leaves, and on what
the monitor builds from real (mock) tick records."""

import gzip
import json
import subprocess
import sys
from pathlib import Path

import pytest

from bench.stage_monitor_multi import build, cell, load_truth, running_scores, episode_dir

ROOT = Path(__file__).resolve().parent.parent
needs_dev = pytest.mark.skipif(not (ROOT / "data/episodes_dev/dev_C01_wet_coal").exists(),
                               reason="dev episodes not generated")


def bench(tmp_root, *args):
    """The runner on the mock backend, writing under a temporary results root."""
    code = ("import sys, bench.benchmark as b; from pathlib import Path; "
            f"b.ROOT_RESULTS = Path({str(tmp_root)!r}); sys.argv = ['benchmark.py', *{list(args)!r}]; "
            "raise SystemExit(b.main())")
    return subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True,
                          timeout=600)


@pytest.fixture(scope="module")
def first(tmp_path_factory):
    root = tmp_path_factory.mktemp("bench")
    p = bench(root, "t", "dev_C01_wet_coal", "ep_N01_normal", "--backend", "mock", "--plain")
    assert p.returncode == 0, p.stdout[-2000:] + p.stderr[-2000:]
    return root / "t", p


@needs_dev
def test_a_test_folder_holds_every_episode_and_the_settings(first):
    d, p = first
    names = sorted(x.name for x in d.iterdir())
    for ep in ("dev_C01_wet_coal", "ep_N01_normal"):
        for kind in ("summary.json", "run.json.gz", "log"):
            assert f"{ep}_multi.{kind}" in names
    assert "RESULTS.md" in names and "test.json" in names
    assert not [n for n in names if n.endswith(".ticks.jsonl") or n.startswith(".tmp_")]
    t = json.loads((d / "test.json").read_text())
    assert t["params"]["arch"] == "multi" and t["params"]["overlay"] == "configs/fast.yaml"
    assert [(r["stem"], r["status"]) for r in t["runs"]] == [
        ("dev_C01_wet_coal_multi", "done"), ("ep_N01_normal_multi", "done")]
    res = (d / "RESULTS.md").read_text()
    assert "MOCK backend" in res and res.count("\n| dev_C01_wet_coal | 1 |") == 1


@needs_dev
def test_summary_counts_match_the_saved_run(first):
    d, _ = first
    s = json.loads((d / "dev_C01_wet_coal_multi.summary.json").read_text())
    run = json.loads(gzip.decompress((d / "dev_C01_wet_coal_multi.run.json.gz").read_bytes()))
    envs = [e for a in run["assessments"] for e in a["envelopes"]]
    envs += [t["envelope"] for a in run["assessments"] for t in a["multi"]["text"]]
    assert s["calls"]["calls"] == len(envs) > 0
    assert s["calls"]["tokens_in"] == sum(e["tokens"]["prefill"] for e in envs)
    assert s["calls"]["ticks"] == len(run["assessments"])
    assert s["meta"]["energy_mwh"] is None and "MOCK" in s["meta"]["where"]


@needs_dev
def test_same_name_resumes_again_adds_and_other_settings_are_refused(first, tmp_path):
    d, _ = first
    root = d.parent
    p = bench(root, "t", "dev_C01_wet_coal", "--backend", "mock", "--plain")
    assert p.returncode == 0 and "skipped" in p.stdout
    assert not list(d.glob("dev_C01_wet_coal_multi_r2.*"))
    p = bench(root, "t", "dev_C01_wet_coal", "--backend", "mock", "--plain", "--again")
    assert p.returncode == 0, p.stderr[-1500:]
    assert (d / "dev_C01_wet_coal_multi_r2.summary.json").exists()
    assert (d / "dev_C01_wet_coal_multi.summary.json").exists()          # run 1 untouched
    p = bench(root, "t", "dev_C01_wet_coal", "--backend", "mock", "--plain",
              "--merge-rule", "tiebreak")
    assert p.returncode != 0 and "other settings" in p.stderr
    assert json.loads((d / "test.json").read_text())["params"]["merge_rule"] == "model"


def test_bad_names_and_unknown_episodes_are_refused_before_anything_runs(tmp_path):
    p = bench(tmp_path, "../x", "ep_N01_normal", "--backend", "mock")
    assert p.returncode != 0 and "test name" in p.stderr
    p = bench(tmp_path, "x", "ep_Z99_none", "--backend", "mock")
    assert p.returncode != 0 and "unknown episode" in p.stderr
    p = bench(tmp_path, "x", "ep_N01_normal", "--backend", "mock", "--arch", "single",
              "--mode", "realtime")
    assert p.returncode != 0 and "multi-agent only" in p.stderr
    assert not list(tmp_path.iterdir())


# ---------------------------------------------------------------- the monitor
def _records(d: Path, stem: str) -> list[dict]:
    return json.loads(gzip.decompress((d / f"{stem}.run.json.gz").read_bytes()))["assessments"]


@needs_dev
def test_per_tick_marks_add_up_to_the_evaluators_group_top1(first):
    d, _ = first
    recs = _records(d, "dev_C01_wet_coal_multi")
    truth = load_truth(episode_dir("dev_C01_wet_coal"))
    rows = build(recs, truth)["rows"]
    scored = [r["acc"] for r in rows if r["acc"]["scored"]]
    t2 = running_scores(recs, truth)["t2"]
    # a different route to the same number: marks counted tick by tick
    assert len(scored) == t2["n_scored"] > 0
    assert round(sum(a["pub"] in ("✓", "≈") for a in scored) / len(scored), 3) == t2["group_top1"]
    assert round(sum(a["bel"] in ("✓", "≈") for a in scored) / len(scored), 3) == t2["belief_group"]
    assert all(a["conf"] is not None for a in scored)
    assert all(r["acc"]["pub"] in ("", "pre") for r in rows if not r["acc"]["scored"])


@needs_dev
def test_cells_carry_each_calls_input_tokens(first):
    d, _ = first
    recs = _records(d, "dev_C01_wet_coal_multi")
    model = build(recs)
    envs = [e for a in recs for e in a["envelopes"]] + \
           [t["envelope"] for a in recs for t in a["multi"]["text"]]
    assert sum(j["in_tok"] for j in model["jobs"]) == sum(e["tokens"]["prefill"] for e in envs)
    r = next(r for r in model["rows"] if any(j["tick"] == r["tick"] and j["agent"] == "diag_heat"
                                             for j in model["jobs"]))
    j = next(j for j in model["jobs"] if j["tick"] == r["tick"] and j["agent"] == "diag_heat")
    assert f" {j['in_tok']}t" in cell(r, "diag_heat", model["jobs"], 0.0)


@needs_dev
def test_real_time_answers_get_the_tokens_of_their_own_envelope(tmp_path, monkeypatch):
    import run_demo
    monkeypatch.chdir(ROOT)
    live = tmp_path / "t.jsonl"
    monkeypatch.setattr(sys, "argv", [
        "run_demo.py", "--backend", "mock", "--arch", "multi", "--overlay", "configs/fast.yaml",
        "--mode", "realtime", "--tick-s", "0.02", "--episodes-dir", "data/episodes_dev",
        "--episode", "dev_C01_wet_coal", "--live-ticks", str(live), "--tag", "t",
        "--out", str(tmp_path)])
    run_demo.main()
    recs = [json.loads(x) for x in live.read_text().splitlines()]
    jobs = [j for j in build(recs)["jobs"] if j.get("finish_s") is not None and not j["verdict"] == "stale"]
    envs = [e for a in recs for e in a["envelopes"]] + \
           [t["envelope"] for a in recs for t in a["multi"]["text"]]
    assert jobs and all(j["in_tok"] for j in jobs)
    assert sum(j["in_tok"] for j in jobs) == sum(e["tokens"]["prefill"] for e in envs)


@needs_dev
def test_single_agent_ticks_show_diagnosis_and_verifier_calls(tmp_path):
    p = bench(tmp_path, "s", "dev_A01_fcv_seize", "--arch", "single", "--backend", "mock",
              "--plain")
    assert p.returncode == 0, p.stderr[-1500:]
    recs = _records(tmp_path / "s", "dev_A01_fcv_seize_single")
    model = build(recs, load_truth(episode_dir("dev_A01_fcv_seize")))
    assert model["arch"] == "single"
    n_env = sum(e["agent"] in ("diagnostician", "verifier") for a in recs for e in a["envelopes"])
    assert len(model["jobs"]) == n_env > 0
    assert {j["agent"] for j in model["jobs"]} <= {"diagnostician", "verifier"}


# ---------------------------------------------------------------- --arch bev
@pytest.fixture(scope="module")
def bev(tmp_path_factory):
    root = tmp_path_factory.mktemp("bev")
    p = bench(root, "b", "dev_A01_fcv_seize", "--arch", "bev", "--backend", "mock", "--plain")
    assert p.returncode == 0, p.stdout[-2000:] + p.stderr[-2000:]
    return root / "b"


@needs_dev
def test_bev_arch_saves_bev_files_with_the_deciders_counts(bev):
    t = json.loads((bev / "test.json").read_text())
    p = t["params"]
    assert p["arch"] == "bev" and p["overlay"] == "configs/bev3.yaml" and p["bev_device"] == "npu"
    assert p["models"]["bev"] == "bev-decider-0.4B-backbone-Q8_0.gguf" and p["merge_rule"] == "hybrid"
    assert [(r["stem"], r["status"]) for r in t["runs"]] == [("dev_A01_fcv_seize_bev", "done")]
    s = json.loads((bev / "dev_A01_fcv_seize_bev.summary.json").read_text())
    run = json.loads(gzip.decompress((bev / "dev_A01_fcv_seize_bev.run.json.gz").read_bytes()))
    n_env = sum(e["agent"] == "decider" for a in run["assessments"] for e in a["envelopes"])
    # counted two ways: the agent's own counters and the envelopes in the run file
    assert s["calls"]["decider"]["calls"] == n_env == s["calls"]["by_agent"]["decider"]["calls"] > 0
    assert s["calls"]["decider"]["failed"] == 0
    assert s["meta"]["replay_reproduces_published"] is True
    res = (bev / "RESULTS.md").read_text()
    assert "decider calls / failed / rejected" in res and f"| {n_env} / 0 / 0 |" in res
    assert "| yes |" in res


@needs_dev
def test_bev_monitor_shows_the_decider_and_its_picks(bev):
    from bench.stage_monitor_multi import header
    recs = _records(bev, "dev_A01_fcv_seize_bev")
    truth = load_truth(episode_dir("dev_A01_fcv_seize"))
    model = build(recs, truth)
    assert model["arch"] == "bev" and "decide·bev" in header("bev") and "rule" in header("bev")
    jobs = [j for j in model["jobs"] if j["agent"] == "decider"]
    envs = [e for a in recs for e in a["envelopes"] if e["agent"] == "decider"]
    assert len(jobs) == len(envs) > 0
    assert sum(j["in_tok"] for j in jobs) == sum(e["tokens"]["prefill"] for e in envs)
    accepted = {c["evidence_tick"] for a in recs for c in a["multi"]["compact"]
                if c.get("agent") == "decider" and c.get("ranking")}
    scored = {r["tick"] for r in model["rows"] if r["acc"]["scored"]}
    # a dec mark on exactly the scored ticks with an accepted decider answer
    assert {r["tick"] for r in model["rows"] if r["dec"]} == accepted & scored
    assert any(r["rule"] for r in model["rows"])


def test_bev_settings_are_refused_where_they_do_not_fit(tmp_path):
    p = bench(tmp_path, "x", "ep_N01_normal", "--backend", "mock", "--overlay", "configs/bev3.yaml")
    assert p.returncode != 0 and "use --arch bev" in p.stderr
    p = bench(tmp_path, "x", "ep_N01_normal", "--backend", "mock", "--arch", "bev",
              "--overlay", "configs/v3.yaml")
    assert p.returncode != 0 and "decider on" in p.stderr
    p = bench(tmp_path, "x", "ep_N01_normal", "--backend", "mock", "--arch", "bev",
              "--mode", "realtime")
    assert p.returncode != 0 and "multi-agent only" in p.stderr
    assert not list(tmp_path.iterdir())


def test_a_failed_decider_call_rejects_the_run_a_gate_rejection_does_not():
    from bench.benchmark import decider_problem
    ok = {"by_agent": {}, "decider": {"calls": 12, "failed": 0, "rejected": 3}}
    assert decider_problem(ok) is None
    assert decider_problem({**ok, "decider": {"calls": 0, "failed": 0, "rejected": 0}}) is None
    assert "failed" in decider_problem({**ok, "decider": {"calls": 12, "failed": 1, "rejected": 0}})
    assert decider_problem({"by_agent": {}}) is not None


@needs_dev
def test_older_test_settings_are_unchanged_by_the_bev_arch(first):
    d, _ = first
    p = json.loads((d / "test.json").read_text())["params"]
    assert "bev_device" not in p and set(p["models"]) == {"npu", "cpu"}
