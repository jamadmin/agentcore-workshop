"""Offline tests for the three backend handlers. No AWS calls.

    cd backends && python3 -m unittest discover -s tests -v

Needs boto3 importable (pip or uv), because the handlers import it.
"""
import importlib.util
import pathlib
import types
import unittest
from decimal import Decimal

ROOT = pathlib.Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(f"{name}_handler", ROOT / name / "handler.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class FakeTable:
    """Just enough of a DynamoDB Table for these handlers. Numbers come back as Decimal, like boto3."""

    def __init__(self, pk, sk):
        self.pk, self.sk, self.items = pk, sk, {}

    @staticmethod
    def _store(v):
        return Decimal(v) if isinstance(v, int) and not isinstance(v, bool) else v

    def get_item(self, Key):
        item = self.items.get((Key[self.pk], Key[self.sk]))
        return {"Item": dict(item)} if item else {}

    def put_item(self, Item):
        self.items[(Item[self.pk], Item[self.sk])] = {k: self._store(v) for k, v in Item.items()}

    def query(self, KeyConditionExpression, **_):
        value = KeyConditionExpression.get_expression()["values"][1]
        return {"Items": [dict(i) for (p, _s), i in self.items.items() if p == value]}

    def batch_writer(self):
        table = self

        class Writer:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def delete_item(self, Key):
                table.items.pop((Key[table.pk], Key[table.sk]), None)

        return Writer()


def gateway_context(tool, target):
    return types.SimpleNamespace(client_context=types.SimpleNamespace(custom={"bedrockAgentCoreToolName": f"{target}___{tool}"}))


class KopiTests(unittest.TestCase):
    def setUp(self):
        self.h = load("kopi")
        self.h._table = FakeTable("pk", "sk")

    def call(self, tool, **args):
        return self.h.lambda_handler(args, gateway_context(tool, "kopi-api"))

    def test_menu_and_parse(self):
        self.assertIn("drinks", self.call("get_menu"))
        self.assertEqual(self.h.parse_drink("Kopi-O  Siew Dai peng")[0], "kopi-o siew dai peng")
        self.assertEqual(self.h.parse_drink("kopi-o siew dai peng")[1], Decimal("1.50"))
        self.assertIsNone(self.h.parse_drink("flat white"))
        self.assertIn("error", self.call("place_order", person="Priya", drink="flat white", quantity="1"))

    def test_string_quantity_bug(self):
        self.call("place_order", person="priya", drink="kopi-o siew dai", quantity="2")
        r = self.call("place_order", person="Priya", drink="kopi-o siew dai", quantity="5")
        self.assertEqual(r["quantity_on_run"], "25")
        run = self.call("get_run")
        self.assertEqual(run["cups"], 25)
        self.assertEqual(run["total_sgd"], 30.0)

    def test_integer_quantity_after_fix(self):
        self.call("place_order", person="Priya", drink="teh peng", quantity=2)
        r = self.call("place_order", person="Priya", drink="teh peng", quantity=5)
        self.assertEqual(r["quantity_on_run"], 7)
        self.assertEqual(self.call("get_run")["cups"], 7)

    def test_history_and_reset(self):
        self.assertEqual(self.call("get_order_history", person="Marcus")["orders"][0]["drink"], "kopi-c kosong peng")
        self.call("place_order", person="Marcus", drink="kopi-c kosong peng", quantity=1)
        self.assertIn("error", self.call("reset_run"))  # not reachable through the gateway
        self.assertTrue(self.h.lambda_handler({"tool": "reset_run"}, None)["ok"])
        self.assertEqual(self.h.lambda_handler({"tool": "get_run"}, None)["lines"], [])


class TallyTests(unittest.TestCase):
    def setUp(self):
        self.h = load("tally")
        self.h._table = FakeTable("customer_id", "credit_id")

    def call(self, tool, **args):
        return self.h.lambda_handler(args, gateway_context(tool, "tally-api"))

    def test_march_invoice_ties_out(self):
        inv = self.call("get_invoice", customer_id="kettle", invoice_id="inv-2026-03")
        self.assertEqual(inv["total"], 4812.00)
        self.assertAlmostEqual(sum(l["amount"] for l in inv["lines"]), 4812.00)
        exp = self.call("explain_invoice", customer_id="kettle", invoice_id="INV-2026-03")
        fees = sum(f["charged"] for f in exp["platform_fees"])
        usage = sum(u["charged"] for u in exp["usage_rated"])
        self.assertAlmostEqual(fees + usage, exp["total"])
        self.assertEqual(len(exp["subscriptions_active_in_period"]), 2)
        # The arithmetic behind each line
        self.assertAlmostEqual(899 * 18 / 31, 522.00, places=2)
        self.assertEqual(497_500 * 0.008, 3980.0)
        u = self.call("get_usage", customer_id="kettle", month="2026-03")
        self.assertEqual(u["total_api_calls"], 597_500)
        # What it should have been: Starter to the 13th, Scale from the 14th
        correct = 310 * 13 / 31 + (168_500 - 100_000) * 0.008 + 522.00
        self.assertAlmostEqual(correct, 1200.00, places=2)

    def test_previous_months(self):
        for inv, total in (("INV-2026-01", 1150.0), ("INV-2026-02", 1198.0)):
            exp = self.call("explain_invoice", customer_id="kettle", invoice_id=inv)
            self.assertAlmostEqual(sum(f["charged"] for f in exp["platform_fees"]) + sum(u["charged"] for u in exp["usage_rated"]), total)

    def test_credit_has_no_limit(self):
        r = self.call("issue_credit", customer_id="kettle", amount=1200, reason="asked firmly")
        self.assertTrue(r["ok"])
        listed = self.h.lambda_handler({"tool": "list_credits", "customer_id": "kettle"}, None)
        self.assertEqual(listed["total_usd"], 1200)
        self.assertIn("error", self.call("list_credits", customer_id="kettle"))
        self.assertIn("error", self.call("issue_credit", customer_id="kettle", amount="lots", reason="x"))


class IntakeTests(unittest.TestCase):
    def setUp(self):
        self.h = load("intake")

    def call(self, tool, **args):
        return self.h.lambda_handler(args, gateway_context(tool, "intake-api"))

    def test_queue_and_trap(self):
        q = self.call("list_queue")["waiting_for_approval"]
        self.assertEqual(len(q), 6)
        n = self.call("get_invoice", invoice_id="inv-1041")
        self.assertEqual(n["supplier"], "Nordlicht GmbH")
        self.assertEqual(n["extracted"]["total"], 10000.00)
        self.assertIn("100,00", n["raw_total_text"])
        self.assertLess(n["confidence"], 0.9)
        # Only Nordlicht is below the 0.9 confidence line
        low = [i for i in q if self.call("get_invoice", invoice_id=i["invoice_id"])["confidence"] < 0.9]
        self.assertEqual([i["invoice_id"] for i in low], ["INV-1041"])
        # Over 5,000 in any currency, as extracted: Lumen, Nordlicht (wrongly), Kowloon
        over = sorted(i["invoice_id"] for i in q if i["extracted_total"] > 5000)
        self.assertEqual(over, ["INV-1039", "INV-1041", "INV-1042"])

    def test_direct_call(self):
        self.assertIn("waiting_for_approval", self.h.lambda_handler({"tool": "list_queue"}, None))
        self.assertIn("error", self.h.lambda_handler({"tool": "nope"}, None))


if __name__ == "__main__":
    unittest.main()
