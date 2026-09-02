# Stage 6 / Gemini prompt logging + ep_A01 tick 49 diagnosis — report

## Status

DONE (parts 1–2), part 3 (6-episode gemini vs mock) appended below.

- **Part 1** — `AgentEnvelope` now carries the rendered prompt, the raw model
  reply, the prompt token count, the transient-retry count, the error string,
  and the retrieved case ids. Prompt/reply text only under `--log-prompts`;
  everything else always. `GeminiBackend` gained a 429/5xx/network retry loop
  and a client-side rate limiter, and the config model was switched off the
  decommissioned `gemini-2.0-flash`.
- **Part 2** — ep_A01 tick 49: **RCA-01 was retrieved at rank 1**; the
  RCA-09/RCA-10 ranking is the **deterministic fallback**, not the model —
  Gemini never replied on the old run (dead model, HTTP 404 on every call).
  With a working model on the identical prompt, Gemini returns RCA-01 rank 1.

## Part 1 — what was added

### `AgentEnvelope` (schemas.py)

| field | always? | purpose |
|---|---|---|
| `prompt_tokens` | yes | scheduling-study prompt size; backend count if present, else `est_tokens` (`len/4`) |
| `error` | yes | failure reason — **was silently dropped**; `payload` was left `{}` |
| `payload` | yes | now `{"error": …}` on failure instead of `{}` |
| `retries` | yes | transient-failure retries spent on the call |
| `retrieved_cases` | yes | case ids in rank order **as prompted** — answers "was X retrieved" without the full prompt |
| `prompt` | `--log-prompts` only | the exact rendered prompt (~1–3 kB) |
| `raw_reply` | `--log-prompts` only | unparsed model text, incl. the repair-retry reply |

`--log-prompts` is a `run_demo` flag → `cfg.agent.log_prompts`, read by
`Diagnostician` and `Verifier`. `run_demo` also gained `--episodes a,b,c` for a
subset run. `run_episode` now returns `diag_calls`, `ver_calls`,
`llm_retries`, `mean_prompt_tokens`, `envelope_status_counts` per episode.

### `GeminiBackend`

- **`gemini-2.0-flash` is decommissioned** — `HTTP 404 "no longer available.
  Please update … to models/gemini-3.6-flash"` on every call, observed
  2026-09-02. That is why the previous `results/runs_gemini.json` has
  `status:"error"`, `payload:{}`, `tokens:{0,0}` on **all 106** diagnostician
  envelopes and all 35 verifier envelopes. Config switched to
  **`gemini-flash-lite-latest`** (fast ~0.8–1.5 s, non-"thinking" — unlike
  `gemini-3.6-flash`, which burns the `maxOutputTokens` budget on
  `thoughtsTokenCount` and truncates the JSON).
- **Retry loop**: `429` and `5xx` and network drops (timeout, SSL EOF) →
  exponential backoff (`2·2ⁿ` s, capped 60 s) + jitter, honouring
  `Retry-After`. A non-429 `4xx` (dead model, bad request) returns
  immediately. Count flows out on `LLMReply.retries` → `AgentEnvelope.retries`
  → `run_episode.llm_retries`.
- **Client-side rate limiter** (`min_interval_s`, config `llm.gemini`): the
  free tier is ~15 RPM and the pipeline calls back-to-back, so without spacing
  every call 429s and the retry loop turns a 5-minute run into an hour. Set to
  4.0 s for the rate-limited tier; 0 (off) otherwise.

### Verification

| step | result |
|---|---|
| new self-tests | `python bench/test_envelope_logging.py` → **16 / 16**. Logging off → `prompt`/`raw_reply` empty but `prompt_tokens` filled; logging on → both captured (incl. on a failed call); a failed call keeps `status` + `error` + `payload`; `retries` counted and accumulated; verifier gets the same treatment. |
| mutation check | (a) make `env.prompt` unconditional → "prompt is NOT stored with logging off" FAILS. (b) drop `env.error`/`env.payload` on a non-ok reply (old behaviour) → "error string is preserved" + "payload carries the error" FAIL. Both restored → 16/16. |
| regression | `test_checks` 20/20, `test_orchestrator` 22/22, sim self-tests exit 0, `validate_data` 30/30, `run_demo --all --backend mock` → `Q2_top1 0.334`, `Q3 1.0`, `Q4 0.38/0.926` — unchanged. |
| live gemini smoke | one real `gemini-flash-lite-latest` call on the tick-49 prompt → HTTP 200, 1.5 s, `promptTokenCount 1690`, valid JSON (see part 2). |

## Part 2 — ep_A01_fcv_seize, tick 49

### The retrieved case list, rank order, as the model saw it

From the logged diagnostician prompt (retrieval is backend-independent — same
`Retriever`, same per-tick signature):

| rank | case | retrieval score | title |
|---|---|---|---|
| **1** | **RCA-01** | **0.12** | Drum level low → water-wall starvation — **feed control valve actuator seizure** |
| 2 | RCA-07 | 0.10 | Bed temperature high → clinker — loss of ash recirculation |
| 3 | RCA-16 | 0.10 | Boiler feed pump failure — NPSH-loss cavitation |

`k_cases = 4`; only 3 scored above the `> 0.01` floor. **RCA-01 — the correct
cause — is retrieved at rank 1.** RCA-09 and RCA-10 are **not retrieved at this
tick at all.**

### RCA-01's position: retrieved rank 1. So this is **not** a retrieval failure.

### Which of the three options is it

**None as framed — because the model never ran.** Every Gemini call on the
existing `runs_gemini.json` returned `HTTP 404` (`gemini-2.0-flash`
decommissioned) → `status:"error"`. When `status != "ok"` the orchestrator
**skips `_merge`**, so `claims["hypotheses"]` is left as
`rank_hypotheses(wm)` — the **deterministic belief accumulator**. The
"RCA-09 / RCA-10 first at 0.44 / 0.44, then RCA-03 / RCA-04 at 0.39" the
question describes is that fallback, not a Gemini ranking.

**The model's actual reply.** Sent tick 49's exact rendered prompt to
`gemini-flash-lite-latest` (1.5 s, 1690 prompt tokens, 176 decode):

```json
{
  "headline": "Drum level is falling rapidly despite the feed pump running, pointing to a feedwater delivery failure.",
  "hypotheses": [
    {
      "rank": 1,
      "cause": "Feed water control valve actuator stem seizure from deposit build-up and lack of exercise",
      "confidence": 0.35,
      "supports": ["F1", "F2"],
      "case_ref": "RCA-01",
      "discriminator": "Feed control valve demand saturated at 100% with feed flow not responding."
    }
  ],
  "unexplained": [
    "Operator note indicating FCV not responding properly",
    "Ash slurry pump overload trips"
  ]
}
```

**Gemini gets it right** — single hypothesis, RCA-01, rank 1. No RCA-09/10.

### Why the *deterministic* fallback ranks the ∅-cluster cases first

`wm.hypotheses` **accumulates across ticks** and is never pruned to the
currently-retrieved set. RCA-09 / RCA-10 / RCA-13 were retrieved on **earlier**
ticks (a sparser signature) and built up log-odds; by tick 49 they are stale
but still in `wm.hypotheses` above the 0.08 retire floor, so `rank_hypotheses`
still returns them:

| case | tick-49 fallback confidence | why |
|---|---|---|
| RCA-09 | 0.438 | all-FLAT ∅-cluster signature — on a mostly-flat plant every flat tag scores rule-1 "support" and nothing is ever absent, so it only ever gains |
| RCA-10 | 0.438 | **byte-identical** all-FLAT signature to RCA-09 → identical log-odds updates → the tie the question flagged. Not "descending values down a list" — two structurally identical cases. |
| RCA-13 | 0.214 | `bed_temp_avg UP SLOW` + rest FLAT — one expected-but-absent tag vs RCA-09/10 |
| RCA-01 | **0.15** | expects **movement** (`drum_level DOWN`, `water_balance DEFICIT`, …); rule 2 (`STEP_ABSENT −0.20`) fires for every expected tag not yet in `present_tags`, and it has had ~1 tick to accumulate. Compounded by **known bug 6** — `update_hypotheses` matches on **tag name only**, discarding direction/band, so it mis-credits and mis-penalises. |

So: **retrieval succeeded (RCA-01 rank 1); the deterministic fallback is the
failure**, and it is the belief accumulator — stale non-retrieved all-FLAT
hypotheses outranking a freshly-retrieved correct one — not the model and not
list-order echoing. The tie is two identical case signatures, and it is visible
only because the LLM path was dead and the fallback was showing through.

### Follow-on for the advisor

1. When the LLM path fails, `rank_hypotheses` should arguably be **restricted to
   (or heavily favour) the currently-retrieved cases**, not the full historical
   `wm.hypotheses`. A case that stopped being retrieved 30 ticks ago should not
   lead the fallback.
2. Known bug 6 (`update_hypotheses` tag-name-only matching) is on the critical
   path for the fallback ranking — it is why an all-FLAT case gains on a quiet
   plant. Fixing it is its own task.
3. `_merge` already keeps the deterministic **confidence** (Stage-6 bug-2 fix) —
   which means even with a correct Gemini reply, RCA-01's *displayed* confidence
   at tick 49 would be the accumulator's 0.15, not Gemini's 0.35. That is the
   intended "model reasons, deterministic accumulates" split, but it interacts
   badly with the stale-hypothesis problem above.

## Part 3 — 6-episode subset, gemini vs mock

*(filled in when the run completes)*
