#!/usr/bin/env bash
# Replaces a harness's system prompt in the AgentCore project you're in, ready to deploy.
# Run it from the project folder, for example $WORKSHOP/IntakeQA.
#   set-prompt.sh intake_agent $WORKSHOP/intake/system-prompt-v2.md
# Run this, don't source it: sourcing would run it in your own shell and could close it.
(return 0 2>/dev/null) && { echo "This is a script, so run it rather than sourcing it: ${WORKSHOP:-.}/scripts/set-prompt.sh" >&2; return 1; }
set -euo pipefail
source "$(dirname "$0")/lib/common.sh"
[[ $# -eq 2 ]] || die "Usage: set-prompt.sh <harness name> <prompt file>"
harness="$1"; prompt="$2"
[[ -f "$prompt" ]] || die "No such file: $prompt"
[[ -f agentcore/agentcore.json ]] || die "Run this from your AgentCore project folder (the one with agentcore/agentcore.json)."
dir="app/$harness"
[[ -d "$dir" ]] || die "No $dir here. Is the harness called $harness in this project?"

if [[ -f "$dir/system-prompt.md" ]]; then
  # The CLI keeps the prompt in its own file next to harness.json.
  cp "$prompt" "$dir/system-prompt.md"
  echo "Updated $dir/system-prompt.md."
else
  python3 - "$dir/harness.json" "$prompt" <<'PY'
import json, sys
path, prompt = sys.argv[1], open(sys.argv[2], encoding="utf-8").read()
cfg = json.load(open(path, encoding="utf-8"))
cfg["systemPrompt"] = prompt
json.dump(cfg, open(path, "w", encoding="utf-8"), indent=2)
open(path, "a").write("\n")
PY
  echo "Updated systemPrompt in $dir/harness.json."
fi
echo "Run agentcore deploy -y to apply it."
