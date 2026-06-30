"""
run_registry.py
================
Zentrale Verwaltung aller LLM-Testläufe ("Runs").

Jeder Run = eine Kombination aus Prompt, Modell, Thinking Budget,
Datensatz und Zielvariable, die als Batch-Job an ein LLM geschickt wurde.

Statt Metadaten aus Dateinamen zu parsen (z.B. "classification_results_3_gemini.csv"),
werden sie hier explizit und strukturiert in einer CSV-Datei gespeichert.
Jede run_id ist eindeutig und referenziert alle relevanten Infos.

Spalten der Registry:
    run_id            - eindeutige ID, z.B. "run_0017"
    job_id            - von der API zurückgegebene Batch-Job-ID
    status            - "submitted" | "downloaded" | "failed" | "skipped"
    prompt_id         - Schlüssel des Prompts, z.B. "PROMPT_4" oder "GPT_2"
    prompt_number     - kurze Kennung für Dateinamen (z.B. "4", "gpt2")
    prompt_version    - frei wählbar, z.B. "v1", "v2_longer_context"
    model             - Modell-Alias, z.B. "gemini-2.5-flash"
    thinking_budget   - int oder None
    dataset_id        - z.B. "main_transcripts"
    dataset_version    - z.B. "v3"
    target_variable   - z.B. "ideology_score" oder "populism_score"
    validation_basis  - "manual" | "all_statements" (ersetzt die alte
                         Magic-Number-Logik "1_, 3_, 4_, 7_" vs. "2_, 5_, ...")
    created_at        - Zeitstempel beim Submit
    updated_at        - Zeitstempel der letzten Änderung
    results_path      - Pfad zur heruntergeladenen Ergebnisdatei (csv/xlsx)
    notes             - Freitext, optional
"""

from __future__ import annotations

import pandas as pd
from pathlib import Path
from datetime import datetime

REGISTRY_COLUMNS = [
    "run_id", "job_id", "status",
    "prompt_id", "prompt_number", "prompt_version",
    "model", "thinking_budget",
    "dataset_id", "dataset_version",
    "target_variable", "validation_basis",
    "created_at", "updated_at",
    "results_path", "notes",
]


class RunRegistry:
    def __init__(self, registry_path: str | Path):
        self.path = Path(registry_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            self.df = pd.read_csv(self.path, dtype=str)
        else:
            self.df = pd.DataFrame(columns=REGISTRY_COLUMNS)

    # ---------------------------------------------------------
    def _save(self):
        self.df.to_csv(self.path, index=False)

    # ---------------------------------------------------------
    def _next_run_id(self) -> str:
        if self.df.empty:
            return "run_0001"
        existing = self.df["run_id"].str.extract(r"run_(\d+)")[0].dropna().astype(int)
        next_num = (existing.max() + 1) if not existing.empty else 1
        return f"run_{next_num:04d}"

    # ---------------------------------------------------------
    def add_run(
        self,
        prompt_id: str,
        prompt_number: str,
        model: str,
        dataset_id: str,
        dataset_version: str,
        target_variable: str,
        validation_basis: str = "manual",
        prompt_version: str = "v1",
        thinking_budget: int | None = None,
        job_id: str | None = None,
        status: str = "submitted",
        notes: str = "",
    ) -> str:
        """Legt einen neuen Run an und gibt die run_id zurück."""
        run_id = self._next_run_id()
        now = datetime.now().isoformat(timespec="seconds")

        row = {
            "run_id": run_id,
            "job_id": job_id,
            "status": status,
            "prompt_id": prompt_id,
            "prompt_number": prompt_number,
            "prompt_version": prompt_version,
            "model": model,
            "thinking_budget": thinking_budget,
            "dataset_id": dataset_id,
            "dataset_version": dataset_version,
            "target_variable": target_variable,
            "validation_basis": validation_basis,
            "created_at": now,
            "updated_at": now,
            "results_path": "",
            "notes": notes,
        }
        self.df = pd.concat([self.df, pd.DataFrame([row])], ignore_index=True)
        self._save()
        return run_id

    # ---------------------------------------------------------
    def update_run(self, run_id: str, **kwargs):
        """Aktualisiert beliebige Felder eines bestehenden Runs."""
        mask = self.df["run_id"] == run_id
        if not mask.any():
            raise ValueError(f"run_id '{run_id}' nicht in Registry gefunden.")
        for key, value in kwargs.items():
            self.df.loc[mask, key] = value
        self.df.loc[mask, "updated_at"] = datetime.now().isoformat(timespec="seconds")
        self._save()

    # ---------------------------------------------------------
    def get_runs(self, **filters) -> pd.DataFrame:
        """
        Gibt gefilterte Runs zurück, z.B.:
            registry.get_runs(status="submitted")
            registry.get_runs(dataset_id="main_transcripts", target_variable="ideology_score")
        """
        result = self.df.copy()
        for key, value in filters.items():
            if key not in result.columns:
                raise ValueError(f"Unbekannte Filterspalte: {key}")
            result = result[result[key].astype(str) == str(value)]
        return result

    # ---------------------------------------------------------
    def get_run(self, run_id: str) -> pd.Series:
        rows = self.df[self.df["run_id"] == run_id]
        if rows.empty:
            raise ValueError(f"run_id '{run_id}' nicht in Registry gefunden.")
        return rows.iloc[0]
