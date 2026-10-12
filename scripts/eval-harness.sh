#!/usr/bin/env bash
# Runs AgentCore Evaluations on a harness's recent sessions.
#   eval-harness.sh intake_agent Builtin.Correctness Builtin.Helpfulness Builtin.ToolSelectionAccuracy AmountCheck
#
# `agentcore run eval --runtime <name>` only knows runtimes defined in the project, and a harness
# isn't one, so this looks up the Runtime the harness runs on and the evaluators' ARNs, then uses
# the CLI's standalone mode. Works whether you built the harness in the console or with the CLI.
# Run this, don't source it: sourcing would run it in your own shell and could close it.
(return 0 2>/dev/null) && { echo "This is a script, so run it rather than sourcing it: ${WORKSHOP:-.}/scripts/eval-harness.sh" >&2; return 1; }
set -euo pipefail
source "$(dirname "$0")/lib/common.sh"
need agentcore "Install it with: npm install -g @aws/agentcore"
[[ $# -ge 2 ]] || die "Usage: eval-harness.sh <harness> <evaluator> [<evaluator> ...]   (DAYS=1 by default)"

harness="$1"; shift
runtime_arn="$(agentcore_py harness-runtime-arn "$harness")"

# One evaluator at a time, so a problem with one (for example a tool-level evaluator that
# can't find a span in a trace that's still arriving) doesn't stop the others.
echo "Scoring the last ${DAYS:-1} day(s) of $harness sessions."
failed=""
for e in "$@"; do
  arn="$(agentcore_py evaluator-arn "$e")"
  echo
  echo "== $e"
  if ! agentcore run eval --runtime-arn "$runtime_arn" --evaluator-arn "$arn" \
       --region "$AWS_REGION" --days "${DAYS:-1}"; then
    failed="$failed $e"
  fi
done

if [[ -n "$failed" ]]; then
  echo
  echo "Didn't finish:$failed."
  echo "If the error mentions missing spanIds, some traces were still arriving. Wait a few minutes"
  echo "and run just those again, for example: $0 $harness$failed"
  exit 1
fi
