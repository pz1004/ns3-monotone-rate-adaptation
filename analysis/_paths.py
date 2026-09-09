"""Repo-relative paths, so every script runs from anywhere.

Before the release split these scripts used two incompatible conventions: the campaign
analyses resolved "results/..." against the current working directory, while the table
and figure generators resolved "../results" against the paper directory. Both are now
anchored to the repo root instead.
"""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
RUNNER = ROOT / "runner"

# Generated output -- .tex macro files and figures. Gitignored: it is derived from
# results/ and must never be edited by hand or committed.
OUT = ROOT / "out"
OUT.mkdir(exist_ok=True)
