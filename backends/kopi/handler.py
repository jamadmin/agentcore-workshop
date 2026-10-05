"""Kopi Run backend: the API behind the Kopi Run agent's tools.

AgentCore Gateway calls this function with the tool's arguments as the event and
the tool name in the Lambda context. scripts/kopi.sh calls it directly with
{"tool": "<name>", ...arguments}.

place_order has a deliberate bug for the workshop: it adds the new quantity to an
existing line without checking the type. If the tool schema says quantity is a
string, "2" + "5" becomes "25".
"""
import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Key

TABLE_NAME = os.environ.get("RUN_TABLE", "agentcore-workshop-kopi-run")
SGT = timezone(timedelta(hours=8))
RUN_KEY = "RUN"

# Prices in SGD. A drink is one base plus any options, for example "kopi-o siew dai peng".
BASES = {
    "kopi": "1.40",
    "kopi-o": "1.20",
    "kopi-c": "1.60",
    "teh": "1.40",
    "teh-o": "1.20",
    "teh-c": "1.60",
    "yuan yang": "1.80",
    "milo": "2.00",
}
OPTIONS = {
    "kosong": ("0.00", "no sugar"),
    "siew dai": ("0.00", "less sweet"),
    "ka dai": ("0.00", "extra sweet"),
    "gao": ("0.20", "strong"),
    "po": ("0.00", "weak"),
    "peng": ("0.30", "iced"),
}

# Past orders from Kopi Run's own database, newest first.
HISTORY = {
    "marcus": [(1, "kopi-c kosong peng", 1), (4, "kopi-c kosong peng", 1), (6, "teh-c peng", 1)],
    "priya": [(1, "kopi-o siew dai", 2), (5, "kopi-o siew dai", 1)],
    "wei ling": [(2, "teh peng gao", 1), (3, "teh peng gao", 1)],
    "arjun": [(1, "milo peng", 1)],
    "siti": [(2, "teh-o kosong", 1)],
}

_table = None


def table():
    global _table
    if _table is None:
        _table = boto3.resource("dynamodb").Table(TABLE_NAME)
    return _table


def parse_drink(name):
    """Return (normalised name, unit price) or None if it isn't on the menu."""
    words = " ".join(str(name).lower().replace("_", " ").split())
    base = next((b for b in sorted(BASES, key=len, reverse=True) if words == b or words.startswith(b + " ")), None)
    if base is None:
        return None
    price = Decimal(BASES[base])
    rest = words[len(base):].strip()
    chosen = []
    while rest:
        opt = next((o for o in sorted(OPTIONS, key=len, reverse=True) if rest == o or rest.startswith(o + " ")), None)
        if opt is None:
            return None
        chosen.append(opt)
        price += Decimal(OPTIONS[opt][0])
        rest = rest[len(opt):].strip()
    return " ".join([base] + chosen), price


def money(value):
    return float(Decimal(value).quantize(Decimal("0.01")))


def plain(value):
    """DynamoDB returns Decimal for numbers; make it JSON-friendly."""
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    return value


def get_menu(_args):
    return {
        "kopitiam": "Block 88 Kopitiam",
        "currency": "SGD",
        "drinks": [{"name": b, "price": money(p)} for b, p in BASES.items()],
        "options": [{"name": o, "meaning": m, "extra": money(p)} for o, (p, m) in OPTIONS.items()],
        "how_to_order": "Combine one drink with any options, for example 'kopi-o siew dai peng'.",
    }


def place_order(args):
    person = str(args.get("person", "")).strip()
    if not person:
        return {"error": "person is required"}
    parsed = parse_drink(args.get("drink", ""))
    if parsed is None:
        return {"error": f"'{args.get('drink')}' is not on the menu. Use get_menu to see what is."}
    drink, _price = parsed
    quantity = args.get("quantity")
    key = {"pk": RUN_KEY, "sk": f"{person.lower()}#{drink}"}

    existing = table().get_item(Key=key).get("Item")
    if existing:
        # The workshop bug: no type check, so two strings are concatenated.
        quantity = existing["quantity"] + quantity

    table().put_item(Item={**key, "person": person.title(), "drink": drink, "quantity": quantity})
    return {"ok": True, "person": person.title(), "drink": drink, "quantity_on_run": plain(quantity)}


def get_order_history(args):
    person = str(args.get("person", "")).strip().lower()
    today = datetime.now(SGT).date()
    orders = [
        {"date": (today - timedelta(days=d)).isoformat(), "drink": drink, "quantity": q}
        for d, drink, q in HISTORY.get(person, [])
    ]
    return {"person": person.title(), "orders": orders} if orders else {"person": person.title(), "orders": [], "note": "No past orders for this person."}


def run_items():
    items, kwargs = [], {"KeyConditionExpression": Key("pk").eq(RUN_KEY)}
    while True:
        page = table().query(**kwargs)
        items += page.get("Items", [])
        if "LastEvaluatedKey" not in page:
            return items
        kwargs["ExclusiveStartKey"] = page["LastEvaluatedKey"]


def get_run(_args):
    lines, total, cups = [], Decimal("0"), 0
    for item in sorted(run_items(), key=lambda i: (i["person"], i["drink"])):
        parsed = parse_drink(item["drink"])
        unit = parsed[1] if parsed else Decimal("0")
        count = int(item["quantity"])  # "25" counts as 25 cups, which is how the bug shows up
        lines.append({
            "person": item["person"],
            "drink": item["drink"],
            "quantity": plain(item["quantity"]),
            "unit_price": money(unit),
            "line_total": money(unit * count),
        })
        total += unit * count
        cups += count
    return {"date": datetime.now(SGT).date().isoformat(), "kopitiam": "Block 88 Kopitiam", "lines": lines, "cups": cups, "total_sgd": money(total)}


def reset_run(_args):
    with table().batch_writer() as batch:
        for item in run_items():
            batch.delete_item(Key={"pk": item["pk"], "sk": item["sk"]})
    return {"ok": True, "message": "Today's run is empty."}


TOOLS = {
    "get_menu": get_menu,
    "place_order": place_order,
    "get_order_history": get_order_history,
    "get_run": get_run,
}
DIRECT_ONLY = {"reset_run": reset_run}  # for scripts/kopi.sh, never published to the agent


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
    except Exception as exc:  # the agent sees the error text, which is what we want in the workshop
        return {"error": f"{type(exc).__name__}: {exc}"}
