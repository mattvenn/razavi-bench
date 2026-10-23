#!/bin/bash
# Run one full rollout (50 tasks) of the sandboxed agentic evaluation.
#   run_rollout.sh <rollout-number> [concurrency]
# Run from anywhere inside the repository checkout. Environment overrides:
#   RB_ROOT (staging dir, outside the repo; default /work/rb-r<N>),
#   RB_IMAGE, RB_MODEL, RB_EFFORT, RB_TASK_TIMEOUT (seconds per task),
#   RB_ONLY (space-separated task slugs, to run a subset).
# Re-running skips tasks that already have a non-empty answer.
set -euo pipefail
HARNESS=$(cd "$(dirname "$0")" && pwd)
REPO=$(git -C "$HARNESS" rev-parse --show-toplevel)
N="${1:?usage: run_rollout.sh <rollout-number> [concurrency]}"; P="${2:-5}"
export RB_ROOT="${RB_ROOT:-/work/rb-r$N}"
export RB_IMAGE="${RB_IMAGE:-hpretl/iic-osic-tools:2026.10}"
case "$(realpath -m "$RB_ROOT")/" in "$REPO"/*) echo "RB_ROOT must be outside the repository"; exit 1;; esac

for c in docker claude python3; do command -v $c >/dev/null || { echo "missing: $c"; exit 1; }; done
docker image inspect "$RB_IMAGE" >/dev/null 2>&1 || docker pull "$RB_IMAGE"

# 1. Stage only instruction.md and figure PNGs (whitelist), read-only.
mkdir -p "$RB_ROOT/.guard" "$RB_ROOT/.runs"
for d in "$REPO"/tasks/*/; do
  s=$(basename "$d"); [ -d "$RB_ROOT/$s/in" ] && continue
  mkdir -p "$RB_ROOT/$s/in" "$RB_ROOT/$s/out"
  cp "$d/instruction.md" "$RB_ROOT/$s/in/"
  for f in "$d"/figure-*.png; do [ -e "$f" ] && cp "$f" "$RB_ROOT/$s/in/"; done
  chmod -R a-w "$RB_ROOT/$s/in"; chmod 777 "$RB_ROOT/$s/out"
done
extra=$(find "$RB_ROOT" -path "$RB_ROOT/.*" -prune -o -path '*/in/*' -type f \
        ! -name instruction.md ! -name 'figure-*.png' -print)
[ -z "$extra" ] || { echo "unexpected staged files: $extra"; exit 1; }
# The guard runs from the staging dir so that denial messages, which quote the
# hook command, don't reveal the repository path to the answerer.
cp "$HARNESS/guard.py" "$RB_ROOT/.guard/guard.py"
cat > "$RB_ROOT/.guard/settings.json" <<EOF
{"hooks":{"PreToolUse":[{"matcher":"*","hooks":[{"type":"command","command":"python3 $RB_ROOT/.guard/guard.py"}]}]},
 "permissions":{"allow":["Bash","Read"]}}
EOF

# 2. Preflight: guard unit tests and a sandbox check, before any paid call.
RB_ROOT="$RB_ROOT" python3 "$HARNESS/test_guard.py"
first=$(ls "$RB_ROOT" | head -1)
out=$(docker run --rm --network none --entrypoint bash -v "$RB_ROOT/$first/in:/task:ro" "$RB_IMAGE" -c '
  touch /task/x 2>/dev/null && echo TASK-WRITABLE
  [ -e /var/run/docker.sock ] && echo DOCKER-SOCKET
  python3 -c "import socket;socket.create_connection((\"1.1.1.1\",443),timeout=5)" 2>/dev/null && echo NETWORK
  [ -x /foss/tools/bin/ngspice ] || echo NO-NGSPICE; true')
[ -z "$out" ] || { echo "sandbox preflight failed: $out"; exit 1; }
echo "preflight ok: guard tests pass; sandbox has no network, no socket, read-only inputs"

# 3. Answer every task without a non-empty answer yet.
todo=()
for s in ${RB_ONLY:-$(ls "$RB_ROOT")}; do [ -s "$RB_ROOT/.runs/$s.answer.md" ] || todo+=("$s"); done
echo "rollout $N: ${#todo[@]} tasks to run, concurrency $P, staging $RB_ROOT"
for s in "${todo[@]}"; do find "$RB_ROOT/$s/out" -mindepth 1 -delete; done
printf '%s\n' "${todo[@]}" | xargs -r -P "$P" -I{} "$HARNESS/run_task.sh" {} | tee -a "$RB_ROOT/.runs/_progress.log" || true

# 4. Build the answer JSONL and audit the run.
python3 "$HARNESS/build_rollout.py" "$N"
python3 "$HARNESS/audit.py" "$N"
