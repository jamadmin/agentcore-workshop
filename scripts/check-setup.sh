#!/usr/bin/env bash
# Checks everything the workshop needs. Each line says PASS, FAIL or PENDING, with a hint.
# Run this, don't source it: sourcing would run it in your own shell and could close it.
(return 0 2>/dev/null) && { echo "This is a script, so run it rather than sourcing it: ${WORKSHOP:-.}/scripts/check-setup.sh" >&2; return 1; }
set -uo pipefail
source "$(dirname "$0")/lib/common.sh"

MODEL_ID="${WORKSHOP_MODEL_ID:-global.anthropic.claude-sonnet-4-6}"
fails=0
line() {  # line <PASS|FAIL|PENDING> <what> <detail>
  printf '%-8s %-22s %s\n' "$1" "$2" "$3"
  [[ "$1" == FAIL ]] && fails=$((fails + 1))
  return 0
}

echo "Workshop setup check ($AWS_REGION)"
echo

# Tools
for tool in aws node uv agentcore python3; do
  if command -v "$tool" >/dev/null 2>&1; then
    case "$tool" in
      node)
        major="$(node -p 'process.versions.node.split(".")[0]')"
        if [[ "$major" -ge 20 ]]; then line PASS "Node.js" "$(node -v)"; else line FAIL "Node.js" "$(node -v); the AgentCore CLI needs 20 or later"; fi ;;
      agentcore) line PASS "AgentCore CLI" "$(agentcore --version 2>/dev/null | head -n 1)" ;;
      *) line PASS "$tool" "$("$tool" --version 2>&1 | head -n 1)" ;;
    esac
  else
    hint="ask a facilitator"
    [[ "$tool" == agentcore ]] && hint="sudo npm install -g @aws/agentcore"
    line FAIL "$tool" "not found: $hint"
  fi
done

# Credentials and region
if ident="$(aws sts get-caller-identity --query Account --output text 2>&1)"; then
  line PASS "Credentials" "account $ident"
else
  line FAIL "Credentials" "no working AWS credentials. Open a new terminal from the code editor"
fi
if [[ "$AWS_REGION" == "${WORKSHOP_REGION:-us-east-1}" ]]; then
  line PASS "Region" "$AWS_REGION"
else
  line FAIL "Region" "$AWS_REGION; the workshop runs in ${WORKSHOP_REGION:-us-east-1}"
fi

# One tiny model call
if out="$(aws bedrock-runtime converse --model-id "$MODEL_ID" \
    --messages '[{"role":"user","content":[{"text":"Reply with the single word OK."}]}]' \
    --inference-config maxTokens=10 --query 'output.message.content[0].text' --output text 2>&1)"; then
  line PASS "Bedrock model" "$MODEL_ID replied"
elif [[ "$out" == *AccessDenied* ]]; then
  line FAIL "Bedrock model" "AccessDenied: model access isn't enabled. Put your hand up"
else
  line FAIL "Bedrock model" "$(echo "$out" | tail -n 1 | cut -c1-90)"
fi

# The three sample APIs, called directly once each
check_api() {  # check_api <name> <label> <payload> <field that must be in the reply>
  local out tmp fn_error
  tmp="$(mktemp)"
  if fn_error="$(aws lambda invoke --function-name "agentcore-workshop-$1-api" --cli-binary-format raw-in-base64-out \
      --payload "$3" "$tmp" --query 'FunctionError' --output text 2>&1)" \
      && [[ "$fn_error" == None ]] && grep -q "\"$4\"" "$tmp"; then
    line PASS "$2" "agentcore-workshop-$1-api"
  else
    line FAIL "$2" "agentcore-workshop-$1-api didn't answer. Re-run env.sh, or ask a facilitator"
  fi
  rm -f "$tmp"
}
check_api kopi   "Kopi Run API" '{"tool":"get_menu"}' drinks
check_api tally  "Tally API"    '{"tool":"get_invoice","customer_id":"kettle","invoice_id":"INV-2026-03"}' total
check_api intake "Intake API"   '{"tool":"list_queue"}' waiting_for_approval

# CloudWatch Transaction Search
if ts="$(aws xray get-trace-segment-destination --query '[Destination,Status]' --output text 2>&1)"; then
  dest="$(echo "$ts" | awk '{print $1}')"; state="$(echo "$ts" | awk '{print $2}')"
  if [[ "$dest" == CloudWatchLogs && "$state" == ACTIVE ]]; then
    line PASS "Transaction Search" "on"
  elif [[ "$dest" == CloudWatchLogs ]]; then
    line PENDING "Transaction Search" "turning on ($state). Carry on; it takes up to ten minutes"
  else
    line FAIL "Transaction Search" "off. Run \$WORKSHOP/scripts/enable-transaction-search.sh"
  fi
else
  line FAIL "Transaction Search" "couldn't check: $(echo "$ts" | tail -n 1 | cut -c1-70)"
fi

echo
if [[ "$fails" -eq 0 ]]; then
  echo "All good."
else
  echo "$fails check(s) failed. See the hints above, or the Stuck? box on the setup page."
  exit 1
fi
