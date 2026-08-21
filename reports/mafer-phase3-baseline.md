# MAFER Phase 3 Baseline

Date: 2026-08-10
Application: MIRSAD `1.0.0-rc1`
Purpose: immutable Phase 2 production state before Phase 3 calibration or shadow work

## Evidence Read

The complete Phase 2 intelligence report, Phase 2 benchmark artifact and all 20 case
records, Phase 1 final report, and mixed-source cap audit were inspected before production
code was changed.

## Frozen Production Relevance

- Lexical/semantic fusion: `25% / 75%`
- Bounded semantic opportunity: top `20`
- Secondary-quality budget: `1%`
- `ranking.py`: `3c5e78ca1e8cf979eb22abea8d5cd4ec1194965777bd18a16d3d0448c4416bb4`
- `semantic.py`: `ea56ba7198d43214c684769ef3807e14e0bfecb4e5a5f568440db50351b66e24`
- `clustering.py`: `f8d7c7a38d8bab8ddaae3527d1a04b4f4b1b3f0010ab80f28d666a49e9422e63`

These files and parameters are not Phase 3 tuning targets.

## Phase 2 Planning Components

| Component | File | Baseline SHA-256 |
| --- | --- | --- |
| Intent analyzer | `mafer/intent.py` | `f95fa6e34b42217b8bcce451fe86f352664ad49b3df8d3147ff389b83c1df79a` |
| Query lattice | `mafer/lattice.py` | `95c2e3759355f037bcdc63b2d688c5836260060c3d0ff5fa11c35cf10ceb17e8` |
| Resource router | `mafer/routing.py` | `11bdefc0686dac0a22464702b55b1c6d53d5d70691c59e69fea2bcb88204440b` |
| Engine router/circuit state | `discovery/searxng.py` | `5581eb40d4b9d4c3c2a66411d03470ca3b97d08ae1dc49b2763e8cffc32683d4` |
| Discovery RRF | `mafer/fusion.py` | `fc6a87c145d3889126f22b5aece1363a31bc9bab74f8e7c33f87af60b0666213` |
| Uncertainty and stop logic | `mafer/assessment.py` | `8c480ef198af809e88b2092047d3eedb5157ed6b66fa99c33df6c869aa1a8906` |
| Search budgets | `mafer/budget.py` | `0f82eb815f0adb0aa795d2542387a11b36395173a4f148d2dae945928469c85d` |
| Alias graph | `mafer/aliases.py` | `78c7ce7b415676fa953817d342ed5ef747f0799b01e899d721731a08ffce040b` |

The pre-change search orchestrator hash is
`6283e356babc90bd6ebf7118dbcfa798ac9e8700cde1e509e48f10e320f8fa89`.

## Phase 2 Evidence Baseline

BALANCED planning benchmark: P@5 `0.8600`, MRR `1.0000`, candidate recall
`0.9607`, useful URLs/query `6.60`, requests/query `12.75`, and two rounds/query.
Arabic candidate recall was `0.8429`; English was `1.0000`. Arabic person,
organization, and exact-phrase cases demonstrated incomplete candidate recall while the
recorded uncertainty remained LOW and stop reason SATISFIED. Weighted RRF was the largest
positive ablation; raw lattice expansion regressed top-k behavior before RRF; gated
expansion added no measured benefit.

## Validation Baseline

The immediately preceding verified state passed backend `184/184`, frontend `18/18`,
focused Phase 2 `26/26`, Playwright `11` with `2` opt-in live cases skipped, lint,
TypeScript, production build, doctor, source verification, database/FTS integrity, and
localhost startup smoke. Phase 3 will rerun these gates after all changes.

## Phase 3 Safety Rule

The verified Phase 2 planner remains production. Alternative uncertainty, stopping,
routing, semantic models, fusion, and diversity behavior must run in shadow evaluation
until an independent holdout passes the promotion gate. Stored content is not part of
algorithm rollback.
