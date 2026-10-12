#!/usr/bin/env bash
# Makes the tool-list change a step asks for, then shows exactly what changed.
#   edit-tools.sh kopi-quantity           Kopi Run: quantity becomes an integer from 1 to 20
#   edit-tools.sh tally-explain-invoice   Tally: adds the explain_invoice tool
# You can make the same change by hand in the code editor instead; this is the copy-paste route.
# Run this, don't source it: sourcing would run it in your own shell and could close it.
(return 0 2>/dev/null) && { echo "This is a script, so run it rather than sourcing it: ${WORKSHOP:-.}/scripts/edit-tools.sh" >&2; return 1; }
set -euo pipefail
source "$(dirname "$0")/lib/common.sh"

case "${1:-}" in
  kopi-quantity)         file="$WORKSHOP/kopi-run/tools.json" ;;
  tally-explain-invoice) file="$WORKSHOP/tally/tools.json" ;;
  *) die "Usage: edit-tools.sh kopi-quantity|tally-explain-invoice" ;;
esac

python3 - "$1" "$file" "$WORKSHOP/solutions/tally/tools.json" <<'PY'
import json, sys
change, path, tally_solution = sys.argv[1], sys.argv[2], sys.argv[3]
tools = json.load(open(path, encoding="utf-8"))
if change == "kopi-quantity":
    for t in tools:
        if t["name"] == "place_order":
            t["inputSchema"]["properties"]["quantity"] = {
                "type": "integer", "minimum": 1, "maximum": 20, "description": "How many cups"}
else:
    if not any(t["name"] == "explain_invoice" for t in tools):
        explain = next(t for t in json.load(open(tally_solution, encoding="utf-8")) if t["name"] == "explain_invoice")
        tools.append(explain)
with open(path, "w", encoding="utf-8") as fh:
    json.dump(tools, fh, indent=2)
    fh.write("\n")
PY

echo "Changed ${file#"$WORKSHOP"/}:"
if git -C "$WORKSHOP" rev-parse >/dev/null 2>&1; then
  git -C "$WORKSHOP" --no-pager diff --no-color -- "$file" | sed -n '5,$p'
fi
echo "Now deploy so the Gateway gets the new tool list."
