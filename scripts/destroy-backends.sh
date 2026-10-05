#!/usr/bin/env bash
# Removes the three sample APIs, if you deployed them yourself with deploy-backends.sh.
# Run this, don't source it: sourcing would run it in your own shell and could close it.
(return 0 2>/dev/null) && { echo "This is a script, so run it rather than sourcing it: ${WORKSHOP:-.}/scripts/destroy-backends.sh" >&2; return 1; }
set -euo pipefail
source "$(dirname "$0")/lib/common.sh"

stack=AgentCoreWorkshopBackends
if ! aws cloudformation describe-stacks --stack-name "$stack" >/dev/null 2>&1; then
  echo "There's no $stack stack in $AWS_REGION, so there's nothing to remove."
  echo "(In a workshop account the APIs belong to the event and are removed with it.)"
  exit 0
fi
confirm "Delete $stack (the three sample APIs and their tables) from $AWS_REGION?" || die "Stopped."
aws cloudformation delete-stack --stack-name "$stack"
echo "Deleting..."
aws cloudformation wait stack-delete-complete --stack-name "$stack"
echo "Removed."
