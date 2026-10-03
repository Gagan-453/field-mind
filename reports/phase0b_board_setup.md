# Phase 0b / board setup (Fedora laptop + QIDK) — report

## Status
PARTIAL — in progress. Sections below are filled as each step lands.

## Human decision: quantization recipe (recorded before any board run)

**Decision (human, 2026-10-03), identical for all 4 candidates** (Llama 3.2 3B Instruct, Qwen3 1.7B, Gemma 3 1B QAT,
Qwen2.5 0.5B Instruct):

- every weight matrix Q4_0; token embedding and output at Q8_0. Both types are allowed by the committed rule
  ("every weight matrix Q4_0 or Q8_0", `reports/phase0b_lanes_model_choice.md`, hard constraints).
- built with `llama-quantize --pure --token-embedding-type q8_0 --output-tensor-type q8_0 <src> <dst> Q4_0`;
- from the original 16-bit weights: official safetensors through `convert_hf_to_gguf.py`. If a repo is gated and not
  yet approved, a well-known F16/BF16 GGUF mirror, with repo, file and sha256 recorded;
- Gemma: if Google's QAT Q4_0 GGUF already matches this recipe under `bench.gguf_types`, use it as is; otherwise
  build it from `google/gemma-3-1b-it-qat-q4_0-unquantized`.

**Reason (human):** published "Q4_0" files carry K-quant / Q4_1 tensors, which fall back to the CPU on HTP. Confirmed
on the board's `geniex/models/Llama-3.2-3B-Instruct-Q4_0.gguf` (bartowski, 1,921,909,280 B), whose header has
`token_embd.weight` (tied output) at Q6_K and 3 `ffn_down` tensors at Q4_1 (`bench.gguf_types`, 2026-10-03).

**Earlier 3B rates are on the impure file.** The earlier Llama 3.2 3B rates, 839 tok/s prefill and 11.7 tok/s
decode (figures reported by the human; their measurement is not in this repo), were measured on that impure file.
They are not comparable with any rate from the recipe above and must not be mixed with them.
