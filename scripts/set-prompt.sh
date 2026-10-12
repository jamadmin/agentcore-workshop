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
[[ -f "$dir/harness.json" ]] || die "No $dir/harness.json here. Is the harness called $harness in this project?"

# The CLI deploys harness.json's systemPrompt when it's set; system-prompt.md is only read
# when harness.json has no systemPrompt. Write to whichever one the deploy will use.
python3 - "$dir" "$prompt" <<'PY'
import json, os, sys
d, prompt_file = sys.argv[1], sys.argv[2]
prompt = open(prompt_file, encoding="utf-8").read()
path = os.path.join(d, "harness.json")
cfg = json.load(open(path, encoding="utf-8"))
if "systemPrompt" in cfg or not os.path.exists(os.path.join(d, "system-prompt.md")):
    cfg["systemPrompt"] = prompt
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh, indent=2)
        fh.write("\n")
    print(f"Updated systemPrompt in {path}.")
else:
    with open(os.path.join(d, "system-prompt.md"), "w", encoding="utf-8") as fh:
        fh.write(prompt)
    print(f"Updated {d}/system-prompt.md.")
PY
echo "Run agentcore deploy -y to apply it."
