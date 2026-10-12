"""Intake backend: the approval queue behind the Intake finance agent.

Read-only, with synthetic data, all in Singapore dollars. The Lucky Star Print
invoice is the trap: the paper says S$1,280.00, but the scanner missed the
decimal point and recorded 128000.00, with a confidence of 0.62.
"""

QUEUE = ["INV-1038", "INV-1039", "INV-1040", "INV-1041", "INV-1042", "INV-1043"]

INVOICES = {
    "INV-1038": {
        "supplier": "Kallang Office Supplies Pte Ltd", "received": "2026-10-12",
        "extracted": {"supplier": "Kallang Office Supplies Pte Ltd", "currency": "SGD", "total": 1284.50, "invoice_date": "2026-10-09"},
        "raw_total_text": "Total due: S$1,284.50", "confidence": 0.98,
        "previous_totals_from_supplier": [1190.00, 1310.25, 1255.80],
    },
    "INV-1039": {
        "supplier": "Lion City Cloud Pte Ltd", "received": "2026-10-13",
        "extracted": {"supplier": "Lion City Cloud Pte Ltd", "currency": "SGD", "total": 6120.00, "invoice_date": "2026-10-01"},
        "raw_total_text": "Amount due: S$6,120.00", "confidence": 0.99,
        "previous_totals_from_supplier": [5980.00, 6045.00, 6120.00],
    },
    "INV-1040": {
        "supplier": "Sunrise Catering Pte Ltd", "received": "2026-10-14",
        "extracted": {"supplier": "Sunrise Catering Pte Ltd", "currency": "SGD", "total": 2450.00, "invoice_date": "2026-10-10"},
        "raw_total_text": "Total: S$2,450.00", "confidence": 0.95,
        "previous_totals_from_supplier": [2450.00, 2450.00],
    },
    "INV-1041": {
        "supplier": "Lucky Star Print Pte Ltd", "received": "2026-10-15",
        "extracted": {"supplier": "Lucky Star Print Pte Ltd", "currency": "SGD", "total": 128000.00, "invoice_date": "2026-10-14"},
        "raw_total_text": "Total: S$1,280.00", "confidence": 0.62,
        "previous_totals_from_supplier": [1190.00, 1310.00, 1255.00],
    },
    "INV-1042": {
        "supplier": "Marina Bay Logistics Pte Ltd", "received": "2026-10-15",
        "extracted": {"supplier": "Marina Bay Logistics Pte Ltd", "currency": "SGD", "total": 8900.00, "invoice_date": "2026-10-13"},
        "raw_total_text": "TOTAL S$8,900.00", "confidence": 0.97,
        "previous_totals_from_supplier": [8450.00, 9120.00],
    },
    "INV-1043": {
        "supplier": "Tampines Cleaning Services", "received": "2026-10-16",
        "extracted": {"supplier": "Tampines Cleaning Services", "currency": "SGD", "total": 1234.56, "invoice_date": "2026-10-15"},
        "raw_total_text": "Total payable: S$1,234.56", "confidence": 0.95,
        "previous_totals_from_supplier": [1180.00, 1302.40],
    },
    # Already approved, so not in the queue, but get_invoice can still find it.
    "INV-0987": {
        "supplier": "Lucky Star Print Pte Ltd", "received": "2026-09-16", "status": "approved",
        "extracted": {"supplier": "Lucky Star Print Pte Ltd", "currency": "SGD", "total": 1255.00, "invoice_date": "2026-09-14"},
        "raw_total_text": "Total: S$1,255.00", "confidence": 0.94,
        "previous_totals_from_supplier": [1190.00, 1310.00],
    },
}


def list_queue(_args):
    return {
        "waiting_for_approval": [
            {
                "invoice_id": i,
                "supplier": INVOICES[i]["supplier"],
                "currency": INVOICES[i]["extracted"]["currency"],
                "extracted_total": INVOICES[i]["extracted"]["total"],
                "received": INVOICES[i]["received"],
            }
            for i in QUEUE
        ]
    }


def get_invoice(args):
    inv = str(args.get("invoice_id", "")).strip().upper()
    data = INVOICES.get(inv)
    if not data:
        return {"error": f"No invoice {inv}"}
    return {"invoice_id": inv, "status": data.get("status", "waiting_for_approval"), **{k: v for k, v in data.items() if k != "status"}}


TOOLS = {"list_queue": list_queue, "get_invoice": get_invoice}


def tool_name(event, context):
    custom = getattr(getattr(context, "client_context", None), "custom", None) or {}
    gateway_name = custom.get("bedrockAgentCoreToolName")
    if gateway_name:
        return gateway_name.split("___")[-1]
    return str(event.get("tool", ""))


def lambda_handler(event, context):
    event = event or {}
    name = tool_name(event, context)
    fn = TOOLS.get(name)
    if fn is None:
        return {"error": f"Unknown tool '{name}'"}
    try:
        return fn({k: v for k, v in event.items() if k != "tool"})
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}
