#!/bin/bash
# Run one sandboxed answerer for a Razavi-Bench task.
#   run_task.sh <slug> [prompt-override]
# Expects run_rollout.sh to have staged $RB_ROOT/<slug>/in and written
# $RB_ROOT/.guard/settings.json. Logs go to $RB_ROOT/.runs/<slug>.*
set -u
HARNESS=$(cd "$(dirname "$0")" && pwd)
: "${RB_ROOT:=/work/rb}" "${RB_IMAGE:=hpretl/iic-osic-tools:2026.10}"
: "${RB_MODEL:=claude-opus-5-5}" "${RB_EFFORT:=max}" "${RB_TASK_TIMEOUT:=3600}"
slug="$1"; prompt="${2:-}"
logdir="$RB_ROOT/.runs"; mkdir -p "$logdir"
IICPATH=/headless/.local/bin:/foss/tools/bin:/foss/tools/sak:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/foss/tools/klayout:/foss/tools/osic-multitool
docker rm -f "rb-sbx-$slug" >/dev/null 2>&1
docker run -d --name "rb-sbx-$slug" --network none --entrypoint sleep \
  -e PATH=$IICPATH -e PDK_ROOT=/foss/pdks -e PDK=sky130A -e HOME=/headless \
  -v "$RB_ROOT/$slug/in:/task:ro" -v "$RB_ROOT/$slug/out:/out" -w /out \
  "$RB_IMAGE" infinity >/dev/null || { echo "$slug container failed"; exit 1; }
[ -z "$prompt" ] && prompt="Your task slug is: $slug. Answer the Razavi-Bench question in $RB_ROOT/$slug/in/instruction.md following your instructions. Write the final answer to /out/answer.md inside the container rb-sbx-$slug."
brief=$(sed -e "s#<root>#$RB_ROOT#g" -e "s/<slug>/$slug/g" "$HARNESS/brief.md")

# Start claude from a cleared environment: only PATH/HOME, RB_ROOT for the
# guard, and whichever auth/proxy variables are actually set.
envargs=(HOME="$HOME" PATH="$PATH" RB_ROOT="$RB_ROOT")
for v in ANTHROPIC_API_KEY ANTHROPIC_BASE_URL CLAUDE_CODE_OAUTH_TOKEN \
         HTTPS_PROXY HTTP_PROXY NO_PROXY NODE_EXTRA_CA_CERTS SSL_CERT_FILE \
         CLAUDE_CODE_PROVIDER_MANAGED_BY_HOST CLAUDE_SESSION_INGRESS_TOKEN_FILE; do
  [ -n "${!v:-}" ] && envargs+=("$v=${!v}")
done
cd "$RB_ROOT/$slug/in"
env -i "${envargs[@]}" timeout "$RB_TASK_TIMEOUT" claude -p "$prompt" \
    --model "$RB_MODEL" --effort "$RB_EFFORT" \
    --append-system-prompt "$brief" \
    --tools "Bash,Read" --allowedTools "Bash" "Read" \
    --settings "$RB_ROOT/.guard/settings.json" --setting-sources "" \
    --strict-mcp-config --mcp-config '{"mcpServers":{}}' --disable-slash-commands \
    --output-format json > "$logdir/$slug.json" 2> "$logdir/$slug.err"
rc=$?
# Harvest from inside the container (a symlink in /out can't resolve to host files this way).
docker exec "rb-sbx-$slug" cat /out/answer.md > "$logdir/$slug.answer.md" 2>/dev/null
docker rm -f "rb-sbx-$slug" >/dev/null 2>&1
echo "$slug rc=$rc answer_bytes=$(wc -c < "$logdir/$slug.answer.md")"
