#!/usr/bin/env python3
import json
import re
import time
from pathlib import Path
from urllib import request, error

API_ROOT = "http://100.104.229.62:18080/v1"
API_URL = f"{API_ROOT}/chat/completions"
REQUESTED_MODEL = "qwenglm9"
TEMPERATURE = 0.6
MAX_TOKENS = 700
OUT_DIR = Path("~/clawd/output/benchmarks/2026-04-19-qwenglm9-reconstructed").expanduser()
RAW_PATH = OUT_DIR / "results-raw.json"
SCORED_PATH = OUT_DIR / "results-scored.json"

TASKS = [
    {
        "task": "Extraction-1",
        "category": "Extraction",
        "prompt": "Extract the following into strict JSON with keys company, contact, budget_usd, deadline, blockers, and next_steps. Email: 'Hi team, I'm Nora from Helix Foods. We can allocate up to $48,500 this quarter for warehouse vision tooling. Procurement closes on 2026-05-12. Main blockers are ERP integration uncertainty and lack of a pilot success metric. Next steps: send security docs, propose a 3-week pilot, and book a technical review with DevOps.' Return JSON only."
    },
    {
        "task": "Extraction-2",
        "category": "Extraction",
        "prompt": "Read this memo and extract a markdown bullet list of every metric with its value and direction of change. Memo: 'Week 14: revenue reached $182k, up 12% week over week. Churn fell from 4.8% to 3.9%. NPS moved to 51 from 47. CAC increased by $19 to $143. Trial-to-paid conversion was flat at 8.4%. Support backlog dropped by 33 tickets to 71.'"
    },
    {
        "task": "Extraction-3",
        "category": "Extraction",
        "prompt": "From the text below, extract all dates, owners, and deliverables into a table with columns Date, Owner, Deliverable. Text: 'Amina will ship the pricing page rewrite by April 24. Ben owns the SOC2 evidence pack due April 29. Cara will deliver the partner onboarding playbook on May 2. The dry run happens April 22, facilitated by Diego.'"
    },
    {
        "task": "Tool Routing-1",
        "category": "Tool Routing",
        "prompt": "You are an agent with tools: web_fetch(url), browser(url), image(path), pdf(path), exec(command). For the user request 'Read https://example.com/pricing, inspect the signup modal, and compare any plan details shown in the PDF brochure at /tmp/brochure.pdf', choose the best tool sequence and explain why each tool is used. Keep it concise."
    },
    {
        "task": "Tool Routing-2",
        "category": "Tool Routing",
        "prompt": "Pick the best tool for each subtask and give a numbered plan. Available tools: memory_search(query), web_search(query), web_fetch(url), browser(url), exec(command), spreadsheet(path). User asks: 'Find whether our team has discussed Acme Corp before, look up their latest funding news, open their careers page to see if they are hiring solutions engineers, and then analyze the CSV I uploaded.'"
    },
    {
        "task": "Tool Routing-3",
        "category": "Tool Routing",
        "prompt": "An assistant can use browser, web_fetch, camofox, exec, and pdf. The user says: 'Log into the vendor portal if needed, download the April invoice PDF, and extract the total due.' Recommend the safest and most reliable tool path, including fallbacks, and state what should not be done prematurely."
    },
    {
        "task": "Reasoning-1",
        "category": "Reasoning",
        "prompt": "A team can only ship one of three features this sprint. Feature A adds $70k expected ARR with 0.55 probability and takes 8 dev-days. Feature B adds $40k ARR with 0.8 probability and takes 3 dev-days. Feature C reduces churn worth $90k ARR-equivalent with 0.35 probability and takes 5 dev-days. If the team has 5 dev-days and wants maximum expected value per sprint while also preferring lower execution risk when values are close, which feature should they choose and why? Show the math briefly."
    },
    {
        "task": "Reasoning-2",
        "category": "Reasoning",
        "prompt": "You manage a queue with jobs J1 to J5. Dependencies: J3 after J1, J4 after J2 and J3, J5 after J1. Durations in hours: J1=2, J2=4, J3=3, J4=2, J5=5. Two workers can operate in parallel. Give the minimum completion time and one valid schedule."
    },
    {
        "task": "Reasoning-3",
        "category": "Reasoning",
        "prompt": "A startup has $120k cash, burns $18k per month now, and can choose one of two experiments. Experiment X costs $24k once and has a 40% chance of reducing burn by $6k/month starting next month. Experiment Y costs $10k once and has a 25% chance of increasing monthly revenue enough to offset $9k/month starting in two months. Which experiment gives better expected 6-month cash preservation, and what is the expected difference?"
    },
    {
        "task": "Summarization-1",
        "category": "Summarization",
        "prompt": "Summarize this update for a CEO in exactly 4 bullets, each under 18 words: 'Engineering finished SSO, but audit logs slipped due to a schema migration issue. Sales closed Northstar Bank for $96k ARR and moved Ridgeway to legal. Customer success reported two escalations, both tied to slow imports on large CSVs. Marketing launched the attribution report, early CTR is 2.9%, and webinar registrations hit 418.'"
    },
    {
        "task": "Summarization-2",
        "category": "Summarization",
        "prompt": "Compress the following into a terse executive summary with sections: Wins, Risks, Decisions Needed. Text: 'The migration cut page latency from 1.8s to 1.1s. However, error rates spiked for legacy API keys, affecting 7 enterprise tenants. Support volume rose 14% after the billing UI refresh because invoice exports moved. Product wants approval to delay custom roles by one sprint so the team can stabilize billing and legacy auth.'"
    },
    {
        "task": "Summarization-3",
        "category": "Summarization",
        "prompt": "Turn this transcript into meeting notes with headings Summary, Decisions, Action Items. Transcript: 'We agreed to keep annual pricing unchanged through Q2. Jade will draft the partner reseller addendum by Thursday. Omar will gather churn reasons from the top 15 lost deals. We are not expanding the pilot scope until uptime stays above 99.9% for 30 days.'"
    },
    {
        "task": "General-1",
        "category": "General",
        "prompt": "Write a short but sharp reply to this client message: 'Your proposal looks promising, but we're worried the rollout will distract our ops team. Also, your pricing feels high versus doing this internally.' The reply should acknowledge concern, reduce rollout fear, defend value without sounding defensive, and end with a concrete next step."
    },
    {
        "task": "General-2",
        "category": "General",
        "prompt": "Draft a 6-line internal Slack update announcing that the team is pausing a feature launch for one week due to a critical reliability fix. Tone: calm, accountable, no drama, confidence intact."
    },
    {
        "task": "General-3",
        "category": "General",
        "prompt": "Create a compact decision memo recommending whether to hire a founding solutions engineer now or wait 3 months. Assume pipeline is growing fast, founders are handling demos, and onboarding docs are weak. Include recommendation, rationale, risks, and mitigation."
    },
]


def fetch_models():
    with request.urlopen(f"{API_ROOT}/models", timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8")).get("data", [])



def resolve_model_name(requested: str):
    models = fetch_models()
    ids = [m.get("id", "") for m in models]
    if requested in ids:
        return requested, ids
    requested_lower = requested.lower()
    preferred = [
        mid for mid in ids
        if "qwen" in mid.lower() and "9b" in mid.lower() and "glm" in mid.lower()
    ]
    if preferred:
        return preferred[0], ids
    fuzzy = [mid for mid in ids if requested_lower in mid.lower()]
    if fuzzy:
        return fuzzy[0], ids
    return requested, ids



def call_model(prompt: str, model_name: str):
    payload = {
        "model": model_name,
        "temperature": TEMPERATURE,
        "max_tokens": MAX_TOKENS,
        "messages": [
            {"role": "system", "content": "You are a precise, capable assistant."},
            {"role": "user", "content": prompt},
        ],
    }
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(API_URL, data=data, headers={"Content-Type": "application/json"})
    started = time.time()
    try:
        with request.urlopen(req, timeout=300) as resp:
            body = resp.read().decode("utf-8")
            parsed = json.loads(body)
            text = parsed["choices"][0]["message"]["content"]
            return {
                "ok": True,
                "response": text,
                "seconds": round(time.time() - started, 2),
                "raw": parsed,
            }
    except error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        return {
            "ok": False,
            "response": f"HTTPError {e.code}: {body}",
            "seconds": round(time.time() - started, 2),
            "raw": {"error": body, "status": e.code},
        }
    except Exception as e:
        return {
            "ok": False,
            "response": f"Exception: {e}",
            "seconds": round(time.time() - started, 2),
            "raw": {"error": str(e)},
        }


def score_response(task):
    response = task["response"] or ""
    prompt = task["prompt"]
    category = task["category"]
    score = 0
    notes = []

    if task.get("ok"):
        score += 5
        notes.append("API call succeeded")
    else:
        notes.append("API call failed")
        return 0, "; ".join(notes)

    words = len(re.findall(r"\S+", response))
    if words >= 40:
        score += 4
        notes.append("Substantive length")
    elif words >= 20:
        score += 2
        notes.append("Moderate length")
    else:
        notes.append("Very short response")

    lower = response.lower()

    if category == "Extraction":
        structural_hits = sum([
            1 if any(tok in response for tok in ["{", "}"]) else 0,
            1 if "|" in response else 0,
            1 if "- " in response or "* " in response else 0,
        ])
        score += min(structural_hits * 3, 6)
        if structural_hits:
            notes.append("Used structured output")
        fact_hits = 0
        for pattern in [r"\b\$?48,500\b", r"2026-05-12|May 12|April 24|April 29|May 2", r"Helix Foods|Amina|Ben|Cara|Diego"]:
            if re.search(pattern, response, re.I):
                fact_hits += 1
        score += min(fact_hits * 3, 9)
        notes.append(f"Fact hits: {fact_hits}")

    elif category == "Tool Routing":
        tools = ["web_fetch", "browser", "image", "pdf", "exec", "memory_search", "web_search", "spreadsheet", "camofox"]
        tool_hits = sum(1 for t in tools if t in lower)
        score += min(tool_hits, 6)
        if any(x in lower for x in ["why", "because", "fallback", "safest", "reliable"]):
            score += 5
            notes.append("Included rationale/fallbacks")
        numbered = len(re.findall(r"(^|\n)\s*\d+[\).]", response))
        if numbered:
            score += 4
            notes.append("Included ordered plan")
        notes.append(f"Tool mentions: {tool_hits}")

    elif category == "Reasoning":
        number_hits = len(re.findall(r"\b\d+(?:\.\d+)?\b", response))
        score += min(number_hits, 8)
        if any(x in lower for x in ["expected", "probability", "schedule", "minimum", "difference"]):
            score += 4
            notes.append("Reasoning terms present")
        if any(x in lower for x in ["therefore", "so ", "choose", "recommend"]):
            score += 3
            notes.append("Clear conclusion")

    elif category == "Summarization":
        if any(x in response for x in ["Wins", "Risks", "Decisions Needed", "Summary", "Decisions", "Action Items"]):
            score += 8
            notes.append("Respected requested headings")
        bullets = len(re.findall(r"(^|\n)\s*[-*]", response))
        if bullets >= 3:
            score += 6
            notes.append("Bullet structure present")
        key_terms = sum(1 for x in ["SSO", "$96k", "2.9%", "418", "1.1s", "7 enterprise tenants", "annual pricing", "99.9%"] if x.lower() in lower)
        score += min(key_terms * 2, 6)
        notes.append(f"Key term hits: {key_terms}")

    else:  # General
        if any(x in lower for x in ["next step", "call", "meeting", "pilot", "recommendation", "rationale", "risks", "mitigation"]):
            score += 7
            notes.append("Included requested business structure")
        if any(x in lower for x in ["understand", "concern", "pause", "reliability", "confidence", "recommend"]):
            score += 5
            notes.append("Tone/task alignment")
        line_count = response.count("\n") + 1
        if task["task"] == "General-2" and 5 <= line_count <= 7:
            score += 4
            notes.append("Matched 6-line format closely")
        elif task["task"] != "General-2":
            score += 3

    score = min(score, 25)
    return score, "; ".join(notes)


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    raw_results = []
    scored_results = []
    resolved_model, available_models = resolve_model_name(REQUESTED_MODEL)
    print(f"Requested model: {REQUESTED_MODEL}", flush=True)
    print(f"Resolved model: {resolved_model}", flush=True)

    for task in TASKS:
        result = call_model(task["prompt"], resolved_model)
        raw_entry = {
            "task": task["task"],
            "category": task["category"],
            "prompt": task["prompt"],
            "requested_model": REQUESTED_MODEL,
            "resolved_model": resolved_model,
            "available_models": available_models,
            "response": result["response"],
            "seconds": result["seconds"],
            "ok": result["ok"],
            "raw": result["raw"],
        }
        raw_results.append(raw_entry)

        score, notes = score_response({**task, **result})
        scored_results.append({
            "task": task["task"],
            "score": score,
            "max_score": 25,
            "response": result["response"],
            "seconds": result["seconds"],
            "notes": notes,
        })
        print(f"{task['task']}: {score}/25 in {result['seconds']}s", flush=True)

    RAW_PATH.write_text(json.dumps(raw_results, indent=2, ensure_ascii=False))
    SCORED_PATH.write_text(json.dumps(scored_results, indent=2, ensure_ascii=False))
    print(f"Wrote {RAW_PATH}", flush=True)
    print(f"Wrote {SCORED_PATH}", flush=True)


if __name__ == "__main__":
    main()
