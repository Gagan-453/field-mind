"""bench/belief_saturation.summarise on a hand-built run: counts, not formulas."""
from bench.belief_saturation import summarise
from fieldmind.agent.world_model import CLAMP


def _tick(k, lo, conf, refs=("RCA-14", "RCA-18")):
    brk = [{"case_ref": refs[0], "log_odds": lo[0], "confidence": 0.5},
           {"case_ref": refs[1], "log_odds": lo[1], "confidence": 0.5}]
    return {"tick": k, "belief_ranking": brk,
            "hypotheses": [{"case_ref": refs[0], "confidence": conf}]}


def _run(ticks):
    gt = {"family": "C", "root_cause_id": "RCA-14", "fault_onset_t": 0}
    return {"episode_id": "x", "ground_truth": gt, "assessments": ticks}


def test_counts_clamp_ties_and_confident_wrong_group():
    ticks = [
        _tick(1, (CLAMP, CLAMP), 0.982),                  # tie AT clamp, right group
        _tick(2, (CLAMP, 1.0), 0.982),                    # at clamp, no tie
        _tick(3, (1.5, 1.5), 0.82),                       # tie below clamp
        _tick(4, (0.2, 0.1), 0.55, refs=("RCA-11", "RCA-14")),   # confident, wrong group
        _tick(5, (0.1, 0.0), 0.3),                        # low confidence
    ]
    s = summarise([_run(ticks)])["library"]
    assert s["ticks"] == 5
    assert s["rank1_at_clamp"] == 2
    assert s["ties"] == 2 and s["ties_at_clamp"] == 1
    assert s["confident_and_wrong_group"] == 1
    assert s["shown_conf_deciles"][9] == 2 and s["shown_conf_deciles"][3] == 1


def test_no_fault_class_counts_every_tick_with_belief():
    gt = {"family": "N", "root_cause_id": "NONE", "fault_onset_t": None}
    run = {"episode_id": "n", "ground_truth": gt,
           "assessments": [_tick(1, (CLAMP, 0.0), 0.982),
                           {"tick": 2, "belief_ranking": [], "hypotheses": []}]}
    s = summarise([run])["no-fault"]
    assert s["ticks"] == 1 and s["rank1_at_clamp"] == 1
