"""
=============================================================================
 COMPACT PROMPTS AND ID-ONLY ANSWERS  (multi-agent Phase 2, "Shrink the prompt")
=============================================================================

Pure functions: prompt text in, parsed answers out. No board, no backend.

  record-facts   written by CODE from records.json (human decision a): no
                 model call, own ids R1...
  note-facts     the text reader's answer for ONE engineer note, checked
                 against a fixed vocabulary before it reaches the board.

Stdlib only (copied to the device with the rest of fieldmind/).
=============================================================================
"""

from __future__ import annotations

from pathlib import Path

PROMPT_DIR = Path(__file__).parent / "prompts"


def load_prompt(name: str) -> str:
    return (PROMPT_DIR / name).read_text()


# ======================================================================
#  Record-facts: code, no model
# ======================================================================
def record_facts(records_view: dict) -> list[dict]:
    """One record-fact per item of the Retriever's records view (already
    time-filtered to now, already code-written text). Ids R1.. in view order."""
    out = []
    for key, val in (records_view or {}).items():
        for item in (val if isinstance(val, list) else [val]):
            out.append({"id": f"R{len(out) + 1}", "key": key,
                        "text": f"{key.replace('_', ' ')}: {item}"})
    return out


# ======================================================================
#  Note-facts: the text reader's vocabulary, prompt and answer check
# ======================================================================
class NoteVocab:
    """What a note-fact may say. Subjects: the six tags, the asset model's
    equipment, and the configured extra subjects. Kinds and states: fixed
    lists from the config (multi.text_reader)."""

    def __init__(self, tags, equipment, tcfg: dict):
        self.tags = list(tags)
        self.equipment = list(equipment)
        self.extra = list(tcfg["extra_subjects"])
        self.kinds = list(tcfg["kinds"])
        self.states = list(tcfg["states"])
        self.max_pairs = int(tcfg["max_pairs"])
        self.subjects = set(self.tags) | set(self.equipment) | set(self.extra)


def text_reader_prompt(template: str, note: dict, vocab: NoteVocab) -> str:
    """Rules, the dictionary, and the ONE raw note inside a data fence."""
    return template.format(
        max_pairs=vocab.max_pairs, tags=", ".join(vocab.tags),
        equipment=", ".join(vocab.equipment), extra=", ".join(vocab.extra),
        states=", ".join(vocab.states), note=note.get("text", ""))


def check_note_answer_shape(payload: dict) -> tuple[bool, str]:
    """Shape only (decides whether a repair call is worth making)."""
    if not isinstance(payload.get("k"), str):
        return False, "missing kind k"
    s = payload.get("s")
    if not isinstance(s, list):
        return False, "s must be a list of [subject, state] pairs"
    for pair in s:
        if not (isinstance(pair, list) and len(pair) == 2
                and all(isinstance(x, str) for x in pair)):
            return False, "s must be a list of [subject, state] pairs"
    return True, ""


def check_note_answer(payload: dict, vocab: NoteVocab) -> tuple[bool, str]:
    """The gate's check: every value must come from the vocabulary. A note-fact
    with one unknown subject or state is rejected whole -- half a reading is
    worse than none, because the reader cannot tell it is half."""
    ok, why = check_note_answer_shape(payload)
    if not ok:
        return False, why
    if payload["k"] not in vocab.kinds:
        return False, f"unknown kind {payload['k']!r}"
    if len(payload["s"]) > vocab.max_pairs:
        return False, f"more than {vocab.max_pairs} pairs"
    for subject, state in payload["s"]:
        if subject not in vocab.subjects:
            return False, f"unknown subject {subject!r}"
        if state not in vocab.states:
            return False, f"unknown state {state!r}"
    return True, ""


def note_fact(nf_id: str, note: dict, payload: dict) -> dict:
    """The stored note-fact. `when` and `reliability` come from the note's own
    metadata (code), not from the model; `note_id` links back to the raw note."""
    return {"id": nf_id, "note_id": note.get("id"), "status": "ok",
            "kind": payload["k"],
            "pairs": [list(p) for p in payload["s"]],
            "t": note.get("t", 0.0), "author": note.get("author", "?"),
            "reliability": note.get("reliability")}


def _age(now_s: float, t: float) -> str:
    m = max(0.0, (now_s - t) / 60.0)
    if m < 90:
        return f"{m:.0f} min ago"
    if m < 48 * 60:
        return f"{m / 60:.0f} h ago"
    return f"{m / 1440:.0f} d ago"


def note_fact_text(nf: dict, now_s: float) -> str:
    """The line a diagnosis prompt shows for a note-fact (written by code)."""
    if nf["kind"] == "INSTR":
        body = "instruction-like text, ignored"
    else:
        body = "; ".join(f"{s} {st}" for s, st in nf["pairs"]) or "no listed subject"
    rel = "?" if nf.get("reliability") is None else f"{nf['reliability']:g}"
    return (f"{nf['id']} [note, {nf['kind']}, rel {rel}, "
            f"{_age(now_s, nf['t'])}] {body}")
