"""device/bev_decide/bev_core.hpp: the token layout and the decision head that
bev-decide runs on the board, checked on the host.

Layout: bev's OWN encode.py (tests/data/bev/bev_decider_encode.py, copied
unchanged, run with a minimal stand-in for the three torch calls it makes) and
the C++ layout get the same toy byte tokenizer and the same questions. Token
ids, position ids, read indices and the attention mask must be identical. The
C++ side emits no mask: its mask is IMPLIED by the sequence plan bev_decide.cpp
uses on llama.cpp (prompt seq 0, option i seq i+1, answer seq N+1, cells copied
between sequences), replayed here with llama.cpp's visibility rule. Whether
llama.cpp itself follows that rule on the board is checked there (conformance),
not here.

Head: random weights, the C++ forward against a pure-Python forward written
from bev_decider/model.py, and the order-invariance bev claims.
"""
import importlib.util
import json
import math
import random
import shutil
import struct
import subprocess
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "device" / "bev_decide"
REF = Path(__file__).parent / "data" / "bev" / "bev_decider_encode.py"

pytestmark = pytest.mark.skipif(shutil.which("c++") is None, reason="no C++ compiler")


@pytest.fixture(scope="module")
def core(tmp_path_factory):
    exe = tmp_path_factory.mktemp("bev") / "test_core"
    subprocess.run(["c++", "-std=c++17", "-O2", "-o", str(exe), str(SRC / "test_core.cpp")],
                   check=True, capture_output=True)
    return exe


# ------------------------------------------------------------- bev's encode.py
class _Mat:
    """Just enough of a 2-D torch tensor for Encoder.encode's mask writes."""

    def __init__(self, r, c, fill=0.0):
        self.r, self.c = r, c
        self.v = [[fill] * c for _ in range(r)]

    def __setitem__(self, key, val):
        rs, cs = key
        rows = range(*rs.indices(self.r))
        cols = range(*cs.indices(self.c))
        for a, i in enumerate(rows):
            for b, j in enumerate(cols):
                self.v[i][j] = val.v[a][b] if isinstance(val, _Mat) else float(val)


def _tril(m):
    out = _Mat(m.r, m.c)
    out.v = [[m.v[i][j] if j <= i else 0.0 for j in range(m.c)] for i in range(m.r)]
    return out


def _load_reference():
    fake = types.ModuleType("torch")
    fake.zeros = lambda r, c: _Mat(r, c, 0.0)
    fake.ones = lambda r, c: _Mat(r, c, 1.0)
    fake.tril = _tril
    saved = sys.modules.get("torch")
    sys.modules["torch"] = fake
    try:
        spec = importlib.util.spec_from_file_location("bev_decider_encode", REF)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    finally:
        if saved is None:
            del sys.modules["torch"]
        else:
            sys.modules["torch"] = saved
    return mod


class _ByteTok:
    """One token per byte, id = byte + 1000 (same as test_core.cpp)."""

    def encode(self, text):
        return [b + 1000 for b in text.encode()]

    def decode(self, ids):
        return bytes(i - 1000 for i in ids).decode()


def _reference(state, question, max_state, max_choice):
    enc = _load_reference().Encoder(_ByteTok(), max_state, max_choice)
    return enc.encode(state, question)


def _cpp(core, state, question, max_state, max_choice):
    crit = question.get("criteria")
    if isinstance(crit, dict):
        pairs = list(crit.items())
    elif isinstance(crit, list):
        pairs = [(str(i), v) for i, v in enumerate(crit)]
    else:
        pairs = []
    fields = [state, question["type"], question["instructions"], str(max_state),
              str(max_choice), str(len(pairs))] + [x for kv in pairs for x in kv]
    data = b"".join(f"{len(f.encode())}\n".encode() + f.encode() for f in fields)
    out = subprocess.run([str(core), "layout"], input=data, capture_output=True, check=True)
    return json.loads(out.stdout)


def _implied(lay):
    """(input_ids, position_ids, mask, read_idx, answer_end_idx) from the C++
    layout under bev_decide.cpp's sequence plan and llama.cpp's rule: a token
    sees a cell iff the cell carries the token's sequence and is not after it."""
    P, N = len(lay["prompt"]), len(lay["options"])
    A = N + 1
    toks = []                                    # (id, pos, seq, step)
    toks += [(t, p, 0, 1) for p, t in enumerate(lay["prompt"])]
    read = []
    for i, o in enumerate(lay["options"]):
        read.append(len(toks) + lay["read_idx"][i])
        toks += [(t, P + k, i + 1, 2) for k, t in enumerate(o)]
    toks += [(t, lay["answer_pos0"] + k, A, 3) for k, t in enumerate(lay["answer"])]
    L = len(toks)

    def cell_seqs(u, step):
        """Sequences cell u carries when a token of decode `step` attends."""
        _, _, s, made = toks[u]
        if made > step:
            return set()                         # not decoded yet
        seqs = {s}
        if made == 1 and step >= 2:
            seqs |= set(range(1, N + 1))         # seq_cp(0 -> i) after step 1
        if step >= 3 and made in (1, 2):
            seqs.add(A)                          # seq_cp(0 -> A), seq_cp(i -> A, P, -1)
        return seqs

    mask = [[1.0 if (toks[t][2] in cell_seqs(u, toks[t][3]) and toks[u][1] <= toks[t][1]) else 0.0
             for u in range(L)] for t in range(L)]
    return ([t[0] for t in toks], [t[1] for t in toks], mask, read, L - 1)


CASES = [
    ("choice, three options of different lengths",
     "[RATE/WARN] bed_temp_avg rising 2.1 C/min\n[BALANCE/ALARM] water_balance DEFICIT",
     {"type": "choice", "instructions": "Which root cause best explains the plant facts?",
      "criteria": {"RCA-07": "Bed temperature runaway from loss of ash recirculation cooling",
                   "RCA-14": "PA line choke", "RCA-18": ""}}, 2048, 64),
    ("noul without criteria", "drum level falling", {"type": "noul", "instructions": "Is it a leak?"}, 2048, 64),
    ("noul with criteria", "x", {"type": "noul", "instructions": "q?",
                                 "criteria": {"true": "it is", "false": "it is not"}}, 2048, 64),
    ("score levels", "state", {"type": "score", "instructions": "How bad?",
                               "criteria": ["fine", "watch", "act now"]}, 2048, 64),
    ("state and options truncated", "abcdefghij" * 30,
     {"type": "choice", "instructions": "q", "criteria": {"A": "x" * 100, "B": "short"}}, 50, 8),
    ("single option", "s", {"type": "choice", "instructions": "q", "criteria": {"ONLY": "one"}}, 2048, 64),
]


@pytest.mark.parametrize("name,state,question,ms,mc", CASES, ids=[c[0] for c in CASES])
def test_cpp_layout_reproduces_bev_encode(core, name, state, question, ms, mc):
    ref = _reference(state, question, ms, mc)
    lay = _cpp(core, state, question, ms, mc)
    ids, pos, mask, read, ans_end = _implied(lay)
    assert ids == ref["input_ids"]
    assert pos == list(ref["position_ids"])
    assert read == ref["choice_read_idx"]
    assert ans_end == ref["answer_end_idx"]
    assert lay["keys"] == ref["keys"]
    assert lay["task_type"] == ref["task_type"]
    assert mask == ref["attention_mask"].v


def test_an_unknown_question_type_is_refused(core):
    with pytest.raises(subprocess.CalledProcessError):
        _cpp(core, "s", {"type": "rank", "instructions": "q", "criteria": {"A": "a"}}, 2048, 64)


# ------------------------------------------------------------- decision head
H, D, LAYERS, TASKS, EPS = 8, 4, 2, 3, 1e-5


def _head_shapes():
    s = {"task_embedding.weight": [TASKS, H]}
    for n in ("input_norm", "final_norm"):
        s[n + ".weight"], s[n + ".bias"] = [H], [H]
    for n in ("answer_proj", "choice_proj"):
        s[n + ".weight"], s[n + ".bias"] = [D, H], [D]
    for l in range(LAYERS):
        p = f"layers.{l}."
        for n in ("norm1", "norm2"):
            s[p + n + ".weight"], s[p + n + ".bias"] = [H], [H]
        for n in ("attn.q", "attn.k", "attn.v", "mlp.0"):
            s[p + n + ".weight"], s[p + n + ".bias"] = [D, H], [D]
        for n in ("attn.o", "mlp.2"):
            s[p + n + ".weight"], s[p + n + ".bias"] = [H, D], [H]
    return s


@pytest.fixture(scope="module")
def head_files(tmp_path_factory):
    rng = random.Random(3)
    d = tmp_path_factory.mktemp("head")
    weights, blob, idx, off = {}, b"", [], 0
    for name, shape in _head_shapes().items():
        n = math.prod(shape)
        vals = [rng.gauss(0, 0.5) for _ in range(n)]
        if name.endswith("norm.weight") or ".norm" in name and name.endswith(".weight"):
            vals = [1.0 + 0.2 * v for v in vals]
        raw = struct.pack(f"<{n}f", *vals)
        weights[name] = (list(struct.unpack(f"<{n}f", raw)), shape)   # fp32-rounded
        blob += raw
        idx.append(f"{name} {off} {len(raw)} " + " ".join(map(str, shape)))
        off += len(raw)
    (d / "head.bin").write_bytes(blob)
    (d / "head.idx").write_text("\n".join(idx) + "\n")
    return d, weights


def _ref_head(w, choices, answer, task):
    """bev_decider/model.py ChoiceHead.forward, no padding, in plain Python."""
    def lin(x, n):
        W, (o, i) = w[n + ".weight"][0], w[n + ".weight"][1]
        b = w[n + ".bias"][0]
        return [b[r] + sum(W[r * i + c] * x[c] for c in range(i)) for r in range(o)]

    def ln(x, n):
        m = sum(x) / len(x)
        v = sum((z - m) ** 2 for z in x) / len(x)
        g, b = w[n + ".weight"][0], w[n + ".bias"][0]
        return [(z - m) / math.sqrt(v + EPS) * g[k] + b[k] for k, z in enumerate(x)]

    def softmax(s):
        m = max(s)
        e = [math.exp(z - m) for z in s]
        return [z / sum(e) for z in e]

    te = w["task_embedding.weight"][0]
    x = [te[task * H:(task + 1) * H]] + [list(c) for c in choices] + [list(answer)]
    x = [ln(r, "input_norm") for r in x]
    for l in range(LAYERS):
        p = f"layers.{l}."
        h = [ln(r, p + "norm1") for r in x]
        q = [lin(r, p + "attn.q") for r in h]
        k = [lin(r, p + "attn.k") for r in h]
        v = [lin(r, p + "attn.v") for r in h]
        new = []
        for i in range(len(x)):
            s = softmax([sum(a * b for a, b in zip(q[i], k[j])) / math.sqrt(D) for j in range(len(x))])
            att = [sum(s[j] * v[j][d] for j in range(len(x))) for d in range(D)]
            o = lin(att, p + "attn.o")
            new.append([a + b for a, b in zip(x[i], o)])
        x = new
        for i in range(len(x)):
            m = lin(ln(x[i], p + "norm2"), p + "mlp.0")
            m = [0.5 * z * (1 + math.erf(z / math.sqrt(2))) for z in m]
            m = lin(m, p + "mlp.2")
            x[i] = [a + b for a, b in zip(x[i], m)]
    x = [ln(r, "final_norm") for r in x]
    a = lin(x[-1], "answer_proj")
    return softmax([sum(p * q for p, q in zip(a, lin(c, "choice_proj"))) / math.sqrt(D)
                    for c in x[1:-1]])


def _cpp_head(core, files, choices, answer, task):
    d, _ = files
    nums = f"{task} {len(choices)} " + " ".join(repr(z) for r in choices for z in r) \
        + " " + " ".join(repr(z) for z in answer)
    out = subprocess.run([str(core), "head", str(d / "head.bin"), str(d / "head.idx"),
                          str(H), str(D), str(LAYERS), str(TASKS), str(EPS)],
                         input=nums.encode(), capture_output=True, check=True)
    return [float(x) for x in out.stdout.split()]


def _f32(xs):
    return list(struct.unpack(f"<{len(xs)}f", struct.pack(f"<{len(xs)}f", *xs)))


def _inputs(seed, C):
    rng = random.Random(seed)
    return [_f32([rng.gauss(0, 1) for _ in range(H)]) for _ in range(C)], \
        _f32([rng.gauss(0, 1) for _ in range(H)])


@pytest.mark.parametrize("C,task", [(3, 0), (2, 1), (5, 2), (1, 0)])
def test_cpp_head_equals_the_python_forward(core, head_files, C, task):
    choices, answer = _inputs(C * 10 + task, C)
    got = _cpp_head(core, head_files, choices, answer, task)
    want = _ref_head(head_files[1], choices, answer, task)
    assert len(got) == C
    assert max(abs(a - b) for a, b in zip(got, want)) < 1e-12
    assert abs(sum(got) - 1.0) < 1e-12


def test_cpp_head_is_order_invariant(core, head_files):
    choices, answer = _inputs(99, 6)
    base = _cpp_head(core, head_files, choices, answer, 0)
    perm = list(range(6))
    random.Random(5).shuffle(perm)
    shuffled = _cpp_head(core, head_files, [choices[i] for i in perm], answer, 0)
    assert max(abs(shuffled[k] - base[i]) for k, i in enumerate(perm)) < 1e-12
    assert len(set(round(p, 6) for p in base)) == 6      # not trivially uniform
