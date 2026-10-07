"""bench/bev_convert.py: the split of bev-decider-0.4B for the board.

Outcomes, not expressions: the real header (tests/data/bev/real_header.json,
the first 29,640 bytes of the published model.safetensors) is checked against
the shapes the configs imply; a miniature checkpoint is split and every output
byte is compared with the input byte it came from.
"""
import hashlib
import json
import random
import struct
from pathlib import Path

import pytest

from bench import bev_convert as bc

DATA = Path(__file__).parent / "data" / "bev"
REAL_CFG = json.loads((DATA / "config.json").read_text())
REAL_BCFG = json.loads((DATA / "backbone_config.json").read_text())
# CITED: `size` in the git-lfs pointer of model.safetensors
REAL_FILE_SIZE = 969_892_808


def _real_header():
    h = json.loads((DATA / "real_header.json").read_text())
    h.pop("__metadata__", None)
    return h


# ---------------------------------------------------------------- real model
def test_the_real_header_matches_the_shapes_the_configs_imply():
    bc.check_header(_real_header(), REAL_BCFG, REAL_CFG)


def test_the_real_header_accounts_for_every_byte_of_the_published_file():
    raw = (DATA / "real_header.json").read_bytes()
    h = _real_header()
    data_end = max(v["data_offsets"][1] for v in h.values())
    assert 8 + len(raw) + data_end == REAL_FILE_SIZE


def test_parameter_counts_by_closed_form_equal_the_header_sum():
    """Independent route: per-layer algebra from the config dimensions against
    the element count summed over the 263 real tensors."""
    h = _real_header()
    by = lambda p: sum(bc.n_elements(v["shape"]) for k, v in h.items() if k.startswith(p))
    H, I, hd = 1024, 3072, 128
    nq, nkv = 16 * hd, 8 * hd
    per_layer = (nq * H + 2 * nkv * H + H * nq) + 3 * I * H + 2 * H + 2 * hd
    layers = 20 * per_layer + H                                # + final norm
    D, T = 512, 3
    block = 3 * (D * H + D) + (H * D + H) + 4 * H + (D * H + D) + (H * D + H)
    head = T * H + 4 * H + 2 * block + 2 * (D * H + D)
    assert by("backbone.embed_tokens") == 151936 * H
    assert by("backbone.") - by("backbone.embed_tokens") == layers
    assert by("head.") == head
    assert head == 7_364_608        # README: "7.4M head"


# ---------------------------------------------------------------- miniature
MINI_BCFG = {"hidden_size": 8, "intermediate_size": 12, "head_dim": 4,
             "num_attention_heads": 2, "num_key_value_heads": 1,
             "vocab_size": 10, "num_hidden_layers": 2}
MINI_CFG = {"backbone_config": "backbone_config.json", "version": "mini",
            "head": {"new_dim": 4, "num_layers": 2, "num_task_types": 3},
            "task_types": {"choice": 0, "noul": 1, "score": 2},
            "max_state_tokens": 2048, "max_choice_tokens": 64}


def _write_safetensors(path: Path, tensors: dict, order: list) -> None:
    """A writer independent of bev_convert: data in `order`, header in name order."""
    header, blobs, off = {}, [], 0
    for k in order:
        dtype, shape, blob = tensors[k]
        header[k] = {"dtype": dtype, "shape": shape, "data_offsets": [off, off + len(blob)]}
        blobs.append(blob)
        off += len(blob)
    header = dict(sorted(header.items()))
    header["__metadata__"] = {"format": "pt"}
    hb = json.dumps(header).encode()
    path.write_bytes(struct.pack("<Q", len(hb)) + hb + b"".join(blobs))


def _read_safetensors(path: Path) -> dict:
    raw = path.read_bytes()
    n = struct.unpack("<Q", raw[:8])[0]
    header = json.loads(raw[8:8 + n])
    header.pop("__metadata__", None)
    return {k: (v["dtype"], v["shape"], raw[8 + n + v["data_offsets"][0]:8 + n + v["data_offsets"][1]])
            for k, v in header.items()}


def _mini(tmp_path: Path, mutate=None) -> tuple[Path, dict]:
    rng = random.Random(7)
    shapes = bc.expected_shapes(MINI_BCFG, MINI_CFG)
    tensors = {}
    for k, s in shapes.items():
        dtype = "F32" if k.startswith("head.") else "BF16"
        n = bc.n_elements(s) * bc.DTYPE_BYTES[dtype]
        tensors[k] = (dtype, s, bytes(rng.randrange(256) for _ in range(n)))
    if mutate:
        mutate(tensors)
    order = list(tensors)
    rng.shuffle(order)                  # data order differs from name order
    d = tmp_path / "model"
    d.mkdir()
    _write_safetensors(d / "model.safetensors", tensors, order)
    (d / "config.json").write_text(json.dumps(MINI_CFG))
    (d / "backbone_config.json").write_text(json.dumps(MINI_BCFG))
    for name in bc.TOKENIZER_FILES:
        (d / name).write_text(f"tokenizer file {name}")
    return d, tensors


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_split_copies_every_byte_to_the_right_place(tmp_path):
    d, tensors = _mini(tmp_path)
    out = tmp_path / "out"
    info = bc.split(d, out, expect_sha256=_sha(d / "model.safetensors"))

    got = _read_safetensors(out / "backbone" / "model.safetensors")
    want_bb = {"model." + k[len("backbone."):]: v for k, v in tensors.items()
               if k.startswith("backbone.")}
    assert got == want_bb                                    # names, dtypes, shapes, bytes

    manifest = json.loads((out / "bev_head.json").read_text())
    blob = (out / "bev_head.bin").read_bytes()
    heads = {k[len("head."):]: v for k, v in tensors.items() if k.startswith("head.")}
    assert set(manifest["tensors"]) == set(heads)
    for name, t in manifest["tensors"].items():
        assert t["shape"] == heads[name][1]
        assert blob[t["offset"]:t["offset"] + t["nbytes"]] == heads[name][2]
    assert len(blob) == sum(len(v[2]) for v in heads.values()) == info["head_bytes"]

    assert json.loads((out / "backbone" / "config.json").read_text()) == MINI_BCFG
    for name in bc.TOKENIZER_FILES:
        assert (out / "backbone" / name).read_text() == f"tokenizer file {name}"
    assert manifest["layer_norm_eps"] == 1e-5 and manifest["gelu"] == "erf"
    assert manifest["answer_prompt"] == "The answer is:"


def test_a_git_lfs_pointer_is_refused(tmp_path):
    d, _ = _mini(tmp_path)
    (d / "model.safetensors").write_text(
        "version https://git-lfs.github.com/spec/v1\noid sha256:00\nsize 1\n")
    with pytest.raises(bc.SplitError, match="git lfs pull"):
        bc.split(d, tmp_path / "out", expect_sha256=None)


def test_a_tokenizer_pointer_is_refused(tmp_path):
    d, _ = _mini(tmp_path)
    (d / "tokenizer.json").write_text("version https://git-lfs.github.com/spec/v1\n")
    with pytest.raises(bc.SplitError, match="tokenizer.json"):
        bc.split(d, tmp_path / "out", expect_sha256=_sha(d / "model.safetensors"))


def test_a_different_file_is_refused_by_its_sha256(tmp_path):
    d, _ = _mini(tmp_path)
    with pytest.raises(bc.SplitError, match="sha256"):
        bc.split(d, tmp_path / "out", expect_sha256="0" * 64)


def test_a_wrong_shape_is_refused(tmp_path):
    def wide(t):
        k = "backbone.layers.1.mlp.up_proj.weight"
        dtype, shape, _ = t[k]
        t[k] = (dtype, [shape[0] + 1, shape[1]], bytes(2 * (shape[0] + 1) * shape[1]))
    d, _ = _mini(tmp_path, wide)
    with pytest.raises(bc.SplitError, match="shapes differ"):
        bc.split(d, tmp_path / "out", expect_sha256=None)


def test_an_extra_or_missing_tensor_is_refused(tmp_path):
    def extra(t):
        t["backbone.lm_head.weight"] = ("BF16", [10, 8], bytes(160))
        del t["head.layers.1.attn.o.bias"]
    d, _ = _mini(tmp_path, extra)
    with pytest.raises(bc.SplitError, match="missing.*head.layers.1.attn.o.bias.*extra.*lm_head"):
        bc.split(d, tmp_path / "out", expect_sha256=None)


def test_a_bf16_head_is_refused(tmp_path):
    def bf16(t):
        k = "head.answer_proj.bias"
        _, shape, _ = t[k]
        t[k] = ("BF16", shape, bytes(2 * bc.n_elements(shape)))
    d, _ = _mini(tmp_path, bf16)
    with pytest.raises(bc.SplitError, match="expected F32"):
        bc.split(d, tmp_path / "out", expect_sha256=None)
