"""
Split bev-decider-0.4B into the two parts the board runs (bev-decider plan,
Part A task 2; reports/bev_decider.md).

  .venv/bin/python -m bench.bev_convert <model_dir> <out_dir>

<model_dir> is the Hugging Face folder (avbiswas/bev-decider-0.4B, after
`git lfs pull`). Writes:

  <out_dir>/backbone/        a plain Qwen3 checkpoint for llama.cpp's
                             convert_hf_to_gguf.py: model.safetensors with the
                             `backbone.*` tensors renamed `model.*` (bytes
                             unchanged, bf16 stays bf16), config.json (=
                             backbone_config.json) and the tokenizer files
  <out_dir>/bev_head.bin     the decision head, fp32 little-endian, tensors
                             back to back (bytes unchanged)
  <out_dir>/bev_head.json    manifest: shape and byte offset of every head
                             tensor, the head's dimensions, and the encoding
                             constants bev-decide must reproduce

Nothing is converted numerically: every tensor is copied byte for byte, so
the split cannot change a weight. Shapes are checked against the shapes the two
config files imply (`expected_shapes`) before anything is written; a tensor
that is missing, extra, or a different shape stops the split.

Stdlib only (safetensors is a JSON header + raw bytes: 8-byte little-endian
header length, header {name: {dtype, shape, data_offsets}}, then the data).
"""
from __future__ import annotations

import hashlib
import json
import shutil
import struct
import sys
from pathlib import Path

# CITED: oid of model.safetensors in the git-lfs pointer of
# huggingface.co/avbiswas/bev-decider-0.4B (main, cloned 2026-10-07).
EXPECTED_SHA256 = "e28f9f5ac08bd939b50021bce652e1f87530ff8a187fbeb3c7ec024b6c844282"

# CITED: bev_decider 0.2.1 (PyPI wheel), bev_decider/encode.py. bev-decide must
# build exactly this text around the state, the question and the options.
TASK_PROMPTS = {"choice": "Choose the best option.",
                "score": "Rate it on the given scale.",
                "noul": "Answer yes or no."}
ANSWER_PROMPT = "The answer is:"
OPTION_BEGIN, OPTION_END = "<option>", "</option>"
# CITED: torch.nn.LayerNorm default eps and torch.nn.GELU default
# (approximate="none", the exact erf form); bev_decider/model.py uses both
# with defaults.
LAYER_NORM_EPS = 1e-5
GELU = "erf"

TOKENIZER_FILES = ("tokenizer.json", "tokenizer_config.json", "vocab.json", "merges.txt")
LFS_MAGIC = b"version https://git-lfs"
DTYPE_BYTES = {"F32": 4, "BF16": 2, "F16": 2}


class SplitError(ValueError):
    """The input is not the model this split was written for."""


# ---------------------------------------------------------------------------
def read_header(path: Path) -> tuple[dict, int]:
    """(tensors {name: {dtype, shape, data_offsets}}, byte offset of the data)."""
    with open(path, "rb") as f:
        head = f.read(len(LFS_MAGIC))
        if head == LFS_MAGIC:
            raise SplitError(f"{path} is a git-lfs pointer, not the weights: "
                             f"run `git lfs pull` in {path.parent}")
        f.seek(0)
        n = struct.unpack("<Q", f.read(8))[0]
        header = json.loads(f.read(n))
    header.pop("__metadata__", None)
    return header, 8 + n


def n_elements(shape) -> int:
    p = 1
    for d in shape:
        p *= d
    return p


def expected_shapes(backbone_cfg: dict, cfg: dict) -> dict[str, list[int]]:
    """Every tensor the checkpoint must hold, with its shape, from the two
    config files alone: a Qwen3 decoder without lm_head (tied embeddings,
    bev_decider loads Qwen3Model) and bev_decider/model.py's ChoiceHead."""
    H = backbone_cfg["hidden_size"]
    I = backbone_cfg["intermediate_size"]
    hd = backbone_cfg["head_dim"]
    nq = backbone_cfg["num_attention_heads"] * hd
    nkv = backbone_cfg["num_key_value_heads"] * hd
    V = backbone_cfg["vocab_size"]
    out = {"backbone.embed_tokens.weight": [V, H], "backbone.norm.weight": [H]}
    for i in range(backbone_cfg["num_hidden_layers"]):
        p = f"backbone.layers.{i}."
        out.update({
            p + "input_layernorm.weight": [H],
            p + "post_attention_layernorm.weight": [H],
            p + "self_attn.q_proj.weight": [nq, H],
            p + "self_attn.k_proj.weight": [nkv, H],
            p + "self_attn.v_proj.weight": [nkv, H],
            p + "self_attn.o_proj.weight": [H, nq],
            p + "self_attn.q_norm.weight": [hd],
            p + "self_attn.k_norm.weight": [hd],
            p + "mlp.gate_proj.weight": [I, H],
            p + "mlp.up_proj.weight": [I, H],
            p + "mlp.down_proj.weight": [H, I],
        })
    D = cfg["head"]["new_dim"]
    out.update({"head.task_embedding.weight": [cfg["head"]["num_task_types"], H],
                "head.input_norm.weight": [H], "head.input_norm.bias": [H],
                "head.final_norm.weight": [H], "head.final_norm.bias": [H],
                "head.answer_proj.weight": [D, H], "head.answer_proj.bias": [D],
                "head.choice_proj.weight": [D, H], "head.choice_proj.bias": [D]})
    for i in range(cfg["head"]["num_layers"]):
        p = f"head.layers.{i}."
        for n in ("norm1", "norm2"):
            out[p + n + ".weight"] = [H]
            out[p + n + ".bias"] = [H]
        for n in ("q", "k", "v"):
            out[p + f"attn.{n}.weight"] = [D, H]
            out[p + f"attn.{n}.bias"] = [D]
        out[p + "attn.o.weight"] = [H, D]
        out[p + "attn.o.bias"] = [H]
        out[p + "mlp.0.weight"] = [D, H]        # Linear(H, D)
        out[p + "mlp.0.bias"] = [D]
        out[p + "mlp.2.weight"] = [H, D]        # Linear(D, H)
        out[p + "mlp.2.bias"] = [H]
    return out


def check_header(header: dict, backbone_cfg: dict, cfg: dict) -> None:
    want = expected_shapes(backbone_cfg, cfg)
    missing = sorted(set(want) - set(header))
    extra = sorted(set(header) - set(want))
    if missing or extra:
        raise SplitError(f"tensor names differ from the configs: missing {missing[:5]}"
                         f"{'...' if len(missing) > 5 else ''}, extra {extra[:5]}"
                         f"{'...' if len(extra) > 5 else ''}")
    bad = {k: (header[k]["shape"], want[k]) for k in want if header[k]["shape"] != want[k]}
    if bad:
        raise SplitError(f"shapes differ from the configs (found, expected): {bad}")
    for k, v in header.items():
        if v["dtype"] not in DTYPE_BYTES:
            raise SplitError(f"{k}: dtype {v['dtype']} not handled")
        b, e = v["data_offsets"]
        if e - b != n_elements(v["shape"]) * DTYPE_BYTES[v["dtype"]]:
            raise SplitError(f"{k}: {e - b} bytes for shape {v['shape']} {v['dtype']}")
        if k.startswith("head.") and v["dtype"] != "F32":
            # bev_decider runs the head in fp32; bev-decide reads fp32 only
            raise SplitError(f"{k}: head tensor is {v['dtype']}, expected F32")


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1 << 24):
            h.update(chunk)
    return h.hexdigest()


def _copy_range(src, dst, start: int, length: int) -> None:
    src.seek(start)
    while length > 0:
        chunk = src.read(min(length, 1 << 24))
        if not chunk:
            raise SplitError("weights file ends early")
        dst.write(chunk)
        length -= len(chunk)


# ---------------------------------------------------------------------------
def split(model_dir: Path, out_dir: Path, expect_sha256: str | None = EXPECTED_SHA256) -> dict:
    model_dir, out_dir = Path(model_dir), Path(out_dir)
    weights = model_dir / "model.safetensors"
    cfg = json.loads((model_dir / "config.json").read_text())
    bcfg = json.loads((model_dir / cfg["backbone_config"]).read_text())
    header, data0 = read_header(weights)
    check_header(header, bcfg, cfg)
    if expect_sha256 is not None:
        got = sha256_of(weights)
        if got != expect_sha256:
            raise SplitError(f"sha256 {got} != expected {expect_sha256}")
    for name in TOKENIZER_FILES:
        with open(model_dir / name, "rb") as f:
            if f.read(len(LFS_MAGIC)) == LFS_MAGIC:
                raise SplitError(f"{name} is a git-lfs pointer: run `git lfs pull`")

    order = sorted(header, key=lambda k: header[k]["data_offsets"][0])
    bb = [k for k in order if k.startswith("backbone.")]
    hd = [k for k in order if k.startswith("head.")]

    # ---- backbone -> plain Qwen3 checkpoint (keys model.*, same bytes)
    (out_dir / "backbone").mkdir(parents=True, exist_ok=True)
    new_header, off = {}, 0
    for k in bb:
        v = header[k]
        n = v["data_offsets"][1] - v["data_offsets"][0]
        new_header["model." + k[len("backbone."):]] = {
            "dtype": v["dtype"], "shape": v["shape"], "data_offsets": [off, off + n]}
        off += n
    new_header["__metadata__"] = {"format": "pt"}
    hbytes = json.dumps(new_header, separators=(",", ":")).encode()
    hbytes += b" " * (-len(hbytes) % 8)            # spec: pad header to 8 bytes
    with open(weights, "rb") as src, \
            open(out_dir / "backbone" / "model.safetensors", "wb") as dst:
        dst.write(struct.pack("<Q", len(hbytes)))
        dst.write(hbytes)
        for k in bb:
            b, e = header[k]["data_offsets"]
            _copy_range(src, dst, data0 + b, e - b)
    (out_dir / "backbone" / "config.json").write_text(json.dumps(bcfg, indent=2) + "\n")
    for name in TOKENIZER_FILES:
        shutil.copyfile(model_dir / name, out_dir / "backbone" / name)

    # ---- head -> one fp32 blob + manifest
    tensors, off = {}, 0
    with open(weights, "rb") as src, open(out_dir / "bev_head.bin", "wb") as dst:
        for k in hd:
            b, e = header[k]["data_offsets"]
            _copy_range(src, dst, data0 + b, e - b)
            tensors[k[len("head."):]] = {"shape": header[k]["shape"], "offset": off,
                                         "nbytes": e - b}
            off += e - b
    manifest = {
        "source": {"repo": "avbiswas/bev-decider-0.4B", "sha256": expect_sha256,
                   "model_version": cfg.get("version"),
                   "encoding_from": "bev_decider 0.2.1 encode.py"},
        "dtype": "F32", "byteorder": "little",
        "hidden_dim": bcfg["hidden_size"], "new_dim": cfg["head"]["new_dim"],
        "num_layers": cfg["head"]["num_layers"],
        "num_task_types": cfg["head"]["num_task_types"],
        "task_types": cfg["task_types"],
        "layer_norm_eps": LAYER_NORM_EPS, "gelu": GELU,
        "max_state_tokens": cfg["max_state_tokens"],
        "max_choice_tokens": cfg["max_choice_tokens"],
        "task_prompts": TASK_PROMPTS, "answer_prompt": ANSWER_PROMPT,
        "option_begin": OPTION_BEGIN, "option_end": OPTION_END,
        "tensors": tensors,
    }
    (out_dir / "bev_head.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return {"backbone_tensors": len(bb), "head_tensors": len(hd),
            "backbone_params": sum(n_elements(header[k]["shape"]) for k in bb),
            "head_params": sum(n_elements(header[k]["shape"]) for k in hd),
            "head_bytes": off}


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__.strip().splitlines()[3].strip())
        return 2
    try:
        info = split(Path(argv[0]), Path(argv[1]))
    except SplitError as e:
        print(f"STOP: {e}")
        return 3
    print(json.dumps(info, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
