"""
=============================================================================
 L3  --  RETRIEVAL  (Plan §6)
=============================================================================
Signature-match the fact list against past cases. Search the engineer notes.
Pull the relevant asset facts. Runs at WATCH and above.

Retrieval depth is a TUNED PARAMETER, not a constant, because it directly sets
prompt length and therefore prefill cost -- which on the NPU is the dominant
term (Plan §6.3).

  k_cases   3-5
  k_notes   3-8 after filtering
  k_records topology query, capped at 5
  hard cap  2048 tokens at WATCH, 3072 at INVESTIGATE

If retrieval overflows the cap, drop the LOWEST-SCORING ITEMS WHOLE. Never
truncate mid-record: half a case record is worse than no case record, because
the model cannot tell it is reading half.
=============================================================================
"""

from __future__ import annotations

from ..schemas import Fact


# Rough token estimate. 4 chars/token is close enough for budget enforcement;
# the exact count comes back from the backend afterwards for the cost model.
def est_tokens(text: str) -> int:
    return max(1, len(text) // 4)


class Retriever:
    """Not an LLM. Signature matcher + lexical/vector note search."""

    def __init__(self, asset, cases, notes, experience, cfg: dict):
        self.asset = asset
        self.cases = cases
        self.notes = notes
        self.experience = experience
        self.cfg = cfg

    def retrieve(self, facts: list[Fact], signature: dict, now_s: float,
                 triage_level: str) -> dict:
        r = self.cfg["retrieval"]
        k_cases = r["k_cases"]
        k_notes = r["k_notes"]
        budget = r["context_cap_tokens"].get(triage_level, 2048)

        active_tags = sorted({t for f in facts for t in f.tags
                              if f.severity != "INFO"})

        # ---- 1. curated cases, by signature ----
        cases = self.cases.match(signature, k=k_cases)

        # ---- 2. the agent's own past episodes, weighted below curated ----
        past = self.experience.match(signature, k=r.get("k_experience", 2))
        for p in past:
            p["unverified"] = p.get("provenance") == "agent_unverified"

        # ---- 3. notes: filter by time and tag first, then rank ----
        query_terms = []
        for f in facts:
            if f.severity != "INFO":
                query_terms += f.detail.replace(",", " ").split()
        notes = self.notes.search(query_terms, now_s, active_tags, k=k_notes)

        # ---- 4. candidate causes from plant topology (bounds the model) ----
        candidates = self.asset.candidates_for(active_tags,
                                               depth=r.get("topology_depth", 3))
        candidates = candidates[:r.get("k_records", 5)]

        packet = {"cases": cases, "experience": past, "notes": notes,
                  "candidates": candidates, "dropped": []}
        return self._enforce_budget(packet, budget)

    @staticmethod
    def _enforce_budget(packet: dict, budget: int) -> dict:
        """Drop lowest-scoring items whole until the assembled context fits.

        Order of sacrifice: unverified experience, then notes, then cases.
        Candidates are never dropped -- without them the model has no bounded
        list to choose from and the hallucination guard is gone.
        """
        def size(p):
            n = 0
            for c in p["cases"]:
                n += est_tokens(str(c.get("title", "")) + str(c.get("root_cause", ""))
                                + str(c.get("discriminating_evidence", "")))
            for e in p["experience"]:
                n += est_tokens(str(e.get("root_cause", "")))
            for nt in p["notes"]:
                n += est_tokens(nt["text"])
            n += est_tokens(" ".join(p["candidates"]))
            return n

        for key in ("experience", "notes", "cases"):
            while size(packet) > budget and packet[key]:
                dropped = packet[key].pop()          # already score-sorted
                packet["dropped"].append(
                    f"{key}:{dropped.get('case_id') or dropped.get('id')}")
        return packet
