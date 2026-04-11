# Artifact Family Inventory

Date: 2026-04-11
Phase: Phase 0

This document lists all artifact families produced by the ace-lite engine, their default paths, key filenames, schema versions, writers, and consumers.

---

## 1. Benchmark Run Outputs

**Root**: `artifacts/benchmark/`

**Sub-paths**:
| Path Pattern | Description |
|---|---|
| `artifacts/benchmark/latest/` | Most recent benchmark run |
| `artifacts/benchmark/matrix/latest/` | Multi-repo matrix run |
| `artifacts/benchmark/validation_rich/latest/` | Validation-rich summary outputs |
| `artifacts/benchmark/validation_rich/trend/latest/` | Validation trend reports |
| `artifacts/benchmark/baseline.json` | Baseline results for regression comparison |

**Key Files**:
| Filename | Schema Version Field |
|---|---|
| `results.json` | `schema_version` (top-level) |
| `summary.json` | `schema_version` (top-level) |
| `report.md` | (text/markdown) |

**Writers**:
- `src/ace_lite/cli_app/commands/benchmark.py` — `ace-lite benchmark run` CLI
- `scripts/run_benchmark_matrix.py` — multi-repo matrix runner

**Consumers**:
- `src/ace_lite/benchmark/report.py` — `build_results_summary()`
- `src/ace_lite/benchmark/diff.py` — `BenchmarkDiff`
- `src/ace_lite/benchmark/problem_surface_reader.py` — problem_surface reader (Phase 0 artifact)

---

## 2. Benchmark Diff/Report Outputs

**Root**: `artifacts/benchmark/`

**Sub-paths**:
| Path Pattern | Description |
|---|---|
| `artifacts/benchmark/diff/` | Diff output between two benchmark runs |
| `artifacts/benchmark/report.md` | Human-readable benchmark report |

**Key Files**:
| Filename | Schema Version Field |
|---|---|
| `diff_summary.json` | (no formal schema_version; plain JSON) |
| `report.md` | (markdown) |

**Writers**:
- `src/ace_lite/benchmark/report.py` — `build_results_summary()`
- `src/ace_lite/benchmark/diff.py` — `BenchmarkDiff`

**Consumers**:
- `src/ace_lite/benchmark/report.py` — `build_results_summary()` (reads own output)
- `scripts/build_freeze_trend_report.py` — reads `results.json` and `summary.json`

---

## 3. Validation-Rich and Freeze-Trend Reports

**Root**: `artifacts/benchmark/validation_rich/`

**Sub-paths**:
| Path Pattern | Description |
|---|---|
| `artifacts/benchmark/validation_rich/latest/` | Most recent validation-rich run |
| `artifacts/benchmark/validation_rich/archive/YYYY-MM-DD/` | Dated archive of validation-rich evidence |
| `artifacts/benchmark/validation_rich/trend/latest/` | Trend report |

**Key Files**:
| Filename | Schema Version Field |
|---|---|
| `validation_rich_summary.json` | `schema_version` |
| `freeze_trend_report.json` | `schema_version` |
| `archive_manifest.json` | (in archive dirs) |

**Writers**:
- `scripts/run_validation_rich_stability.py`
- `scripts/build_freeze_trend_report.py`
- `scripts/archive_validation_rich_evidence.py` — writes `archive_manifest.json`

**Consumers**:
- `scripts/build_freeze_trend_report.py` — reads `freeze_regression.json` from history
- Phase 1 evidence surfaces (ALH1-0101 series)

---

## 4. Release-Freeze Regression/Stability Outputs

**Root**: `artifacts/release-freeze/`

**Sub-paths**:
| Path Pattern | Description |
|---|---|
| `artifacts/release-freeze/latest/` | Most recent freeze regression run |
| `artifacts/release-freeze/stability/latest/` | Stability test outputs |

**Key Files**:
| Filename | Schema Version Field |
|---|---|
| `freeze_regression.json` | `schema_version` (top-level) |
| `stability_summary.json` | `schema_version` (top-level) |

**Writers**:
- `scripts/run_release_freeze_regression.py`
- `scripts/run_freeze_stability.py`

**Consumers**:
- `scripts/build_freeze_trend_report.py` — reads `freeze_regression.json`
- Phase 4 governance (ALH1-0403 series)
- Phase 5 closeout (ALH1-0502 series)

---

## 5. Gate-Registry Artifacts

**Root**: `artifacts/gate-registry/`

**Sub-paths**:
| Path Pattern | Description |
|---|---|
| `artifacts/gate-registry/latest/` | Most recent gate registry snapshot |
| `artifacts/gate-registry/archive/YYYY-MM-DD/` | Dated archive |

**Key Files**:
| Filename | Schema Version Field |
|---|---|
| `gate_registry.json` | `schema_version` |

**Writers**:
- `scripts/gate_registry_generator.py` (Phase 4 — ALH1-0401)
- Manual updates to `docs/maintainers/GATE_REGISTRY.md`

**Consumers**:
- Phase 4 release-review (ALH1-0403)
- Phase 5 closeout (ALH1-0501)
- `docs/maintainers/GATE_REGISTRY.md`

---

## 6. Run-Manifest Artifacts

**Root**: `artifacts/run-manifest/`

**Sub-paths**:
| Path Pattern | Description |
|---|---|
| `artifacts/run-manifest/latest/` | Latest run manifest |
| `artifacts/run-manifest/phaseN/` | Phase-specific run manifest |

**Key Files**:
| Filename | Schema Version Field |
|---|---|
| `run_manifest.jsonl` | `schema_version` (per-line) |

**Writers**:
- `scripts/write_run_manifest.py` — Phase 0 (ALH1-0004.T2)

**Consumers**:
- `scripts/generate_closeout_ledger_summary.py` — Phase 5 closeout
- Phase 5 closeout dashboard (ALH1-0501.T2)

---

## 7. Checkpoint Manifests

**Root**: `artifacts/checkpoints/`

**Sub-paths**:
| Path Pattern | Description |
|---|---|
| `artifacts/checkpoints/phaseN/YYYY-MM-DD/` | Dated checkpoint for Phase N |
| `artifacts/checkpoints/phaseN/archive/YYYY-MM-DD/` | Archived checkpoint |

**Key Files**:
| Filename | Schema Version Field |
|---|---|
| `checkpoint_manifest.json` | `schema_version` |
| `problem_ledger.json` | `problem_ledger_v1` |
| `wave_scorecard.json` | `wave_scorecard_v1` |

**Writers**:
- `scripts/create_dated_checkpoint.py` — Phase 0 (ALH1-0005.T2)
- `scripts/build_problem_ledger.py` — writes `problem_ledger.json`
- `scripts/write_run_manifest.py` — writes `wave_scorecard.json`

**Consumers**:
- `scripts/archive_validation_rich_evidence.py` — archives checkpoints
- Phase 4 promotion governance (ALH1-0403)
- Phase 5 closeout (ALH1-0501)

---

## Schema Version Reference

| Artifact Family | Schema Version |
|---|---|
| problem_ledger | `problem_ledger_v1` |
| problem_surface | `problem_surface_v1` |
| run_manifest | `run_manifest_v1` |
| checkpoint_manifest | `checkpoint_manifest_v1` |
| gate_registry | `gate_registry_v1` |
| wave_scorecard | `wave_scorecard_v1` |
| smoke_summary | `smoke_summary_v1` |
| validation_rich_summary | (informal; no schema_version) |
| freeze_regression | (informal; no schema_version) |
