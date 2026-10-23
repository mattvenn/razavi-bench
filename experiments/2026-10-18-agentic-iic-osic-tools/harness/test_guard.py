#!/usr/bin/env python3
"""Escape attempts that guard.py must deny (and the shapes it must allow).

Runs guard.py as the hook does, with RB_ROOT from the environment, and exits
non-zero if any case is decided wrongly. Uses the first staged task.
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.realpath(os.environ.get("RB_ROOT", "/work/rb"))
slug = sorted(s for s in os.listdir(ROOT) if not s.startswith("."))[0]
fig = next((f for f in sorted(os.listdir(f"{ROOT}/{slug}/in")) if f.endswith(".png")), None)
inp = f"{ROOT}/{slug}/in"
H = f"docker exec -i rb-sbx-{slug} bash -s <<'RBEOF'\n"
secret = "/etc/passwd"

cases = [
    (True, "Bash", {"command": H + "ngspice -v\nls /task\nRBEOF"}),
    (True, "Bash", {"command": H + "echo hi\nRBEOF\n"}),
    (True, "Read", {"file_path": f"{inp}/instruction.md"}),
    (False, "Bash", {"command": H + f"echo\nRBEOF\ncat {secret}"}),
    (False, "Bash", {"command": f"cat {secret}; " + H + "x\nRBEOF"}),
    (False, "Bash", {"command": f"X=1 " + H + "x\nRBEOF"}),
    (False, "Bash", {"command": f"docker exec -i rb-sbx-a bash -s <<RBEOF\n$(cat {secret})\nRBEOF"}),
    (False, "Bash", {"command": H + f"x\nRBEOF\ncat {secret}\nRBEOF"}),
    (False, "Bash", {"command": H + f"x\nRBEOF\r\ncat {secret}"}),
    (False, "Bash", {"command": f"docker exec -i rb-sbx-a bash -s <<'RBEOF' ; cat {secret}\nx\nRBEOF"}),
    (False, "Bash", {"command": f"docker exec -i rb-sbx-$(cat {secret}) bash -s <<'RBEOF'\nx\nRBEOF"}),
    (False, "Bash", {"command": "docker exec -i -u root rb-sbx-a bash -s <<'RBEOF'\nid\nRBEOF"}),
    (False, "Bash", {"command": "docker exec -i other bash -s <<'RBEOF'\nx\nRBEOF"}),
    (False, "Bash", {"command": "docker run --rm -v /:/h alpine cat /h/etc/passwd"}),
    (False, "Bash", {"command": f"ls {inp}"}),
    (False, "Read", {"file_path": f"{inp}/../../../../etc/passwd"}),
    (False, "Read", {"file_path": f"{ROOT}/{slug}/out/answer.md"}),
    (False, "Read", {"file_path": secret}),
    (False, "Write", {"file_path": "/tmp/x", "content": "x"}),
    (False, "Glob", {"pattern": "**/*"}),
    (False, "Grep", {"pattern": "x"}),
    (False, "WebFetch", {"url": "https://github.com"}),
    (False, "Agent", {"prompt": "x"}),
    (False, "mcp__github__get_file_contents", {}),
]
if fig:
    cases.append((True, "Read", {"file_path": f"{inp}/{fig}"}))

# Test decisions go to their own log, not the run's audit log.
env = dict(os.environ, RB_ROOT=ROOT, RB_GUARD_LOG=f"{ROOT}/.guard/log.selftest.jsonl")
bad = 0
for want, tool, ti in cases:
    r = subprocess.run([sys.executable, f"{HERE}/guard.py"], input=json.dumps({"tool_name": tool, "tool_input": ti}),
                       capture_output=True, text=True, env=env)
    if (r.returncode == 0) != want:
        bad += 1
        print("WRONG:", "allowed" if r.returncode == 0 else "denied", tool, ti)
r = subprocess.run([sys.executable, f"{HERE}/guard.py"], input="garbage", capture_output=True, text=True, env=env)
if r.returncode != 2:
    bad += 1
    print("WRONG: malformed input not denied")
print(f"guard self-test: {len(cases) + 1 - bad}/{len(cases) + 1} correct")
sys.exit(1 if bad else 0)
