"""Tally backend: the billing API behind the Tally support agent.

Called by AgentCore Gateway (tool name in the Lambda context), by the agent's own
boto3 tools in tally/agent/agent.py, and by scripts/tally.sh, all with
{"tool": "<name>", ...arguments} when called directly.

The story: Kettle & Co moved from the Basic plan (S$300 a month) to the Pro plan
(S$900 a month) on 1 March 2026, but nobody cancelled Basic. March was billed for
both: S$1,200 instead of S$900. explain_invoice shows it. issue_credit has no limit.
All amounts are whole Singapore dollars.
"""
import os
import uuid
from datetime import datetime, timezone

import boto3
from boto3.dynamodb.conditions import Key

TABLE_NAME = os.environ.get("CREDITS_TABLE", "agentcore-workshop-tally-credits")

CUSTOMERS = {
    "kettle": {"name": "Kettle & Co", "billing_email": "accounts@kettle.example"},
}

PLANS = {"Basic": 300, "Pro": 900}  # S$ per month

# Plans billed in each month, as the billing system recorded them.
BILLED = {
    ("kettle", "2026-01"): [("Basic", "2025-06-01", None)],
    ("kettle", "2026-02"): [("Basic", "2025-06-01", None)],
    # Upgraded to Pro on 1 March, but Basic was never cancelled.
    ("kettle", "2026-03"): [("Basic", "2025-06-01", None), ("Pro", "2026-03-01", None)],
}

# How many people at the customer used the software. Not part of the bill.
USERS = {("kettle", "2026-01"): 9, ("kettle", "2026-02"): 11, ("kettle", "2026-03"): 12}

_table = None


def table():
    global _table
    if _table is None:
        _table = boto3.resource("dynamodb").Table(TABLE_NAME)
    return _table


def norm_customer(args):
    cid = str(args.get("customer_id", "")).strip().lower()
    return cid if cid in CUSTOMERS else None


def month_of(args):
    """INV-2026-03 -> 2026-03."""
    inv = str(args.get("invoice_id", "")).strip().upper()
    return inv, (inv[4:] if inv.startswith("INV-") else "")


def get_invoice(args):
    cid, (inv, month) = norm_customer(args), month_of(args)
    plans = BILLED.get((cid, month))
    if not plans:
        return {"error": f"No invoice {inv} for customer {args.get('customer_id')}"}
    total = sum(PLANS[p] for p, _, _ in plans)
    # The invoice itself shows one line. The breakdown is in explain_invoice.
    return {
        "customer_id": cid,
        "customer": CUSTOMERS[cid]["name"],
        "invoice_id": inv,
        "month": month,
        "currency": "SGD",
        "lines": [{"description": f"Subscription fees, {month}", "amount": total}],
        "total": total,
    }


def get_usage(args):
    cid = norm_customer(args)
    month = str(args.get("month", "")).strip()[:7]
    users = USERS.get((cid, month))
    if users is None:
        return {"error": f"No usage recorded for {args.get('customer_id')} in {month}"}
    return {"customer_id": cid, "month": month, "active_users": users,
            "note": "Usage doesn't change the bill. Plans are a flat monthly fee."}


def explain_invoice(args):
    cid, (inv, month) = norm_customer(args), month_of(args)
    plans = BILLED.get((cid, month))
    if not plans:
        return {"error": f"No invoice {inv} for customer {args.get('customer_id')}"}
    return {
        "customer_id": cid,
        "invoice_id": inv,
        "month": month,
        "currency": "SGD",
        "plans_billed": [
            {"plan": p, "monthly_fee": PLANS[p], "started": start, "cancelled": end}
            for p, start, end in plans
        ],
        "total": sum(PLANS[p] for p, _, _ in plans),
        "plan_prices": PLANS,
    }


def issue_credit(args):
    cid = norm_customer(args)
    if not cid:
        return {"error": f"Unknown customer {args.get('customer_id')}"}
    try:
        amount = int(args.get("amount"))
    except (TypeError, ValueError):
        return {"error": "amount must be a whole number of Singapore dollars"}
    if amount <= 0:
        return {"error": "amount must be positive"}
    # No upper limit. That's the problem the workshop solves with Policy.
    credit = {
        "customer_id": cid,
        "credit_id": f"CR-{datetime.now(timezone.utc):%Y%m%d%H%M%S}-{uuid.uuid4().hex[:4].upper()}",
        "amount": amount,
        "currency": "SGD",
        "reason": str(args.get("reason", ""))[:500],
        "issued_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "applies_to": "next invoice",
    }
    table().put_item(Item=credit)
    return {"ok": True, **credit}


def list_credits(args):
    cid = str(args.get("customer_id", "")).strip().lower()
    items = table().query(KeyConditionExpression=Key("customer_id").eq(cid)).get("Items", [])
    credits = [{**i, "amount": int(i["amount"])} for i in sorted(items, key=lambda i: i["issued_at"])]
    return {"customer_id": cid, "credits": credits, "total_sgd": sum(c["amount"] for c in credits)}


def reset_credits(args):
    cid = str(args.get("customer_id", "")).strip().lower()
    items = table().query(KeyConditionExpression=Key("customer_id").eq(cid)).get("Items", [])
    with table().batch_writer() as batch:
        for i in items:
            batch.delete_item(Key={"customer_id": i["customer_id"], "credit_id": i["credit_id"]})
    return {"ok": True, "deleted": len(items)}


TOOLS = {
    "get_invoice": get_invoice,
    "get_usage": get_usage,
    "issue_credit": issue_credit,
    "explain_invoice": explain_invoice,
}
DIRECT_ONLY = {"list_credits": list_credits, "reset_credits": reset_credits}


def tool_name(event, context):
    custom = getattr(getattr(context, "client_context", None), "custom", None) or {}
    gateway_name = custom.get("bedrockAgentCoreToolName")
    if gateway_name:
        return gateway_name.split("___")[-1], False
    return str(event.get("tool", "")), True


def lambda_handler(event, context):
    event = event or {}
    name, direct = tool_name(event, context)
    args = {k: v for k, v in event.items() if k != "tool"}
    fn = TOOLS.get(name) or (DIRECT_ONLY.get(name) if direct else None)
    if fn is None:
        return {"error": f"Unknown tool '{name}'"}
    try:
        return fn(args)
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}
