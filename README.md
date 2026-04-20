# Model Benchy 🏁

A lightweight benchmark dashboard for comparing LLM models on structured agent tasks.

## What It Does

- Runs a standardized 9-task benchmark suite across local and cloud LLM models
- Displays results in a sortable leaderboard with scores, speed metrics, and per-task breakdowns
- Supports toggling between local-only and cloud model views
- Single-file Python HTTP server with embedded React + Tailwind frontend

## Benchmark Suite v3

9 tasks across 3 tracks, each scored 0–25 (225 max):

| Track | Tasks | Focus |
|-------|-------|-------|
| **A: Recovery** | a1 Canon, a2 Archaeology, a3 SourceTruth | Recovering context from conflicting/incomplete data |
| **B: Normalization** | b1 SchemaNorm, b2 RawOnly, b3 CanonDrift | Normalizing messy data across schemas |
| **C: Proof** | c1 Screenshot, c2 Attachability, c3 BuildVerify | Verifying claims with evidence |

## Quick Start

```bash
# 1. Run benchmarks against a model (OpenAI-compatible API)
python3 run_v3_suite.py --api http://localhost:18080/v1 --model mlx-community/Qwen3.6-35B-A3B-4bit

# 2. Start the dashboard
python3 server.py

# 3. Open http://localhost:3005
```

## Architecture

- `server.py` — Python HTTP server (no dependencies) with embedded React SPA
- `run_v3_suite.py` — Benchmark runner that outputs JSON results
- Benchmark data lives in `data/` as per-model directories with `results-raw.json` and `results-scored.json`

## Cloud Models

Model Benchy supports benchmarking cloud providers (OpenAI, Anthropic, Google, xAI, ZAI, MiniMax) alongside local models. Cloud results are tagged with `"cloud": true` and can be toggled in the UI.

## License

MIT
