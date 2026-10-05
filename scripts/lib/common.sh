# Shared by the workshop scripts. Not meant to be run on its own.
# Loads env.sh if this terminal hasn't, so every script works in a fresh terminal.

_lib_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -z "${WORKSHOP:-}" || -z "${AWS_REGION:-}" ]]; then
  # shellcheck disable=SC1091
  source "$_lib_dir/../env.sh" 2>/dev/null
fi
export AWS_PAGER=""

die() { echo "$*" >&2; exit 1; }

need() { command -v "$1" >/dev/null 2>&1 || die "$1 isn't installed in this environment. $2"; }

confirm() {
  local reply
  read -r -p "$1 [y/N] " reply
  [[ "$reply" == y || "$reply" == Y || "$reply" == yes ]]
}

# AgentCore helpers in Python. uv keeps a recent boto3 for them, separate from the system Python.
agentcore_py() {
  need uv "See the setup page."
  uv run --quiet --script "$WORKSHOP/scripts/lib/agentcore.py" "$@"
}

# Call one of the sample APIs directly: invoke_backend <kopi|tally|intake> '<json payload>'
invoke_backend() {
  local out status
  out="$(mktemp)"
  if ! status="$(aws lambda invoke --function-name "agentcore-workshop-$1-api" \
      --cli-binary-format raw-in-base64-out --payload "$2" "$out" \
      --query 'FunctionError' --output text 2>&1)"; then
    rm -f "$out"
    die "Couldn't call agentcore-workshop-$1-api: $status"
  fi
  if [[ "$status" != "None" && -n "$status" ]]; then
    cat "$out" >&2; rm -f "$out"
    die "agentcore-workshop-$1-api returned an error."
  fi
  cat "$out"
  rm -f "$out"
}
