"""
=============================================================================
 LLM BACKEND  --  the one place that knows how a model is actually called
=============================================================================

THIS IS THE SWITCHABLE PART.

Everything else in the codebase (l4_diagnose, l5_verify) only ever calls:

        reply = backend.generate(prompt, role="diagnostician")

and gets back an `LLMReply`.  It has no idea whether that prompt went to a
Google datacentre or to the Hexagon NPU eight centimetres away.  That is the
whole point: you develop the agent logic against the cloud API where iteration
is fast, then flip one line in configs/base.yaml and the identical pipeline
runs offline on the QIDK.

    llm:
      backend: mock      <- no network, no key, deterministic. Default.
      backend: gemini    <- Google AI Studio API. For development.
      backend: litert    <- LiteRT-LM on the QIDK. For the real result.

Three implementations, one interface:

    +----------------+-------------------------------+-------------------+
    | MockBackend    | no network, instant, canned   | CI / unit tests   |
    | GeminiBackend  | Google AI Studio HTTP API     | development       |
    | LiteRTBackend  | litert_lm_main over adb/local | the QIDK result   |
    +----------------+-------------------------------+-------------------+

Adding a fourth (Qualcomm Genie, llama.cpp, Ollama) means writing one class
with one method.  Nothing downstream changes.
=============================================================================
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
from dataclasses import dataclass, field


# =======================================================================
#  The uniform reply object
# =======================================================================

@dataclass
class LLMReply:
    """What every backend must return.

    The token counts and `backend` string are not decoration -- they feed the
    per-stage cost model in the FieldMind scheduling study (Plan §11).  Cloud
    backends fill in what the API tells them; the device backend parses them
    out of litert_lm_main's own timing output.
    """
    text: str                       # raw model output, unparsed
    status: str = "ok"              # ok | timeout | error
    latency_ms: float = 0.0
    backend: str = "unknown"        # npu | gpu | cpu | cloud | mock
    model: str = "unknown"
    prefill_tokens: int = 0
    decode_tokens: int = 0
    ttft_ms: float = 0.0            # time to first token, headline metric on device
    error: str = ""
    retries: int = 0               # transient-failure retries spent on this call


class LLMBackend:
    """Interface. Subclass this to add a runtime."""

    name = "base"

    def generate(self, prompt: str, role: str = "generic",
                 max_tokens: int = 512, mock_hint: dict | None = None) -> LLMReply:
        """Run one completion.

        role       : which agent is calling ("diagnostician" / "verifier").
                     Used for per-stage telemetry, and lets a backend route
                     different stages to different accelerators later.
        max_tokens : decode budget.  On the NPU this interacts with the static
                     shape chosen at compile time -- see Plan §10.3.
        mock_hint  : IGNORED by every real backend.  It exists so MockBackend
                     can produce a sensible answer without a model.  Never put
                     anything load-bearing in here.
        """
        raise NotImplementedError

    def close(self) -> None:
        """Release the model.  On device this actually matters (Plan §10.1:
        all models must stay resident, so we do NOT close between ticks)."""
        pass


# =======================================================================
#  1. MOCK  --  runs anywhere, no key, no device, no network
# =======================================================================

class MockBackend(LLMBackend):
    """A stand-in that returns schema-valid JSON derived from the facts it was
    given.  Purpose: let the whole tick pipeline, the harness and the evaluator
    be developed and unit-tested with zero external dependencies.

    It is NOT a quality baseline.  It picks the top retrieved case and echoes
    it back, so any accuracy number produced under the mock backend measures
    the retrieval layer, not a language model.  The evaluator labels runs with
    the backend name for exactly this reason -- never report a mock number as
    an agent result.
    """

    name = "mock"

    def __init__(self, latency_ms: float = 5.0, **_):
        self.latency_ms = latency_ms

    def generate(self, prompt, role="generic", max_tokens=512, mock_hint=None):
        t0 = time.perf_counter()
        hint = mock_hint or {}

        if role == "diagnostician":
            payload = self._mock_diagnosis(hint)
        elif role == "verifier":
            payload = self._mock_verification(hint)
        else:
            payload = {"note": "mock backend, no role-specific behaviour"}

        text = json.dumps(payload)
        # Rough token accounting so the telemetry plumbing is exercised.
        return LLMReply(
            text=text,
            latency_ms=(time.perf_counter() - t0) * 1000 + self.latency_ms,
            backend="mock", model="mock-0",
            prefill_tokens=len(prompt) // 4,
            decode_tokens=len(text) // 4,
            ttft_ms=self.latency_ms * 0.5,
        )

    @staticmethod
    def _mock_diagnosis(hint: dict) -> dict:
        """Rank the retrieved cases by their retrieval score. No reasoning."""
        cases = hint.get("cases", [])
        facts = [f["id"] for f in hint.get("facts", [])]
        candidates = hint.get("candidates", [])
        hyps = []
        for i, c in enumerate(cases[:3]):
            hyps.append({
                "rank": i + 1,
                "cause": c.get("root_cause", "unknown"),
                "confidence": round(max(0.15, c.get("score", 0.5) - 0.1 * i), 2),
                "supports": facts[:2],
                "case_ref": c.get("case_id"),
                "discriminator": c.get("discriminating_evidence", ""),
            })
        if not hyps and candidates:
            hyps = [{"rank": 1, "cause": f"Fault at or upstream of {candidates[0]}",
                     "confidence": 0.3, "supports": facts[:1],
                     "case_ref": None, "discriminator": "no similar case retrieved"}]
        return {
            "headline": hint.get("headline", "Deviation detected."),
            "hypotheses": hyps,
            "unexplained": [],
        }

    @staticmethod
    def _mock_verification(hint: dict) -> dict:
        """Always agrees. A real verifier must not -- that is why the mock is
        useless as a quality baseline and fine as a plumbing test."""
        return {"checks": [], "strongest_contradiction": None,
                "revised_confidence": None, "agree": True}


# =======================================================================
#  2. GEMINI  --  Google AI Studio, for development before the board is ready
# =======================================================================

class GeminiBackend(LLMBackend):
    """Calls the Google Generative Language REST API over plain HTTPS.

    Uses urllib from the stdlib on purpose -- no google-generativeai SDK
    dependency, so `pip install -r requirements.txt` stays tiny and there is
    one less thing to strip out before pushing to the device.

    Key comes from an environment variable, never from the config file:
        export GOOGLE_API_KEY="..."

    NOTE FOR THE WRITEUP: numbers produced through this backend are cloud
    numbers.  They are useful for measuring AGENT QUALITY (Q1-Q7) while the
    device path is still being built, and useless for SYSTEM metrics (S1-S7).
    Never mix them in one table.
    """

    name = "gemini"

    def __init__(self, model: str = "gemini-flash-lite-latest",
                 api_key_env: str = "GOOGLE_API_KEY",
                 temperature: float = 0.1,
                 timeout_s: float = 30.0,
                 json_mode: bool = True,
                 max_retries: int = 5,
                 backoff_base_s: float = 2.0,
                 backoff_cap_s: float = 60.0, **_):
        self.model = model
        self.temperature = temperature
        self.timeout_s = timeout_s
        self.json_mode = json_mode
        self.max_retries = max_retries
        self.backoff_base_s = backoff_base_s
        self.backoff_cap_s = backoff_cap_s
        self.api_key = os.environ.get(api_key_env, "")
        if not self.api_key:
            raise RuntimeError(
                f"{api_key_env} is not set. Either export it, or set "
                f"llm.backend: mock in configs/base.yaml."
            )

    def generate(self, prompt, role="generic", max_tokens=512, mock_hint=None):
        import random
        import urllib.request
        import urllib.error

        url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
               f"{self.model}:generateContent")
        body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": self.temperature,
                "maxOutputTokens": max_tokens,
            },
        }
        # Structured output. This is the cloud equivalent of grammar-constrained
        # decoding. LiteRT-LM may not offer it (Plan §10.3, open question) --
        # which is precisely why l4_diagnose still has a repair-retry path that
        # works without it. Do not let the pipeline come to depend on this.
        if self.json_mode:
            body["generationConfig"]["responseMimeType"] = "application/json"

        req_data = json.dumps(body).encode()
        headers = {"Content-Type": "application/json",
                   "x-goog-api-key": self.api_key}

        # ---- retry loop: 429 (rate limit) and 5xx (transient server) and
        #      network drops (timeout, SSL EOF) get exponential backoff with
        #      jitter, honouring Retry-After when the server sends it. A 4xx
        #      that is NOT 429 (e.g. 404 dead model, 400 bad request) is
        #      permanent and returns immediately.
        t_all = time.perf_counter()
        retries = 0
        last_err = "unknown"
        for attempt in range(self.max_retries + 1):
            t0 = time.perf_counter()
            req = urllib.request.Request(url, data=req_data, headers=headers,
                                         method="POST")
            try:
                with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                    data = json.loads(resp.read().decode())
                break                                          # success
            except urllib.error.HTTPError as e:
                payload = e.read()[:300]
                last_err = f"HTTP {e.code}: {payload!r}"
                transient = e.code == 429 or 500 <= e.code < 600
                if not transient or attempt == self.max_retries:
                    return LLMReply(
                        text="", status="error", backend="cloud",
                        model=self.model, retries=retries,
                        latency_ms=(time.perf_counter() - t_all) * 1000,
                        error=last_err)
                ra = e.headers.get("Retry-After") if e.headers else None
                wait = (float(ra) if ra and str(ra).isdigit()
                        else min(self.backoff_cap_s,
                                 self.backoff_base_s * (2 ** attempt)))
                wait += random.uniform(0, 0.5 * wait)
            except Exception as e:                              # timeout, SSL, DNS
                last_err = str(e)
                if attempt == self.max_retries:
                    return LLMReply(
                        text="", status="timeout", backend="cloud",
                        model=self.model, retries=retries,
                        latency_ms=(time.perf_counter() - t_all) * 1000,
                        error=last_err)
                wait = min(self.backoff_cap_s,
                           self.backoff_base_s * (2 ** attempt))
                wait += random.uniform(0, 0.5 * wait)
            retries += 1
            time.sleep(wait)

        latency = (time.perf_counter() - t_all) * 1000
        try:
            text = data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError):
            # Safety filter or empty candidate. Treat as a schema failure so the
            # normal repair/fallback path handles it.
            return LLMReply(text="", status="error", backend="cloud",
                            model=self.model, latency_ms=latency, retries=retries,
                            error=f"no candidate: {json.dumps(data)[:200]}")

        usage = data.get("usageMetadata", {})
        return LLMReply(
            text=text, backend="cloud", model=self.model, latency_ms=latency,
            retries=retries,
            prefill_tokens=usage.get("promptTokenCount", 0),
            decode_tokens=usage.get("candidatesTokenCount", 0),
            ttft_ms=0.0,   # not exposed by the non-streaming endpoint
        )


# =======================================================================
#  3. LITERT  --  Gemma3-1B on the QIDK.  The result that actually counts.
# =======================================================================

class LiteRTBackend(LLMBackend):
    """Drives `litert_lm_main` on the Snapdragon 8 Gen 3 board.

    Two modes, same class:

      mode: adb    host pushes the prompt and shells out over adb.  Slower
                   (adb round-trip is in the measurement) but it is how you
                   will do the first runs from the MacBook.
      mode: local  the agent itself is running on the board; invoke the binary
                   directly.  This is the configuration the reported numbers
                   should come from -- no host in the loop.

    LD_LIBRARY_PATH must be set on EVERY invocation or the HTP backend silently
    falls back to CPU and you get a plausible-looking wrong number.  That is
    the single most expensive mistake available here, so the path is built into
    the command rather than left to the shell environment.

    ---------------------------------------------------------------------
    STATUS: the command construction and output parsing below are written
    against litert_lm_main's current CLI.  Confirm the flag names and the
    timing-line format on the board before trusting any number out of this
    class -- run `bench/probe_device.py` first.  Anything that does not parse
    is returned as 0, never as a guess.
    ---------------------------------------------------------------------
    """

    name = "litert"

    def __init__(self,
                 mode: str = "adb",
                 device_dir: str = "/data/local/tmp/llm",
                 binary: str = "litert_lm_main",
                 model_file: str = "Gemma3-1B-IT_q4_ekv1280_sm8650.litertlm",
                 accelerator: str = "npu",           # cpu | gpu | npu
                 timeout_s: float = 60.0,
                 adb_serial: str = "", **_):
        self.mode = mode
        self.device_dir = device_dir.rstrip("/")
        self.binary = binary
        self.model_file = model_file
        self.accelerator = accelerator
        self.timeout_s = timeout_s
        self.adb_serial = adb_serial

    # ---- command construction -------------------------------------------

    def _device_command(self, prompt_path: str, max_tokens: int) -> str:
        """The shell line that runs on the board.

        `LD_LIBRARY_PATH` picks up libQnnHtpV75Skel.so / libQnnHtpV75Stub.so.
        Without it the HTP backend is unavailable and litert_lm_main will
        quietly use CPU instead of failing.
        """
        return (
            f"cd {self.device_dir} && "
            f"LD_LIBRARY_PATH={self.device_dir} "
            f"ADSP_LIBRARY_PATH={self.device_dir} "
            f"./{self.binary} "
            f"--model_path={self.device_dir}/{self.model_file} "
            f"--backend={self.accelerator} "
            f"--max_decode_steps={max_tokens} "
            f"--input_prompt_file={prompt_path} "
            f"--report_timing=true"
        )

    def _adb(self, *args: str) -> list[str]:
        cmd = ["adb"]
        if self.adb_serial:
            cmd += ["-s", self.adb_serial]
        return cmd + list(args)

    # ---- the call --------------------------------------------------------

    def generate(self, prompt, role="generic", max_tokens=512, mock_hint=None):
        t0 = time.perf_counter()
        prompt_path = f"{self.device_dir}/_prompt_{role}.txt"

        try:
            if self.mode == "adb":
                # Push the prompt as a file rather than passing it inline:
                # shell-quoting a 2-3 kB prompt containing JSON and braces is a
                # reliable source of silent corruption.
                import tempfile
                with tempfile.NamedTemporaryFile("w", suffix=".txt",
                                                 delete=False) as fh:
                    fh.write(prompt)
                    host_path = fh.name
                subprocess.run(self._adb("push", host_path, prompt_path),
                               capture_output=True, timeout=self.timeout_s)
                os.unlink(host_path)
                proc = subprocess.run(
                    self._adb("shell", self._device_command(prompt_path, max_tokens)),
                    capture_output=True, text=True, timeout=self.timeout_s)
            else:                                     # mode == "local"
                with open(prompt_path, "w") as fh:
                    fh.write(prompt)
                proc = subprocess.run(
                    ["sh", "-c", self._device_command(prompt_path, max_tokens)],
                    capture_output=True, text=True, timeout=self.timeout_s)

        except subprocess.TimeoutExpired:
            # A deadline miss, not a crash. The orchestrator will record it and
            # fall back to the deterministic assessment (Plan §9).
            return LLMReply(text="", status="timeout", backend=self.accelerator,
                            model=self.model_file,
                            latency_ms=(time.perf_counter() - t0) * 1000,
                            error="litert_lm_main exceeded timeout")
        except FileNotFoundError as e:
            return LLMReply(text="", status="error", backend=self.accelerator,
                            model=self.model_file, error=f"binary/adb missing: {e}")

        latency = (time.perf_counter() - t0) * 1000
        raw = proc.stdout or ""
        if proc.returncode != 0 and not raw.strip():
            return LLMReply(text="", status="error", backend=self.accelerator,
                            model=self.model_file, latency_ms=latency,
                            error=(proc.stderr or "")[:300])

        text, timing = self._parse_output(raw)
        return LLMReply(
            text=text, backend=self.accelerator, model=self.model_file,
            latency_ms=latency,
            prefill_tokens=timing.get("prefill_tokens", 0),
            decode_tokens=timing.get("decode_tokens", 0),
            ttft_ms=timing.get("ttft_ms", 0.0),
        )

    @staticmethod
    def _parse_output(raw: str) -> tuple[str, dict]:
        """Separate the generated text from litert_lm_main's own timing report.

        Anything that does not match is left at zero rather than estimated. A
        missing number is recoverable; a fabricated one poisons the whole
        cost model.
        """
        timing: dict = {}
        patterns = {
            "ttft_ms": r"(?:time to first token|TTFT)[^0-9]*([\d.]+)",
            "prefill_tokens": r"prefill[^0-9]*(\d+)\s*tokens",
            "decode_tokens": r"decode[^0-9]*(\d+)\s*tokens",
        }
        for key, pat in patterns.items():
            m = re.search(pat, raw, re.IGNORECASE)
            if m:
                timing[key] = float(m.group(1)) if "ms" in key else int(m.group(1))

        # The model's own output is whatever survives after dropping the
        # binary's log lines. Prefer a JSON object if one is present, since
        # that is what every agent prompt asks for.
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        text = m.group(0) if m else raw
        return text, timing


# =======================================================================
#  FACTORY  --  the single switch point
# =======================================================================

_REGISTRY = {
    "mock": MockBackend,
    "gemini": GeminiBackend,
    "litert": LiteRTBackend,
}


def make_backend(cfg: dict) -> LLMBackend:
    """Build a backend from the `llm:` block of the config.

        llm:
          backend: gemini
          gemini: {model: gemini-2.0-flash}
          litert: {accelerator: npu}

    Only the sub-block matching the selected backend is read, so you can keep
    settings for all three side by side and flip between them by editing one
    word.
    """
    name = cfg.get("backend", "mock")
    if name not in _REGISTRY:
        raise ValueError(f"unknown llm backend {name!r}; "
                         f"expected one of {sorted(_REGISTRY)}")
    return _REGISTRY[name](**cfg.get(name, {}))


def register_backend(name: str, cls: type) -> None:
    """Hook for adding Qualcomm Genie, llama.cpp, Ollama, etc. without editing
    this file. Implement LLMBackend.generate and register it at import time."""
    _REGISTRY[name] = cls
