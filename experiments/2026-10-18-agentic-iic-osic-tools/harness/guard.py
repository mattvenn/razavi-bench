#!/usr/bin/env python3
"""PreToolUse guard for the razavi-answerer subagent.

Fails closed: any tool call that is not one of the two allowed shapes, and any
error while checking, is denied (exit 2). Every decision is logged.

Allowed:
  Bash  exactly:  docker exec -i rb-sbx-<slug> bash -s <<'RBEOF'\n<body>\nRBEOF
        (quoted heredoc, so the host shell expands nothing; the body runs
        inside a --network none container that holds only public task inputs)
  Read  /work/rb/<slug>/in/instruction.md or /work/rb/<slug>/in/figure-N.png,
        a regular file (not a symlink) whose realpath is the path itself.
"""
import json
import os
import re
import sys
import time

LOG = "/work/rb-guard/log.jsonl"
SLUG = r"[a-z0-9][a-z0-9-]*"
BASH_RE = re.compile(
    r"docker exec -i rb-sbx-(" + SLUG + r") bash -s <<'RBEOF'\n"
    r"((?:.*\n)*?)"
    r"RBEOF\n?",
)
READ_RE = re.compile(r"/work/rb/(" + SLUG + r")/in/(instruction\.md|figure-[0-9]+\.png)")


def log(entry):
    try:
        with open(LOG, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass


def check(data):
    tool = data.get("tool_name", "")
    inp = data.get("tool_input") or {}
    if tool == "Bash":
        cmd = inp.get("command", "")
        m = BASH_RE.fullmatch(cmd)
        if not m:
            return False, "Bash is only allowed as: docker exec -i rb-sbx-<slug> bash -s <<'RBEOF' ... RBEOF (nothing before or after)"
        if any(line == "RBEOF" for line in m.group(2).split("\n")):
            return False, "heredoc body may not contain the terminator"
        if inp.get("dangerouslyDisableSandbox"):
            return False, "sandbox override not allowed"
        return True, "ok"
    if tool == "Read":
        p = inp.get("file_path", "")
        if not READ_RE.fullmatch(p):
            return False, "Read is only allowed on /work/rb/<slug>/in/instruction.md or figure-N.png"
        if os.path.islink(p) or not os.path.isfile(p) or os.path.realpath(p) != p:
            return False, "path must be a regular, non-symlink file"
        return True, "ok"
    return False, f"tool {tool!r} is not allowed for the answerer"


def main():
    raw = sys.stdin.read()
    try:
        data = json.loads(raw)
        ok, why = check(data)
    except Exception as e:  # fail closed
        data, ok, why = {"raw": raw[:2000]}, False, f"guard error: {e}"
    log({"t": time.time(), "allow": ok, "why": why,
         "agent_type": data.get("agent_type"), "agent_id": data.get("agent_id"),
         "tool": data.get("tool_name"), "input": data.get("tool_input")})
    if ok:
        sys.exit(0)
    print(f"DENIED by razavi sandbox guard: {why}", file=sys.stderr)
    sys.exit(2)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except BaseException:
        sys.exit(2)
