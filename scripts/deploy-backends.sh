#!/usr/bin/env bash
# Deploys the three sample APIs into the current account and region. Only needed if
# you're running the workshop in your own account; workshop accounts already have them.
# Run this, don't source it: sourcing would run it in your own shell and could close it.
(return 0 2>/dev/null) && { echo "This is a script, so run it rather than sourcing it: ${WORKSHOP:-.}/scripts/deploy-backends.sh" >&2; return 1; }
set -euo pipefail
source "$(dirname "$0")/lib/common.sh"
need npx "Install Node.js 20 or later."

account="$(aws sts get-caller-identity --query Account --output text)"
echo "This deploys the stack AgentCoreWorkshopBackends (three Lambda functions, two DynamoDB tables)"
echo "into account $account, region $AWS_REGION."
confirm "Continue?" || die "Stopped."

cd "$WORKSHOP/backends"
npm install --no-audit --no-fund
npx cdk deploy AgentCoreWorkshopBackends --require-approval broadening
echo
echo "Done. Run: source \$WORKSHOP/scripts/env.sh"
