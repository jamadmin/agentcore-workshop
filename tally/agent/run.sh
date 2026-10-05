#!/usr/bin/env bash
# Starts the Tally agent in this terminal, with tracing to CloudWatch switched on.
#   ./run.sh before  --customer kettle    the original agent, tools call the backend directly
#   ./run.sh gateway --customer kettle    the same agent, tools from the tally-gw Gateway
# Run this, don't source it: sourcing would run it in your own shell and could close it.
(return 0 2>/dev/null) && { echo "This is a script, so run it rather than sourcing it: ./run.sh" >&2; return 1; }
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
source "$here/../../scripts/lib/common.sh"
need uv "See the setup page."

mode="${1:-}"; shift || true
case "$mode" in
  before)  script=agent.py ;;
  gateway)
    script=agent_gateway.py
    echo "Looking up the tally-gw Gateway..."
    TALLY_GATEWAY_URL="$("$WORKSHOP/scripts/gateway-url.sh" tally-gw)" \
      || die "Couldn't find a ready Gateway called tally-gw. If you just created it, wait a minute and try again."
    export TALLY_GATEWAY_URL ;;
  *) die "Usage: ./run.sh before|gateway --customer <id>" ;;
esac

# Telemetry settings for ADOT. They contain no credentials.
set -a
# shellcheck disable=SC1091
source "$here/otel.env"
set +a
log_group=/aws/bedrock-agentcore/runtimes/tally-billing-agent
aws logs create-log-group --log-group-name "$log_group" >/dev/null 2>&1 || true
aws logs create-log-stream --log-group-name "$log_group" --log-stream-name runtime-logs >/dev/null 2>&1 || true

cd "$here"
uv sync --quiet
exec uv run --quiet opentelemetry-instrument python "$script" "$@"
