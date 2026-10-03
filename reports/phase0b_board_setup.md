# Phase 0b / board setup (Fedora laptop + QIDK) — report

## Status
PARTIAL — laptop side done: llama.cpp pinned and built (Android Hexagon package + host `llama-quantize`), package pushed
and checksum-verified, all 4 candidate GGUFs built to the recipe and checked. Not done (board unplugged by the human):
pushing the GGUFs, the smoke test, and committing the CLAUDE.md / `/board-up` updates. Step-by-step state:
`reports/session2_setup_progress.md`.

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

## Human decision: context size and slots (2026-10-03)
`llama-server` is always launched with `-c 4096 -np 1`, the same for every model and both lanes, because the
single-agent prompt is ~2484 tokens and context size changes NPU speed. Code: `bench/board.py` (`CTX_SIZE`,
`N_PARALLEL`, `lane_command`); test: `tests/test_board_env.py::test_lanes_always_use_ctx_4096_np_1`.

## Human decisions on the mirror, EOS and launch flags (2026-10-03, after the laptop-side build)
1. **Safetensors mirrors accepted for the two gated models.** Reason: the weights are the official files. How the
   identity was established: the Hub's API (`model_info(..., files_metadata=True)`) returns the LFS sha256 of every
   file even for a gated repo that cannot be downloaded. Those published hashes were read for the official repos and
   compared with the mirrors' published hashes, then `~/fieldmind-build/fetch_weights.py` recomputed sha256 over the
   downloaded bytes and required equality (`logs/fetch_weights.log`, `OK` lines):
   - `meta-llama/Llama-3.2-3B-Instruct` == `unsloth/Llama-3.2-3B-Instruct`:
     `model-00001-of-00002.safetensors` `13cbd6d16e927a0c5bad54102514e6e18b4a47b3a6eb911e39d678d328d19f55`,
     `model-00002-of-00002.safetensors` `7b770216613ac5c34d7c54bdff1fa616bc4e338a9d0b20af6303e48c295ee23c`;
   - `google/gemma-3-1b-it-qat-q4_0-unquantized` == `unsloth/gemma-3-1b-it-qat`:
     `model.safetensors` `6d571889049c5550a2cdcc3e1846646e595b683ce0d3c7bea904ed8874cf8ef2`,
     `tokenizer.model` `1299c11d7cf632ef3b4e11937501358ada021bbdf7c47638d13c0ee982f2e79c`.
   Limit: the identity covers those LFS files only. The mirrors' small JSON files differ from the official ones.
2. **Gemma EOS id = 1 accepted**, to match Google's own GGUF.
3. **`-fit off` accepted on both lanes**, so the server cannot change the context size or the offload on its own.
   **`-lv 4` is NOT yet accepted**: it waits for the measured cost (smoke test, step C).

## What was built
- **llama.cpp pin:** `ggml-org/llama.cpp` tag `b11371`, commit `99b95488cac0f00ce3f05af113a8c1e287753f87`.
- **Android package:** container `ghcr.io/snapdragon-toolchain/arm64-android:v0.7` (digest `sha256:c012b817...`,
  NDK r29, Hexagon SDK 6.6.0.0), preset `arm64-android-snapdragon-release` plus `-DLLAMA_BUILD_SERVER=ON
  -DLLAMA_OPENSSL=OFF`. On the board at `/data/local/tmp/llm/llama.cpp`; 134 files, board sha256 == laptop sha256.
  `llama-server --version` on the board: `build 11371, commit 99b95488c`; `--list-devices` shows `HTP0: Hexagon`.
- **Host build:** `llama-quantize` from the same commit. Convert venv from `requirements-convert_hf_to_gguf.txt`.
- **Candidates** (`bench/build_candidate_gguf.sh`; `convert_hf_to_gguf.py --outtype auto`, then
  `llama-quantize --pure --token-embedding-type q8_0 --output-tensor-type q8_0 ... Q4_0`):

| model | source repo @ revision | official? | source precision | bytes | sha256 | matrices |
|---|---|---|---|---|---|---|
| Llama 3.2 3B Instruct | `unsloth/Llama-3.2-3B-Instruct` @ `006f5dcd13` | mirror (Meta gated) | BF16 | 2,012,612,832 | `5aa3ece50ab33d09a7181888a75f8755f924c662dc99626e7f45440adfeadcdb` | 196 Q4_0, token_embd Q8_0 (output tied) |
| Qwen3 1.7B | `Qwen/Qwen3-1.7B` @ `70d244cc86cc` | official | BF16 | 1,460,395,904 | `4a4ebf10354822c45dfa38b9248a42a59ebae53c0ad992147b881dd7ed09c56c` | 196 Q4_0, token_embd Q8_0, output.weight Q8_0 |
| Gemma 3 1B QAT | `unsloth/gemma-3-1b-it-qat` @ `82120d4d65` | mirror (Google gated) | BF16 | 720,425,280 | `3a229fece56839877093042f0699939d9c4a65691dda81999f80ff27dae2cc5f` | 182 Q4_0, token_embd Q8_0 (output tied) |
| Qwen2.5 0.5B Instruct | `Qwen/Qwen2.5-0.5B-Instruct` @ `7ae557604adf` | official | BF16 | 352,154,624 | `00d3bb3f9210f132ef246cc5db2a7d8c9f8b63785679a95aef3558875b50e341` | 168 Q4_0, token_embd Q8_0 (output tied) |

Files: `~/fieldmind-build/gguf/<name>-Q4_0-pure-embq8.gguf`.

## Verification
| step | result |
|---|---|
| ran the module | `bench/build_candidate_gguf.sh` ran for all 4, exit 0 each; `bench.board env/temp/start/log/stop` ran against the board (before it was unplugged) |
| self-tests | 103 passed / 0 failed (`.venv/bin/python -m pytest`), 5 new in `tests/test_board_env.py` |
| independent re-derivation | tensor-type counts of each candidate by llama.cpp's own `gguf-py` `GGUFReader` (a different parser): identical to `bench.gguf_types` for all 4, relative difference 0. Also: for the impure on-board file, llama-server's loader printed `f32 58, q4_0 193, q4_1 3, q6_K 1`, identical to `bench.gguf_types` on its header (the "first real file" check left open in `phase0b_lanes_model_choice.md`) |
| mutation check | `CTX_SIZE` 4096 -> 2048: caught by `test_lanes_always_use_ctx_4096_np_1`. `ADSP_LIBRARY_PATH` removed from the launch: caught by `test_lane_command_env_and_offload`. `drop_pythonpath()` removed: caught by `test_board_script_drops_pythonpath`. `env=clean_env()` removed from the adb call: caught by `test_adb_subprocess_gets_clean_env`. Build-script gate: fed the impure bartowski header, the `verdict OK` grep fails (exit 3 path) |

## Direction checks
None: no physical response was modelled in this stage.

## Constants introduced
| symbol | value | provenance | range | affects |
|---|---|---|---|---|
| `CTX_SIZE` | 4096 | human decision 2026-10-03 (equals `llm.llamaserver.ctx_size`, itself derived in the config) | fixed | NPU speed, KV buffer size; every lane launch |
| `N_PARALLEL` | 1 | human decision 2026-10-03; CLAUDE.md "one request at a time" | fixed | one slot per lane |
| log level | `-lv 4` | found on the board: the default level prints no loader lines | 4 or higher | whether the NPU-confirmation rule can be checked. Effect on speed NOT measured |
| `-fit` | off | conservative: no argument may be adjusted silently (HTP0 reports 0 MiB free) | on/off | layer placement |

## Numbers that changed
| quantity | old | new | note |
|---|---|---|---|
| Llama 3.2 3B file | 1,921,909,280 B (bartowski: 193 Q4_0, 3 Q4_1, token_embd Q6_K) | 2,012,612,832 B (196 Q4_0, token_embd Q8_0) | ratio 1.047. The earlier 839 / 11.7 tok/s belong to the old file |
| tests | 98 | 103 | |

## Decisions taken
1. **Toolchain image pulled.** The message said the snapdragon-toolchain container was already in `podman images`; it
   was not (only `ubuntu:22.04`). Pulled the image the pinned llama.cpp docs name. NDK is r29 in the image.
2. **Safetensors mirrors, not GGUF mirrors, for the two gated models.** The instruction for a gated repo was an
   F16/BF16 GGUF mirror. I used safetensors mirrors whose weight files have the same sha256 as the official gated files
   (the Hub publishes LFS hashes for gated repos): both Llama shards equal Meta's; Gemma `model.safetensors` and
   `tokenizer.model` equal `google/gemma-3-1b-it-qat-q4_0-unquantized`. That keeps the recipe's primary path
   (official weights through `convert_hf_to_gguf.py`, lossless BF16). Reversible: nothing downstream has run.
3. **Gemma: Google's QAT GGUF not used.** Checked on the byte-identical copy in `tetf/gemma-3-1b-it-qat-q4_0-GGUF`
   (sha256 `95e5b8d8...` equals Google's): `token_embd.weight` is F16, so it does not match the recipe.
4. **Gemma EOS restored to 1.** unsloth's tokenizer files set EOS to `<end_of_turn>` (106). Google's own GGUF and the
   `mlx-community/gemma-3-1b-it-qat-bf16` config say `<eos>` (1). Built with
   `--override-kv tokenizer.ggml.eos_token_id=int:1`; verified 1 in the output.
5. **Llama metadata left as converted.** Chat template, tokens, token types, merges, BOS/EOS are identical to the
   Meta-derived `bartowski/...-f16.gguf` header. unsloth adds `padding_token_id` 128004; left in (unused here).
6. **`-lv 4` and `-fit off` added to the launch command** (see Constants).
7. **Build tree outside the repo:** `~/fieldmind-build/` (new folder; nothing existing was changed).
8. **`logs/` added to `.gitignore`.**

## Disagreements recorded, not resolved
- Gemma tokenizer arrays: against Google's own GGUF, my conversion differs in 30 token spellings (ids 138-167, `▁`
  runs vs spaces), 6,414 scores and 6,407 token types. The sentencepiece `tokenizer.model` is byte-identical, so I
  attribute this to the converter version. **Not tested** (would need Google's file converted by the pinned converter,
  which needs the gated repo). Recorded as unexplained-but-probable, not as verified.
- Gemma chat template: Google's GGUF stores a flattened one-line template whose system prefix ends in one newline; the
  HF template (unsloth and mlx copies, identical to each other) uses two. Irrelevant to this project's requests
  (single user message, `LlamaServerBackend._body`); it would matter if a system message were ever sent.

## Blocked / needs a decision
- Board steps (push GGUFs, smoke test) wait for the human to reconnect the board and say continue.

## What I could not verify
- That every operation runs on the NPU. The dry run (impure on-board file, launch mechanics only, no request sent, no
  timings taken) showed `offloading output layer to GPU`, `offloaded 29/29 layers`, `HTP0 model buffer size = 1845.95
  MiB`, `CPU model buffer size = 308.23 MiB`. That is weight placement, not execution. The 308 MiB CPU buffer is
  probably the input embedding table; not checked.
- Whether `-lv 4` changes prefill or decode speed.
- Gemma: my Q4_0 tensors were not compared bit-for-bit with Google's QAT GGUF (needs the full 1 GB file).
- The unsloth small files (config, tokenizer_config) against the official gated ones, beyond the comparisons above.
- No timing, energy or accuracy number exists for any of the 4 candidates yet.
