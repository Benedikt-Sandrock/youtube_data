"""Submit one production politics-screening batch to Vertex AI.

Thin entry point around the shared core in ``screening_batch_submission.py``
(factored out in Phase 4d, Schritt 6 — see ``.claude/plans/phase_4.md``).
Only the config below differs from ``run_longitudinal_screening_batch.py``:
this pipeline's candidate files use the ``time_period`` column instead of
``interval_label``.

Set ``MODE`` to:

- ``"title"``: submit the title candidates from create_screening_round.py
  to Prompt 32.
- ``"description"``: submit the title-uncertain cases produced by
  update_screening_state.py to Prompt 33.
"""

from __future__ import annotations

from youtube_code.llm_analysis.screening_batch_submission import (
    submit_screening_batch,
)


# ============================================================
# USER CONFIG
# ============================================================

ROUND_NUMBER = 1

# "title" or "description"
MODE = "description"

# Keep True until the generated JSONL, manifest, counts, and sample inputs
# have been inspected. Then change only this setting to False.
DRY_RUN = False

# False prevents duplicate production runs for the same round and stage.
# Set True only for a deliberate retry after inspecting the existing run.
ALLOW_EXISTING_RUN = False


def main() -> None:
    submit_screening_batch(
        round_number=ROUND_NUMBER,
        period_column="time_period",
        period_noun="period",
        mode=MODE,
        dry_run=DRY_RUN,
        allow_existing_run=ALLOW_EXISTING_RUN,
    )


if __name__ == "__main__":
    main()
