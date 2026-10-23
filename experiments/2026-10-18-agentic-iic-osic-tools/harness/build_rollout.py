#!/usr/bin/env python3
"""Build the answer JSONL for one rollout from $RB_ROOT/.runs.

  build_rollout.py <rollout-number>

Writes ../claude-opus-5-5/model_outputs/claude-opus-5-5-agentic-iic-max-rollout-<N>.jsonl
in the direct-QA row schema (plus mode and tools_used) and merges per-task
usage into ../claude-opus-5-5/usage.json under "<N>:<task_slug>". Exits
non-zero, writing nothing, if any task lacks a completed, non-empty answer.
"""
import datetime
import json
import os
import re
import sys

N = int(sys.argv[1])
ROOT = os.path.realpath(os.environ.get("RB_ROOT", f"/work/rb-r{N}"))
MODEL = os.environ.get("RB_MODEL", "claude-opus-5-5")
EFFORT = os.environ.get("RB_EFFORT", "max")
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "claude-opus-5-5")
RUNS = os.path.join(ROOT, ".runs")

slugs = sorted(s for s in os.listdir(ROOT) if not s.startswith("."))
missing = []
for s in slugs:
    a, j = f"{RUNS}/{s}.answer.md", f"{RUNS}/{s}.json"
    ok = os.path.exists(a) and open(a).read().strip() and os.path.exists(j)
    if ok:
        try:
            ok = json.load(open(j)).get("terminal_reason") == "completed"
        except ValueError:
            ok = False
    if not ok:
        missing.append(s)
if missing:
    print(f"rollout {N}: {len(missing)} task(s) incomplete, re-run run_rollout.sh {N}:")
    print("\n".join("  " + s for s in missing))
    sys.exit(1)

rows, usage = [], {}
for s in slugs:
    inst = open(f"{ROOT}/{s}/in/instruction.md").read()
    q = re.search(r"## Question\s*\n(.*?)(?:\n## |\Z)", inst, re.S).group(1).strip()
    r = json.load(open(f"{RUNS}/{s}.json"))
    m = re.search(r"TOOLS_USED: ngspice=(\w+) xschem=(\w+)", r.get("result", ""))
    u = r["usage"]
    usage[f"{N}:{s}"] = {
        "input_tokens": u["input_tokens"] + u.get("cache_creation_input_tokens", 0) + u.get("cache_read_input_tokens", 0),
        "cached_input_tokens": u.get("cache_read_input_tokens", 0),
        "output_tokens": u["output_tokens"],
        "num_turns": r.get("num_turns"), "duration_ms": r.get("duration_ms"),
        "cost_usd_list": r.get("total_cost_usd"),
    }
    part, num = re.match(r"(part\d)-(\d+)", s).groups()
    rows.append({
        "answer": open(f"{RUNS}/{s}.answer.md").read().strip(),
        "benchmark": "razavi-bench", "experiment": "2026-10-18-agentic-iic-osic-tools",
        "figures": sorted(f for f in os.listdir(f"{ROOT}/{s}/in") if f.endswith(".png")),
        "internet_or_tool_evidence": False, "mode": "agentic-iic-osic-tools", "model_call_attempts": 1,
        "model_family": "anthropic", "model_name": "Claude Opus 5.5", "part": part, "provider_model": MODEL,
        "question": q, "question_number": int(num), "reasoning_effort": EFFORT, "rollout": N,
        "run_date": datetime.date.fromtimestamp(os.path.getmtime(f"{RUNS}/{s}.json")).isoformat(),
        "task_path": f"tasks/{s}", "task_slug": s,
        "tools_used": {"ngspice": m.group(1) == "yes", "xschem": m.group(2) == "yes"} if m else None,
    })

os.makedirs(f"{OUT}/model_outputs", exist_ok=True)
path = f"{OUT}/model_outputs/{MODEL}-agentic-iic-{EFFORT}-rollout-{N}.jsonl"
with open(path, "w") as f:
    for x in rows:
        f.write(json.dumps(x, ensure_ascii=False) + "\n")
upath = f"{OUT}/usage.json"
allu = json.load(open(upath)) if os.path.exists(upath) else {}
allu.update(usage)
json.dump(dict(sorted(allu.items())), open(upath, "w"), indent=1)
out = sum(v["output_tokens"] for v in usage.values())
cost = sum(v["cost_usd_list"] or 0 for v in usage.values())
print(f"rollout {N}: wrote {len(rows)} answers to {os.path.relpath(path)}; "
      f"{out:,} output tokens, ${cost:.2f} list price")
