# Workshop environment. Load it into your terminal with:
#
#   source ~/agentcore-workshop/scripts/env.sh
#
# It lasts for that terminal only and changes nothing on disk. The workshop scripts
# load it themselves, so they work in a fresh terminal without it.

_ws_here="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
export WORKSHOP="$(cd "$_ws_here/.." && pwd)"
export AWS_REGION="${WORKSHOP_REGION:-us-west-2}"
export AWS_DEFAULT_REGION="$AWS_REGION"
export AWS_PAGER=""

_ws_arn() {
  aws lambda get-function --function-name "$1" --query 'Configuration.FunctionArn' --output text 2>/dev/null || true
}

# The three sample APIs, deployed in your account before the workshop.
export KOPI_API_ARN="$(_ws_arn agentcore-workshop-kopi-api)"
export TALLY_API_ARN="$(_ws_arn agentcore-workshop-tally-api)"
export INTAKE_API_ARN="$(_ws_arn agentcore-workshop-intake-api)"

# A fresh session ID (AgentCore needs at least 33 characters; a UUID has 36).
newsession() { python3 -c 'import uuid; print(uuid.uuid4())'; }
[ -n "${BASH_VERSION:-}" ] && export -f newsession

if [ -z "$KOPI_API_ARN" ] || [ -z "$TALLY_API_ARN" ] || [ -z "$INTAKE_API_ARN" ]; then
  echo "env.sh: couldn't find all three sample APIs in $AWS_REGION. Run \$WORKSHOP/scripts/check-setup.sh for details." >&2
fi
unset _ws_here
unset -f _ws_arn
