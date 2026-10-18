#!/bin/bash
# Run one sandboxed answerer for a Razavi-Bench task: ./run_task.sh <slug> [prompt-override]
set -u; : "${HTTP_PROXY:=}" "${NO_PROXY:=}" "${SSL_CERT_FILE:=}" "${NODE_EXTRA_CA_CERTS:=}"
slug="$1"; prompt="${2:-}"
logdir=/work/rb-runs; mkdir -p "$logdir"
IICPATH=/headless/.local/bin:/foss/tools/bin:/foss/tools/sak:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/foss/tools/klayout:/foss/tools/osic-multitool
docker rm -f "rb-sbx-$slug" >/dev/null 2>&1
docker run -d --name "rb-sbx-$slug" --network none --entrypoint sleep \
  -e PATH=$IICPATH -e PDK_ROOT=/foss/pdks -e PDK=sky130A -e HOME=/headless \
  -v "/work/rb/$slug/in:/task:ro" -v "/work/rb/$slug/out:/out" -w /out \
  hpretl/iic-osic-tools:2026.10 infinity >/dev/null || { echo "container failed"; exit 1; }
[ -z "$prompt" ] && prompt="Your task slug is: $slug. Answer the Razavi-Bench question in /work/rb/$slug/in/instruction.md following your instructions. Write the final answer to /out/answer.md inside the container rb-sbx-$slug."
brief=$(sed "s/<slug>/$slug/g" /work/rb-guard/brief.md)
cd "/work/rb/$slug/in"
env -i HOME=/root PATH="$PATH" HTTPS_PROXY="$HTTPS_PROXY" HTTP_PROXY="$HTTP_PROXY" NO_PROXY="$NO_PROXY" \
  NODE_EXTRA_CA_CERTS="$NODE_EXTRA_CA_CERTS" SSL_CERT_FILE="$SSL_CERT_FILE" ANTHROPIC_BASE_URL="$ANTHROPIC_BASE_URL" \
  CLAUDE_CODE_PROVIDER_MANAGED_BY_HOST="$CLAUDE_CODE_PROVIDER_MANAGED_BY_HOST" \
  CLAUDE_SESSION_INGRESS_TOKEN_FILE="$CLAUDE_SESSION_INGRESS_TOKEN_FILE" \
  timeout 3600 claude -p "$prompt" --model claude-opus-5-5 --effort max \
    --append-system-prompt "$brief" \
    --tools "Bash,Read" --allowedTools "Bash" "Read" \
    --settings /work/rb-guard/settings.json --setting-sources "" \
    --strict-mcp-config --mcp-config '{"mcpServers":{}}' --disable-slash-commands \
    --output-format json > "$logdir/$slug.json" 2> "$logdir/$slug.err"
rc=$?
# Harvest from inside the container (a symlink in /out can't resolve to host files this way).
docker exec "rb-sbx-$slug" cat /out/answer.md > "$logdir/$slug.answer.md" 2>/dev/null
docker rm -f "rb-sbx-$slug" >/dev/null 2>&1
echo "$slug rc=$rc answer_bytes=$(wc -c < "$logdir/$slug.answer.md")"
