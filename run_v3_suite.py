#!/usr/bin/env python3
"""Run benchmark-suite-v3 tasks against local models via OpenAI-compatible API."""
import json
import time
import os
import re
import sys
from pathlib import Path
from urllib import request, error

API_ROOT = os.environ.get('API_ROOT', 'http://100.104.229.62:18080/v1')
API_URL = f'{API_ROOT}/chat/completions'
OUT_DIR = Path(os.environ.get('OUT_DIR', '/Users/enterprise/clawd-benchmarks/data'))
SUITE_DIR = Path(os.environ.get('SUITE_DIR', '/Users/enterprise/clawd-benchmarks/benchmark-suite-v3'))

MODELS = [
    'Jackrong/MLX-Qwen3.5-9B-GLM5.1-Distill-v1-4bit',
    'mlx-community/gemma-4-26b-a4b-it-4bit',
    'mlx-community/gemma-4-31b-it-4bit',
    'mlx-community/Qwen3.6-35B-A3B-4bit',
    'mlx-community/Qwen3.6-35B-A3B-4.4bit-msq',
    'mlx-community/Qwen3.6-35B-A3B-4bit-DWQ',
    'Jiunsong/supergemma4-e4b-abliterated-mlx',
    'prism-ml/Ternary-Bonsai-1.7B-mlx-2bit',
    'mlx-community/MiniMax-M2.7-4bit',
]

# Build concrete prompts from v3 task specs
TASKS = [
    {
        "id": "a1_missing_canon_conflicting_claims",
        "short": "Canon",
        "prompt": """You are given the following conflicting evidence about a benchmark suite called 'benchmark-suite-v2':

Evidence A: "benchmark-suite-v2 contains 5 tracks with 3 tasks each, totaling 15 tasks. The tracks are: canon_recovery, schema_drift, proof_capture, tool_failure, and delivery."

Evidence B: "benchmark-suite-v2 has 4 tasks: JSON extraction, tool routing, reasoning, and summary scoring. Each task is worth 25 points."

Evidence C: A transcript excerpt says "we ran the v2 suite today, 9 tasks across 3 tracks" and another says "v2 was the one with 5 tasks total."

Evidence D: A memory note says "benchmark-suite-v2 was replaced by v3 which has 9 tasks in 3 tracks."

Task: Determine what benchmark-suite-v2 actually is. List your verified findings, recovered findings, open questions, and evidence paths. Be honest about what you cannot verify.""",
    },
    {
        "id": "a2_first_use_archaeology",
        "short": "Archaeology",
        "prompt": """A benchmark skill was created on 2026-04-10 according to git history. Memory notes mention it was "first tested" on 2026-04-12. A transcript from 2026-04-14 says "we ran the benchmark skill for the Gemma model yesterday" (meaning 2026-04-13). Another transcript from 2026-04-11 mentions "setting up the benchmark pipeline" but no actual execution logs.

Questions:
1. When was the skill created?
2. When was it first actually used (not just created or discussed)?
3. What task was it used for in that first use?
4. What evidence supports each answer?

Be precise about creation vs first use. Cite the evidence for each claim.""",
    },
    {
        "id": "a3_source_of_truth_hunt",
        "short": "SourceTruth",
        "prompt": """You have these directories on a machine:

1. /Users/enterprise/Benchboard/ — a running HTTP server on port 3005 serving benchmark results
2. /Users/enterprise/clawd-benchmarks/ — contains data/ folders with results-raw.json and results-scored.json
3. /home/henrymascot/clawd/output/benchboard_server_clean.py — the "clean" server source that gets SCP'd to the Benchboard dir
4. /tmp/benchboard-build/ — an old build output directory
5. /home/henrymascot/clawd/output/ — local working copies and patches

Questions:
1. Where should edits to the server code happen?
2. What is the canonical source of truth?
3. What is just a runtime/build output?
4. Explain the correct edit-deploy cycle.

Be specific about paths and the relationship between source, build, and runtime.""",
    },
    {
        "id": "b1_mixed_schema_normalization",
        "short": "SchemaNorm",
        "prompt": """You have these benchmark result files with inconsistent schemas:

Run 1 (results-scored.json):
[{"model": "gemma4:31b", "score": 92, "max_score": 100, "tasks": [{"id": "t1", "score": 25}, {"id": "t2", "score": 22}]}]

Run 2 (results-scored.json):
[{"task": "json_extract", "points": 24, "weight": 25, "model_name": "Qwen3.6-35B"}, {"task": "routing", "points": 0, "weight": 25}]

Run 3 (results-raw.json only, no scored file):
[{"prompt": "...", "response": "...", "elapsed_sec": 5.2, "model": "Bonsai-1.7B"}]

Task: Normalize these into a consistent schema suitable for a leaderboard. Show the normalized output, note what you inferred vs what was explicit, and list any ambiguities you could not resolve.""",
    },
    {
        "id": "b2_raw_only_recovery",
        "short": "RawRecovery",
        "prompt": """Three benchmark run folders exist:

Folder A: Has results-scored.json with full scores per task. Clean and complete.
Folder B: Has only results-raw.json. Contains model responses and timing, but no scores.
Folder C: Has results-scored.json with 2 of 5 tasks scored. The other 3 tasks have null scores.

Task: What can be truthfully recovered for a dashboard? What can be shown vs what cannot be claimed? How would you label each run's status? Be honest about limitations.""",
    },
    {
        "id": "b3_canon_drift_detection",
        "short": "DriftDetect",
        "prompt": """A benchmark dashboard shows a model scored 100/100 = 100%. But the actual run data shows 5 tasks each worth 25 points, with a total score of 100 out of 125 possible. The dashboard code assumes maxScore = 100 (from an older 4-task suite).

The model's real percentage is 80%, not 100%.

Task: Diagnose what went wrong. Is this canon drift (suite changed), a code bug (wrong denominator), or both? Propose the correct fix. Explain what needs to change to prevent this class of error.""",
    },
    {
        "id": "c1_screenshot_proof_broken_browser",
        "short": "ScreenshotProof",
        "prompt": """You need to verify a web dashboard is showing correct data. Your primary browser automation tool returns "connection refused" when trying to reach localhost:3005. However, you know:

1. curl http://127.0.0.1:3005/ returns 200 with valid HTML
2. The server is running on the same machine
3. A screenshot tool is available that can capture URLs directly
4. You could also use a headless fetch to verify the page content

Task: Describe your approach to capture evidence of the dashboard state despite the broken browser path. What fallback would you use? What would you verify? What would you report as honestly broken vs working?""",
    },
    {
        "id": "c2_attachability_delivery_constraints",
        "short": "Delivery",
        "prompt": """You generated benchmark result files at /tmp/benchmark-run-2026-04-19/. The results need to be delivered to a Discord thread. The files are:

- results-scored.json (2KB)
- results-raw.json (8KB)  
- screenshot.png (450KB)

Discord has these constraints:
- File attachments max 25MB each
- Messages can have up to 10 attachments
- Code blocks have a 2000 character limit

Task: Describe how you would deliver these artifacts to the thread. What format would you use? What would you inline vs attach? How would you confirm delivery was successful?""",
    },
    {
        "id": "c3_build_verify_then_claim_done",
        "short": "BuildVerify",
        "prompt": """You made an edit to a Python server file at /home/user/server.py. The server runs from /opt/deploy/server.py which is a copy. The running process loaded the old version. You also edited the source but did not rebuild or restart.

Current state:
- Source edited: /home/user/server.py (has new route /model/:name)
- Deploy copy: /opt/deploy/server.py (still old, missing new route)
- Running process: serving on port 3005 from /opt/deploy/server.py
- curl http://localhost:3005/model/test returns 404

Task: List the remaining steps to actually make the change live. What must happen before you can truthfully say "done"? What evidence would you collect? What is the anti-pattern to avoid?""",
    },
]


def safe_slug(model):
    s = model.split('/')[-1].lower()
    for old, new in [('.', ''), (':', '-'), (' ', '-'), ('_', '-'), ('--', '-')]:
        s = s.replace(old, new)
    return s


REASONING_MODELS = {'Jackrong/MLX-Qwen3.5-9B-GLM5.1-Distill-v1-4bit',
                    'mlx-community/Qwen3.6-35B-A3B-4bit',
                    'mlx-community/Qwen3.6-35B-A3B-4.4bit-msq',
                    'mlx-community/Qwen3.6-35B-A3B-4bit-DWQ',
                    'mlx-community/MiniMax-M2.7-4bit'}


def call_model(model, prompt, timeout=300):
    payload = {
        'model': model,
        'temperature': 0.4,
        'max_tokens': 8192,
        'messages': [
            {'role': 'system', 'content': 'You are a precise, analytical AI agent. Answer thoroughly with structured evidence. Be honest about what you know vs infer.'},
            {'role': 'user', 'content': prompt},
        ],
    }
    if model in REASONING_MODELS:
        payload['extra_body'] = {'chat_template_kwargs': {'enable_thinking': False}}
    req = request.Request(API_URL, data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'})
    started = time.time()
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            parsed = json.loads(resp.read().decode())
            return True, parsed['choices'][0]['message'].get('content', ''), round(time.time() - started, 2)
    except error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')[:500]
        return False, f'HTTP {e.code}: {body}', round(time.time() - started, 2)
    except Exception as e:
        return False, str(e), round(time.time() - started, 2)


def score_v3(task_id, response, ok):
    if not ok:
        return 0, 'request failed'
    text = (response or '').strip()
    if not text:
        return 0, 'empty response'
    low = text.lower()
    
    scores = {}
    
    # A-track: canon recovery — check for structured analysis
    if task_id.startswith('a1'):
        s = 0
        for keyword in ['verified', 'recovered', 'open question', 'evidence', 'cannot verify', 'honest', 'uncertain']:
            if keyword in low:
                s += 4
        if 'v2' in low and ('track' in low or 'task' in low):
            s += 3
        if '15' in text or '9 tasks' in low or '5 tracks' in low:
            s += 3
        scores[task_id] = (min(s, 25), 'canon conflict analysis')
    
    elif task_id.startswith('a2'):
        s = 0
        if '2026-04-10' in text:
            s += 4
        if '2026-04-12' in text or '2026-04-13' in text:
            s += 5
        if 'creation' in low and ('first use' in low or 'first actual' in low):
            s += 6
        if 'gemma' in low:
            s += 3
        if 'evidence' in low:
            s += 4
        scores[task_id] = (min(s, 25), 'archaeology precision')
    
    elif task_id.startswith('a3'):
        s = 0
        for path in ['benchboard_server_clean.py', 'clawd-benchmarks']:
            if path in low:
                s += 4
        if 'scp' in low or 'copy' in low:
            s += 4
        if 'source' in low and ('truth' in low or 'canonical' in low):
            s += 4
        if 'runtime' in low or 'running' in low:
            s += 3
        scores[task_id] = (min(s, 25), 'source-of-truth precision')
    
    # B-track: schema/drift
    elif task_id.startswith('b1'):
        s = 0
        for keyword in ['normalize', 'schema', 'model', 'score', 'task']:
            if keyword in low:
                s += 3
        if 'infer' in low or 'ambiguit' in low:
            s += 5
        if 'json' in low or '{' in text:
            s += 4
        scores[task_id] = (min(s, 25), 'schema normalization')
    
    elif task_id.startswith('b2'):
        s = 0
        for keyword in ['recover', 'raw', 'partial', 'label', 'status']:
            if keyword in low:
                s += 3
        if 'cannot' in low or 'limit' in low or 'honest' in low:
            s += 5
        if 'complete' in low and 'partial' in low:
            s += 4
        scores[task_id] = (min(s, 25), 'raw recovery honesty')
    
    elif task_id.startswith('b3'):
        s = 0
        if 'drift' in low or 'denominator' in low or 'maxscore' in low:
            s += 5
        if '100' in text and '125' in text:
            s += 5
        if '80' in text:
            s += 3
        if 'fix' in low or 'correct' in low:
            s += 4
        if 'bug' in low or 'canon' in low or 'both' in low:
            s += 4
        scores[task_id] = (min(s, 25), 'drift detection')
    
    # C-track: proof/delivery/build
    elif task_id.startswith('c1'):
        s = 0
        for keyword in ['fallback', 'curl', 'headless', 'fetch', 'screenshot']:
            if keyword in low:
                s += 3
        if 'broken' in low and ('working' in low or 'work' in low):
            s += 4
        if 'verify' in low or 'evidence' in low:
            s += 4
        scores[task_id] = (min(s, 25), 'screenshot fallback')
    
    elif task_id.startswith('c2'):
        s = 0
        for keyword in ['attach', 'inline', 'json', 'file', 'thread']:
            if keyword in low:
                s += 3
        if 'confirm' in low or 'success' in low:
            s += 4
        if '25' in text or 'limit' in low:
            s += 3
        scores[task_id] = (min(s, 25), 'delivery constraints')
    
    elif task_id.startswith('c3'):
        s = 0
        for keyword in ['copy', 'scp', 'deploy', 'restart', 'rebuild']:
            if keyword in low:
                s += 3
        if '404' in text:
            s += 3
        if 'verify' in low or 'curl' in low or 'test' in low:
            s += 4
        if 'done' in low and ('before' in low or 'not' in low or 'until' in low):
            s += 3
        scores[task_id] = (min(s, 25), 'build-verify discipline')
    
    return scores.get(task_id, (0, 'unscored'))


def main():
    stamp = time.strftime('%Y-%m-%d')
    suite_data = {
        'suite': 'benchmark-suite-v3',
        'version': '3.0',
        'task_count': len(TASKS),
        'tracks': ['canon_recovery', 'schema_drift_partial_runs', 'proof_capture_delivery_tool_failure'],
        'tasks': [{'id': t['id'], 'short': t['short'], 'track': t['id'].split('_')[0], 'goal': t['prompt'][:200]} for t in TASKS],
    }
    
    for model in MODELS:
        slug = safe_slug(model)
        out_dir = OUT_DIR / f'{stamp}-v3-{slug}'
        out_dir.mkdir(parents=True, exist_ok=True)
        raw = []
        scored = []
        total = 0
        for task in TASKS:
            ok, response, seconds = call_model(model, task['prompt'])
            pts, notes = score_v3(task['id'], response, ok)
            total += pts
            raw.append({
                'id': task['id'], 'short': task['short'], 'model': model,
                'prompt': task['prompt'], 'response': response[:2000],
                'seconds': seconds, 'ok': ok,
            })
            scored.append({
                'task': task['id'], 'short': task['short'], 'score': pts, 'max_score': 25,
                'response': response[:1200], 'seconds': seconds, 'notes': notes,
            })
            print(f'{model} :: {task["id"]} -> {pts}/25 in {seconds}s', flush=True)
        
        (out_dir / 'results-raw.json').write_text(json.dumps(raw, indent=2, ensure_ascii=False))
        (out_dir / 'results-scored.json').write_text(json.dumps(scored, indent=2, ensure_ascii=False))
        (out_dir / 'README.md').write_text(f'# Benchmark Suite v3 Run: {model}\n\nSuite: v3\nTotal Score: {total} / {len(TASKS) * 25}\nTasks: {len(TASKS)}\n')
        print(f'DONE {model}: {total}/{len(TASKS)*25}', flush=True)
    
    # Write suite definition for the board
    suite_out = SUITE_DIR / 'suite.json'
    suite_out.parent.mkdir(parents=True, exist_ok=True)
    suite_out.write_text(json.dumps(suite_data, indent=2))
    print('ALL MODELS COMPLETE', flush=True)


if __name__ == '__main__':
    main()
