#!/usr/bin/env bash
# Switches on managed memory (semantic facts and summaries) for a harness in the AgentCore
# project you're in. `agentcore add harness` leaves memory off by default.
#   set-memory.sh kopi_agent
# Run this, don't source it: sourcing would run it in your own shell and could close it.
(return 0 2>/dev/null) && { echo "This is a script, so run it rather than sourcing it: ${WORKSHOP:-.}/scripts/set-memory.sh" >&2; return 1; }
set -euo pipefail
source "$(dirname "$0")/lib/common.sh"
[[ $# -eq 1 ]] || die "Usage: set-memory.sh <harness name>"
path="app/$1/harness.json"
[[ -f agentcore/agentcore.json ]] || die "Run this from your AgentCore project folder (the one with agentcore/agentcore.json)."
[[ -f "$path" ]] || die "No $path here. Is the harness called $1 in this project?"
python3 - "$path" <<'PY'
import json, sys
path = sys.argv[1]
cfg = json.load(open(path, encoding="utf-8"))
cfg["memory"] = {"mode": "managed", "strategies": ["SEMANTIC", "SUMMARIZATION"]}
with open(path, "w", encoding="utf-8") as fh:
    json.dump(cfg, fh, indent=2)
    fh.write("\n")
print(f'Set "memory" in {path} to managed (SEMANTIC and SUMMARIZATION).')
PY
