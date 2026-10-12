"""Formats backend replies for kopi.sh and tally.sh. Standard library only.

    ... | python3 show.py run
    ... | python3 show.py credits
    ... | python3 show.py inventory
"""
import json
import sys


def show_run(run):
    print(f"Today's run to {run.get('kopitiam', 'the kopitiam')} ({run.get('date', '')})")
    lines = run.get("lines", [])
    if not lines:
        print("  (empty)")
    for line in lines:
        qty = str(line["quantity"])
        print(f"  {line['person']:<10} {qty:>4} x {line['drink']:<24} S${line['line_total']:>7.2f}")
    print(f"  {run.get('cups', 0)} cups, total S${run.get('total_sgd', 0):.2f}")


def show_credits(reply):
    credits = reply.get("credits", [])
    print(f"Credits for {reply.get('customer_id')}:")
    if not credits:
        print("  (none)")
    for c in credits:
        print(f"  {c['issued_at']}  S${c['amount']:>6,}  {c['reason'][:60]}")
    print(f"  Total: S${reply.get('total_sgd', 0):,}")


def show_inventory(items):
    for item in items:
        print(f"  - {item['type']}: {item['name']}")


if __name__ == "__main__":
    data = json.load(sys.stdin)
    if isinstance(data, dict) and "error" in data:
        sys.exit(f"Backend error: {data['error']}")
    {"run": show_run, "credits": show_credits, "inventory": show_inventory}[sys.argv[1]](data)
