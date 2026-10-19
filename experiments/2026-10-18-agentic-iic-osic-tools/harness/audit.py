#!/usr/bin/env python3
"""Blinding audit for one rollout. Prints counts only, never golden text.

  audit.py <rollout-number>

Checks the guard log in $RB_ROOT/.guard and every answer-agent transcript
under ~/.claude/projects for references to forbidden material and for any
100-character span of a golden solution (also checked in the answers).
Copies the gzipped guard log next to the answers and writes
../claude-opus-5-5/audit-rollout-<N>.json. Exits non-zero on any finding.
"""
import collections
import glob
import gzip
import json
import os
import re
import shutil
import subprocess
import sys

N = int(sys.argv[1])
ROOT = os.path.realpath(os.environ.get("RB_ROOT", f"/work/rb-r{N}"))
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = subprocess.check_output(["git", "-C", HERE, "rev-parse", "--show-toplevel"], text=True).strip()
OUT = os.path.join(HERE, "..", "claude-opus-5-5")
norm = lambda s: re.sub(r"\s+", " ", s)

# 1. Guard log: allowed calls are safe by construction; list denials.
log = f"{ROOT}/.guard/log.jsonl"
entries = [json.loads(l) for l in open(log)] if os.path.exists(log) else []
counts = collections.Counter("allowed" if e["allow"] else "denied" for e in entries)
denied = collections.Counter()
for e in entries:
    if not e["allow"]:
        i = e.get("input") or {}
        what = i.get("file_path") or (i.get("command") or "").split("\n")[0]
        denied[f'{e["tool"]}: {re.sub(r"[a-z0-9-]{20,}", "<slug>", what)[:100]}'] += 1

# 2. Transcripts and answers.
proj = os.path.expanduser("~/.claude/projects/") + re.sub(r"[^A-Za-z0-9]", "-", ROOT) + "-*"
files = [f for d in glob.glob(proj) for f in glob.glob(d + "/**/*.jsonl", recursive=True)]
text = norm(" ".join(open(f, errors="ignore").read() for f in files))
answers = norm(" ".join(open(f).read() for f in glob.glob(f"{ROOT}/.runs/*.answer.md")))
terms = ["golden_solution", "netlists/", "verify.py", "evaluation_rubric", "razavi-bench", "tokenzhang", "github.com/"]
term_hits = {t: text.count(t) for t in terms}
span_hits = 0
for g in glob.glob(f"{REPO}/tasks/*/golden_solution.md"):
    t = norm(open(g).read())
    span_hits += sum(1 for i in range(0, max(1, len(t) - 100), 50)
                     if len(t[i:i + 100]) == 100 and (t[i:i + 100] in text or t[i:i + 100] in answers))

report = {"rollout": N, "guard": dict(counts), "denied": dict(denied.most_common()),
          "transcript_files": len(files), "forbidden_term_hits": term_hits, "golden_span_hits": span_hits}
os.makedirs(OUT, exist_ok=True)
json.dump(report, open(f"{OUT}/audit-rollout-{N}.json", "w"), indent=1)
if os.path.exists(log):
    with open(log, "rb") as src, gzip.open(f"{OUT}/guard_log.rollout-{N}.jsonl.gz", "wb") as dst:
        shutil.copyfileobj(src, dst)

print(f"audit rollout {N}: guard {dict(counts)}; {len(files)} transcripts; "
      f"forbidden-term hits {sum(term_hits.values())}; golden 100-char spans {span_hits}")
for k, v in denied.most_common():
    print(f"  denied x{v}  {k}")
bad = sum(term_hits.values()) + span_hits
print("AUDIT CLEAN" if not bad else "AUDIT FINDINGS: inspect the transcripts before using this rollout")
sys.exit(1 if bad else 0)
