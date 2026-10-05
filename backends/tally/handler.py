"""Tally backend: the billing API behind the Tally support agent.

Called by AgentCore Gateway (tool name in the Lambda context), by the agent's own
boto3 tools in tally/agent/agent.py, and by scripts/tally.sh, all with
{"tool": "<name>", ...arguments} when called directly.

The story: Kettle & Co upgraded from Starter to Scale on 14 March 2026, but the
Starter subscription was never closed. March was billed on both plans, so the
invoice is $4,812.00 instead of $1,200.00. The pricing code is right; the data
is wrong. explain_invoice shows it. issue_credit has no limit at all.
"""
import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Key

TABLE_NAME = os.environ.get("CREDITS_TABLE", "agentcore-workshop-tally-credits")

CUSTOMERS = {
    "kettle": {"name": "Kettle & Co", "plan_now": "Scale", "billing_email": "accounts@kettle.example"},
    "lumio": {"name": "Lumio Labs", "plan_now": "Starter", "billing_email": "billing@lumio.example"},
}

PLANS = {
    "Starter": {"platform_fee": "310.00", "included_api_calls": 100_000, "overage_per_call": "0.008"},
    "Scale": {"platform_fee": "899.00", "included_api_calls": 1_000_000, "overage_per_call": "0.002"},
}

SUBSCRIPTIONS = {
    "kettle": [
        {"subscription_id": "sub_kettle_starter", "plan": "Starter", "started": "2025-06-01", "ended": None},
        {"subscription_id": "sub_kettle_scale", "plan": "Scale", "started": "2026-03-14", "ended": None},
    ],
    "lumio": [
        {"subscription_id": "sub_lumio_starter", "plan": "Starter", "started": "2025-11-01", "ended": None},
    ],
}

USAGE = {
    ("kettle", "2026-01"): [("2026-01-01", "2026-01-31", 205_000)],
    ("kettle", "2026-02"): [("2026-02-01", "2026-02-28", 211_000)],
    ("kettle", "2026-03"): [("2026-03-01", "2026-03-13", 168_500), ("2026-03-14", "2026-03-31", 429_000)],
    ("lumio", "2026-03"): [("2026-03-01", "2026-03-31", 84_000)],
}

# Explanations as the billing engine produced them. Totals tie out exactly.
EXPLANATIONS = {
    ("kettle", "INV-2026-01"): {
        "period": "2026-01-01 to 2026-01-31",
        "subscriptions_active_in_period": [
            {"subscription_id": "sub_kettle_starter", "plan": "Starter", "started": "2025-06-01", "ended": None, "active_days": 31, "days_in_period": 31},
        ],
        "platform_fees": [{"subscription_id": "sub_kettle_starter", "plan": "Starter", "monthly_fee": 310.00, "charged": 310.00}],
        "usage_rated": [
            {"subscription_id": "sub_kettle_starter", "plan": "Starter", "rated_period": "2026-01-01 to 2026-01-31", "api_calls_rated": 205_000,
             "included_api_calls": 100_000, "overage_calls": 105_000, "overage_per_call": 0.008, "charged": 840.00},
        ],
        "credits": [],
        "total": 1150.00,
    },
    ("kettle", "INV-2026-02"): {
        "period": "2026-02-01 to 2026-02-28",
        "subscriptions_active_in_period": [
            {"subscription_id": "sub_kettle_starter", "plan": "Starter", "started": "2025-06-01", "ended": None, "active_days": 28, "days_in_period": 28},
        ],
        "platform_fees": [{"subscription_id": "sub_kettle_starter", "plan": "Starter", "monthly_fee": 310.00, "charged": 310.00}],
        "usage_rated": [
            {"subscription_id": "sub_kettle_starter", "plan": "Starter", "rated_period": "2026-02-01 to 2026-02-28", "api_calls_rated": 211_000,
             "included_api_calls": 100_000, "overage_calls": 111_000, "overage_per_call": 0.008, "charged": 888.00},
        ],
        "credits": [],
        "total": 1198.00,
    },
    ("kettle", "INV-2026-03"): {
        "period": "2026-03-01 to 2026-03-31",
        "subscriptions_active_in_period": [
            {"subscription_id": "sub_kettle_starter", "plan": "Starter", "started": "2025-06-01", "ended": None, "active_days": 31, "days_in_period": 31},
            {"subscription_id": "sub_kettle_scale", "plan": "Scale", "started": "2026-03-14", "ended": None, "active_days": 18, "days_in_period": 31},
        ],
        "platform_fees": [
            {"subscription_id": "sub_kettle_starter", "plan": "Starter", "monthly_fee": 310.00, "charged": 310.00},
            {"subscription_id": "sub_kettle_scale", "plan": "Scale", "monthly_fee": 899.00, "charged": 522.00, "proration": "18 of 31 days"},
        ],
        "usage_rated": [
            {"subscription_id": "sub_kettle_starter", "plan": "Starter", "rated_period": "2026-03-01 to 2026-03-31", "api_calls_rated": 597_500,
             "included_api_calls": 100_000, "overage_calls": 497_500, "overage_per_call": 0.008, "charged": 3980.00},
            {"subscription_id": "sub_kettle_scale", "plan": "Scale", "rated_period": "2026-03-14 to 2026-03-31", "api_calls_rated": 429_000,
             "included_api_calls": 1_000_000, "overage_calls": 0, "overage_per_call": 0.002, "charged": 0.00},
        ],
        "credits": [],
        "total": 4812.00,
    },
    ("lumio", "INV-2026-03"): {
        "period": "2026-03-01 to 2026-03-31",
        "subscriptions_active_in_period": [
            {"subscription_id": "sub_lumio_starter", "plan": "Starter", "started": "2025-11-01", "ended": None, "active_days": 31, "days_in_period": 31},
        ],
        "platform_fees": [{"subscription_id": "sub_lumio_starter", "plan": "Starter", "monthly_fee": 310.00, "charged": 310.00}],
        "usage_rated": [
            {"subscription_id": "sub_lumio_starter", "plan": "Starter", "rated_period": "2026-03-01 to 2026-03-31", "api_calls_rated": 84_000,
             "included_api_calls": 100_000, "overage_calls": 0, "overage_per_call": 0.008, "charged": 0.00},
        ],
        "credits": [],
        "total": 310.00,
    },
}

_table = None


def table():
    global _table
    if _table is None:
        _table = boto3.resource("dynamodb").Table(TABLE_NAME)
    return _table


def norm_customer(args):
    cid = str(args.get("customer_id", "")).strip().lower()
    return cid if cid in CUSTOMERS else None


def norm_invoice(args):
    return str(args.get("invoice_id", "")).strip().upper()


def get_invoice(args):
    cid, inv = norm_customer(args), norm_invoice(args)
    exp = EXPLANATIONS.get((cid, inv))
    if not exp:
        return {"error": f"No invoice {inv} for customer {args.get('customer_id')}"}
    fees = sum(Decimal(str(f["charged"])) for f in exp["platform_fees"])
    usage = sum(Decimal(str(u["charged"])) for u in exp["usage_rated"])
    month = exp["period"][:7]
    # The invoice itself only shows totals per charge type. The detail is in explain_invoice.
    return {
        "customer_id": cid,
        "customer": CUSTOMERS[cid]["name"],
        "invoice_id": inv,
        "period": exp["period"],
        "currency": "USD",
        "status": "issued",
        "lines": [
            {"description": f"Platform fees, {month}", "amount": float(fees)},
            {"description": f"Usage charges, {month}", "amount": float(usage)},
        ],
        "total": exp["total"],
    }


def get_usage(args):
    cid = norm_customer(args)
    month = str(args.get("month", "")).strip()[:7]
    rows = USAGE.get((cid, month))
    if not rows:
        return {"error": f"No usage recorded for {args.get('customer_id')} in {month}"}
    return {
        "customer_id": cid,
        "month": month,
        "metric": "api_calls",
        "total_api_calls": sum(r[2] for r in rows),
        "by_period": [{"from": a, "to": b, "api_calls": n} for a, b, n in rows],
    }


def explain_invoice(args):
    cid, inv = norm_customer(args), norm_invoice(args)
    exp = EXPLANATIONS.get((cid, inv))
    if not exp:
        return {"error": f"No invoice {inv} for customer {args.get('customer_id')}"}
    return {"customer_id": cid, "invoice_id": inv, "currency": "USD", **exp,
            "pricing_rules": {"plans": PLANS, "proration": "A platform fee is prorated by active days when a subscription starts or ends in the period."}}


def issue_credit(args):
    cid = norm_customer(args)
    if not cid:
        return {"error": f"Unknown customer {args.get('customer_id')}"}
    try:
        amount = int(args.get("amount"))
    except (TypeError, ValueError):
        return {"error": "amount must be a whole number of US dollars"}
    if amount <= 0:
        return {"error": "amount must be positive"}
    # No upper limit. That's the problem the workshop solves with Policy.
    credit = {
        "customer_id": cid,
        "credit_id": f"CR-{datetime.now(timezone.utc):%Y%m%d%H%M%S}-{uuid.uuid4().hex[:4].upper()}",
        "amount": amount,
        "currency": "USD",
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
    return {"customer_id": cid, "credits": credits, "total_usd": sum(c["amount"] for c in credits)}


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
