# Session 2 setup — progress (for resuming)

Updated after every step. Full report: `reports/phase0b_board_setup.md`. Build tree (outside the repo, new):
`~/fieldmind-build/` (llama.cpp checkout, convert venv, source weights, GGUFs). Logs: `logs/` (gitignored).

Standing human decisions: quantization recipe (`reports/phase0b_board_setup.md`); llama-server is always launched
with `-c 4096 -np 1`, the same for every model and both lanes.

| step | state | commit | paths / hashes |
|---|---|---|---|
| 0. record quantization decision | DONE | `ecc4d72` | `reports/phase0b_board_setup.md` |
| 1. small fixes | DONE | `cce26a4`, `b060c6f` | PROMPTS.md, README_SETUP.md, requirements.txt, .gitignore; `bench/board.py`, `bench/probe_device.py`, `tests/test_board_env.py` (101 tests pass) |
| 2. llama.cpp builds | DONE | `ea1651e` | see below |
| 3. build 4 GGUFs | DONE | `f3ab0f8`, `f7b5699`, `b9fd4c0`, this commit | all 4 built and checked; table under "Step 3 results". Source weights verified by sha256 against the Hub (`logs/fetch_weights.log`, 0 retries) |
| 4. push package + GGUFs to `/data/local/tmp/llm/` | PARTIAL | | package pushed to `/data/local/tmp/llm/llama.cpp` (134 files, 288,458,199 B); board sha256 == laptop sha256 for all 134 (`logs/package_sha256_{laptop,board}.txt`). GGUFs not pushed yet |
| 5. smoke test (3B, NPU lane, `-c 4096 -np 1`) | tooling ready | `0c19242`, `929ba99` | `bench.board start npu <file>` / `log npu` / `stop`; prompt saved at `logs/smoke_diagnostician_prompt.txt` (ep_A01 tick 64, 8,988 chars). Launch mechanics dry-run on the impure on-board file worked (ready in 4 s; `logs/dryrun_lane_npu_impure_lv4.log`); no timings taken from it |
| 6. CLAUDE.md + /board-up | not started | | |

## Step 2 details
- llama.cpp: `https://github.com/ggml-org/llama.cpp`, tag `b11371`, commit `99b95488cac0f00ce3f05af113a8c1e287753f87`,
  at `~/fieldmind-build/llama.cpp` (untracked additions only: `CMakeUserPresets.json`, copied from
  `docs/backend/snapdragon/`, and the build/package folders).
- Toolchain container: `ghcr.io/snapdragon-toolchain/arm64-android:v0.7`, digest
  `sha256:c012b8174f4154088ee027077e9cb80e68cc9a494d46f63454a050fa4789897b` (NDK r29, Hexagon SDK 6.6.0.0).
  It was NOT already on this machine (podman had only `ubuntu:22.04`); pulled with podman.
- Android build: preset `arm64-android-snapdragon-release`, plus `-DLLAMA_BUILD_SERVER=ON -DLLAMA_OPENSSL=OFF`
  (the preset already sets OpenSSL off; `LLAMA_CURL` is deprecated at this commit). Package:
  `~/fieldmind-build/llama.cpp/pkg-android/llama.cpp` (276 MB). Log: `logs/llamacpp_android_build.log`.
  - `bin/llama-server` sha256 `853e7ccf3f7e008dca41f28d52440aaf95e292b241dbca4b8ebde52bd0e55cad`
  - `lib/libggml-hexagon.so` sha256 `ac17be24f4dc16469d265108103fdc84f2c1b8a25562d964b33d21f96342cf76`
  - `lib/libggml-htp-v75.so` sha256 `1fd898cc0709498defeed3439a52500ff8340efd7725b3f88902e0adb2d0aa37`
- Host CPU build: `~/fieldmind-build/llama.cpp/build-host/bin/llama-quantize`
  (sha256 `376baf5ced3d3412ff820fcaa3ae9e043390421d39d4ec8d13c55975cbc32da2`), `-DGGML_NATIVE=ON`, gcc 15.2.1.
  Log: `logs/llamacpp_host_build.log`.
- Convert venv: `~/fieldmind-build/venv-convert` (python 3.13, torch 2.11.0+cpu, transformers 4.57.6), from
  `requirements/requirements-convert_hf_to_gguf.txt`. Always run with `env -u PYTHONPATH`. Log: `logs/convert_venv.log`.

## Step 3 sources (decided; see the full report for the evidence)
| model | source repo @ revision | why |
|---|---|---|
| Llama 3.2 3B Instruct | `unsloth/Llama-3.2-3B-Instruct` @ `006f5dcd13` | Meta repo gated, not approved. Both safetensors shards have the same sha256 as Meta's. Tokenizer/template check pending |
| Qwen3 1.7B | `Qwen/Qwen3-1.7B` @ `70d244cc86cc` | official, open |
| Gemma 3 1B QAT | `unsloth/gemma-3-1b-it-qat` @ `82120d4d65` | Google repos gated, not approved. `model.safetensors` and `tokenizer.model` have the same sha256 as `google/gemma-3-1b-it-qat-q4_0-unquantized`. Google's own QAT GGUF does not match the recipe (token_embd is F16) |
| Qwen2.5 0.5B Instruct | `Qwen/Qwen2.5-0.5B-Instruct` @ `7ae557604adf` | official, open |

## Notes for a resuming session
- Network: the laptop is on a phone hotspot; at 16:30 it had 50% packet loss and < 1 MB/s. `snapshot_download` returns
  quietly when the Hub is unreachable (a false "done"); use `fetch_weights.py`, which verifies sha256.
- Resume the fetch with: `cd ~/fieldmind-build && env -u PYTHONPATH venv-convert/bin/python fetch_weights.py`.
- Lane launch needs `-lv 4`: at the default log level this build prints no offload / buffer / tensor-type lines.

## Step 3 results (one row per finished model)
Built by `bench/build_candidate_gguf.sh` at llama.cpp `99b9548`; files in `~/fieldmind-build/gguf/`. Type counts are
from `bench.gguf_types` and agree with llama.cpp's own `gguf-py` reader (`~/fieldmind-build/types_gguf_py.py`).

| model | source precision | candidate file | bytes | sha256 | matrices | verdict |
|---|---|---|---|---|---|---|
| Qwen2.5 0.5B Instruct | BF16 | `Qwen2.5-0.5B-Instruct-Q4_0-pure-embq8.gguf` | 352,154,624 | `00d3bb3f9210f132ef246cc5db2a7d8c9f8b63785679a95aef3558875b50e341` | 168 Q4_0 + token_embd Q8_0 (output tied) | OK |
| Gemma 3 1B QAT | BF16 | `gemma-3-1b-it-qat-Q4_0-pure-embq8.gguf` | 720,425,280 | `3a229fece56839877093042f0699939d9c4a65691dda81999f80ff27dae2cc5f` | 182 Q4_0 + token_embd Q8_0 (output tied) | OK. Built with `--override-kv tokenizer.ggml.eos_token_id=int:1` (unsloth's files give 106; Google's own GGUF has 1) |
| Llama 3.2 3B Instruct | BF16 | `Llama-3.2-3B-Instruct-Q4_0-pure-embq8.gguf` | 2,012,612,832 | `5aa3ece50ab33d09a7181888a75f8755f924c662dc99626e7f45440adfeadcdb` | 196 Q4_0 + token_embd Q8_0 (output tied) | OK. Chat template, tokens, token types, merges, BOS/EOS identical to the Meta-derived `bartowski/...-f16.gguf` header; only extra key is `padding_token_id` 128004 (unsloth), unused in single-sequence generation |
| Qwen3 1.7B | BF16 | `Qwen3-1.7B-Q4_0-pure-embq8.gguf` | 1,460,395,904 | `4a4ebf10354822c45dfa38b9248a42a59ebae53c0ad992147b881dd7ed09c56c` | 196 Q4_0 + token_embd Q8_0 + output.weight Q8_0 (not tied) | OK |

Total to push: 4,545,588,640 B (4.23 GiB). Board free at 16:20 was 9,307,704 KiB before the 288 MB package push.

**State at stop (board unplugged by the human):** step 3 DONE for all 4. Next, only after the human says continue:
step 4 push the 4 GGUFs to `/data/local/tmp/llm/` and compare `sha256sum` on the board with the values above; step 5
smoke test with `Llama-3.2-3B-Instruct-Q4_0-pure-embq8.gguf`; step 6 commit the drafted `CLAUDE.md` and
`.claude/skills/board-up/SKILL.md` (uncommitted in the working tree).

## Stop after step A (Gemma tokenizer check), 2026-10-03
- Human decisions (mirrors accepted, Gemma EOS 1, `-fit off`, `-lv 4` 5% rule, option C, unattended campaign) are in
  `reports/phase0b_board_setup.md`, commits `5018410` and this one.
- Step A result: our Gemma GGUF == Hugging Face tokenizer on 2,084 / 2,084 distinct dev prompts, but == Google's GGUF
  vocabulary on 0 / 2,084 (one extra token each; fixed by adding `add_space_prefix = false` to Google's metadata).
  Rule says stop on any mismatch: **STOPPED before the push, waiting for the human.**
- NOT done: push of the 4 GGUFs, smoke test (B, C, D), docs commit (CLAUDE.md and `/board-up` drafts still
  uncommitted), manifest/sha256 check in `bench.board.start_lane`, and the whole campaign runner (items 1-9).
- Evidence: `~/fieldmind-build/tokcheck/` (prompts, three ID sets, the two vocab-only GGUFs).
  Dev prompts: scratchpad only; regenerate with
  `run_demo.py --all --episodes-dir data/episodes_dev --tag dev --backend mock --log-prompts --out <dir>`.

## Resumed 2026-10-03 (board reconnected)
- Human decision: Hugging Face tokenizer is the Gemma reference; step A passes 2,084 / 2,084 (commit `11ac80b`).
- `bench.board.CANDIDATES` manifest: lanes refuse any file not in it or whose board sha256 differs (`11ac80b`).
- **Step 4 DONE.** 4 GGUFs pushed to `/data/local/tmp/llm/`; `sha256sum` on the board equals the laptop value for all 4
  (`logs/push_gguf.log`). Board free space after the push: 4,581,412 KiB.
- Next: step 5 smoke test (B offload/logits placement, C `-lv 4` cost, D Gemma stop), then docs commit, then the
  campaign runner (items 1-9 of the human's message; nothing built yet).
