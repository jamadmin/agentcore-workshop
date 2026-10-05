#!/usr/bin/env bash
# Jumps a scenario to its finished state, whichever path you were on.
#   catch-up.sh kopi-run | tally | intake
#
# It looks for anything with the scenario's names (built in the console or with the
# CLI), lists it, and asks before replacing it. Then it builds the finished version
# with the AgentCore CLI, the same commands as the terminal path, and deploys it.
# Run this, don't source it: sourcing would run it in your own shell and could close it.
(return 0 2>/dev/null) && { echo "This is a script, so run it rather than sourcing it: ${WORKSHOP:-.}/scripts/catch-up.sh" >&2; return 1; }
set -euo pipefail
source "$(dirname "$0")/lib/common.sh"
need agentcore "Install it with: npm install -g @aws/agentcore"

scenario="${1:-}"
case "$scenario" in
  kopi-run) project=KopiRun ;;
  tally)    project=TallyTools ;;
  intake)   project=IntakeQA ;;
  *) die "Usage: catch-up.sh kopi-run|tally|intake" ;;
esac
project_dir="$WORKSHOP/$project"
started=$(date +%s)

# ---- find what's already there -------------------------------------------------------------

echo "Looking for anything you've already built for $scenario..."
inventory="$(agentcore_py inventory "$scenario")"
found="$(python3 "$WORKSHOP/scripts/lib/show.py" inventory <<<"$inventory")"
have_project=0
[[ -f "$project_dir/agentcore/agentcore.json" ]] && have_project=1

if [[ -n "$found" || "$have_project" -eq 1 || -d "$project_dir" ]]; then
  echo
  echo "This will be replaced:"
  [[ -n "$found" ]] && echo "$found"
  [[ -d "$project_dir" ]] && echo "  - the project folder $project_dir (moved aside, not deleted)"
  echo
  confirm "Replace it with the finished version?" || die "Stopped. Nothing changed."

  if [[ "$have_project" -eq 1 ]]; then
    echo "Removing what your CLI project deployed..."
    (cd "$project_dir" && agentcore remove all -y && agentcore deploy -y) \
      || echo "  (The project may not have been deployed yet. Carrying on.)"
  fi
  if [[ -d "$project_dir" ]]; then
    aside="$project_dir.replaced-$(date +%H%M%S)"
    mv "$project_dir" "$aside"
    echo "Moved your project folder to $aside"
  fi
  left="$(agentcore_py inventory "$scenario")"
  if [[ "$left" != "[]" ]]; then
    echo "Deleting the console-built resources..."
    agentcore_py delete "$scenario"
  fi
fi

# ---- build the finished version ------------------------------------------------------------

arn_for() {
  local value="$1" name="$2"
  [[ -n "$value" ]] || die "Couldn't find the $name API. Run \$WORKSHOP/scripts/check-setup.sh."
  printf '%s' "$value"
}

build_kopi_run() {
  local arn; arn="$(arn_for "${KOPI_API_ARN:-}" Kopi)"
  cd "$WORKSHOP"
  agentcore create --project-name KopiRun --no-agent
  cd KopiRun
  agentcore add gateway --name kopi-gw --authorizer-type AWS_IAM
  agentcore add gateway-target --type lambda-function-arn --name kopi-api --lambda-arn "$arn" \
    --tool-schema-file "$WORKSHOP/solutions/kopi-run/tools.json" --gateway kopi-gw
  agentcore add harness --name kopi_agent --model-provider bedrock \
    --system-prompt "$(cat "$WORKSHOP/kopi-run/system-prompt.md")" --max-iterations 20
  agentcore add tool --harness kopi_agent --type agentcore_gateway --name kopi --gateway kopi-gw
  agentcore deploy -y
  "$WORKSHOP/scripts/kopi.sh" reset
}

build_tally() {
  local arn gateway_arn; arn="$(arn_for "${TALLY_API_ARN:-}" Tally)"
  cd "$WORKSHOP"
  agentcore create --project-name TallyTools --no-agent
  cd TallyTools
  agentcore add gateway --name tally-gw --authorizer-type AWS_IAM
  agentcore add gateway-target --type lambda-function-arn --name tally-api --lambda-arn "$arn" \
    --tool-schema-file "$WORKSHOP/solutions/tally/tools.json" --gateway tally-gw
  agentcore deploy -y   # the policies need the Gateway's ARN, so it has to exist first

  gateway_arn="$("$WORKSHOP/scripts/gateway-arn.sh" tally-gw)"
  mkdir -p policies
  for f in allow-reads small-credits; do
    sed "s|\${GATEWAY_ARN}|$gateway_arn|g" "$WORKSHOP/tally/policies/$f.cedar" > "policies/$f.cedar"
  done
  agentcore add policy-engine --name tally_policies --attach-to-gateways tally-gw --attach-mode ENFORCE
  agentcore add policy --name allow_reads   --engine tally_policies --source ./policies/allow-reads.cedar
  agentcore add policy --name small_credits --engine tally_policies --source ./policies/small-credits.cedar
  agentcore deploy -y
}

build_intake() {
  local arn; arn="$(arn_for "${INTAKE_API_ARN:-}" Intake)"
  cd "$WORKSHOP"
  agentcore create --project-name IntakeQA --no-agent
  cd IntakeQA
  agentcore add gateway --name intake-gw --authorizer-type AWS_IAM
  agentcore add gateway-target --type lambda-function-arn --name intake-api --lambda-arn "$arn" \
    --tool-schema-file "$WORKSHOP/intake/tools.json" --gateway intake-gw
  agentcore add harness --name intake_agent --model-provider bedrock \
    --system-prompt "$(cat "$WORKSHOP/intake/system-prompt-v2.md")" --max-iterations 20
  agentcore add tool --harness intake_agent --type agentcore_gateway --name intake --gateway intake-gw
  agentcore add tool --harness intake_agent --type agentcore_code_interpreter --name calculator
  agentcore add evaluator --name AmountCheck --level TRACE --rating-scale pass-fail \
    --model global.anthropic.claude-sonnet-4-6 \
    --instructions "$(cat "$WORKSHOP/intake/evaluators/amount-check.txt")"
  agentcore add online-eval --name intake_live --runtime intake_agent \
    --evaluator AmountCheck Builtin.Correctness --sampling-rate 100 --enable-on-create
  agentcore deploy -y
}

echo
echo "Building the finished $scenario. This takes about five minutes."
case "$scenario" in
  kopi-run) build_kopi_run ;;
  tally)    build_tally ;;
  intake)   build_intake ;;
esac

echo
echo "Done in $(( ($(date +%s) - started) / 60 )) min. The finished project is in $project_dir."
case "$scenario" in
  kopi-run) echo "Carry on from 'Send it a rush of orders'." ;;
  tally)    echo "Carry on with: cd \$WORKSHOP/tally/agent && ./run.sh gateway --customer kettle" ;;
  intake)   echo "Carry on from the wrap-up page: ask the questions again with intake-ask.sh, then check the scores." ;;
esac
