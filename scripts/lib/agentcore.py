# /// script
# requires-python = ">=3.10"
# dependencies = ["boto3>=1.43"]
# ///
"""AgentCore helpers for the workshop scripts. Run through uv so boto3 is new enough
to know about harnesses:

    uv run --quiet --script scripts/lib/agentcore.py <command> ...

Everything finds resources by name through the AWS APIs, never through a CLI
project, so it works the same for console-built and CLI-built resources.
Names are matched exactly first. The AgentCore CLI prefixes some names with the
project name (a harness called kopi_agent in project KopiRun is deployed as
KopiRun_kopi_agent), so a name that ends in _<name> or -<name> also matches.

Commands:
    harness-arn <name>
    gateway-url <name>
    gateway-arn <name>
    burst <harness> <n>
    ask <harness> <questions-file>
    inventory <scenario>               list same-named resources as JSON
    delete <scenario>                  delete them (console-built leftovers)
"""
import json
import os
import statistics
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

REGION = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "ap-southeast-1"

# What catch-up.sh may replace, per scenario.
SCENARIOS = {
    "kopi-run": {"harnesses": ["kopi_agent"], "gateways": ["kopi-gw"]},
    "tally": {"gateways": ["tally-gw"], "policy_engines": ["tally_policies"]},
    "intake": {
        "online_evals": ["intake_live"],
        "evaluators": ["AmountCheck"],
        "harnesses": ["intake_agent"],
        "gateways": ["intake-gw"],
    },
}


def fail(msg, code=1):
    print(msg, file=sys.stderr)
    sys.exit(code)


def control():
    return boto3.client("bedrock-agentcore-control", region_name=REGION)


def data_plane(pool=10):
    cfg = Config(max_pool_connections=pool, read_timeout=300, connect_timeout=10, retries={"mode": "standard", "max_attempts": 4})
    return boto3.client("bedrock-agentcore", region_name=REGION, config=cfg)


def paged(method, key, **kwargs):
    out, token = [], None
    while True:
        page = method(**kwargs, **({"nextToken": token} if token else {}))
        out += page.get(key, [])
        token = page.get("nextToken")
        if not token:
            return out


def matches(name, wanted):
    if not name:
        return False
    n, w = name.lower(), wanted.lower()
    variants = {w, w.replace("-", "_"), w.replace("_", "-")}
    return n in variants or any(n.endswith("_" + v) or n.endswith("-" + v) for v in variants)


def pick(items, wanted, name_key, kind):
    exact = [i for i in items if i.get(name_key) == wanted]
    found = exact or [i for i in items if matches(i.get(name_key), wanted)]
    if not found:
        fail(f"No {kind} named {wanted} in {REGION}. Check the name, and that it has finished creating.")
    if len(found) > 1:
        names = ", ".join(i.get(name_key, "?") for i in found)
        print(f"Note: several {kind}s match {wanted} ({names}). Using the most recently updated.", file=sys.stderr)
        found.sort(key=lambda i: str(i.get("updatedAt", "")), reverse=True)
    return found[0]


def find_harness(name):
    h = pick(paged(control().list_harnesses, "harnesses"), name, "harnessName", "harness")
    if h.get("status") != "READY":
        fail(f"Harness {h['harnessName']} is {h.get('status')}, not READY yet. Give it a minute.")
    return h


def find_gateway(name):
    g = pick(paged(control().list_gateways, "items"), name, "name", "gateway")
    detail = control().get_gateway(gatewayIdentifier=g["gatewayId"])
    if detail.get("status") != "READY":
        fail(f"Gateway {detail['name']} is {detail.get('status')}, not READY yet. Give it a minute.")
    return detail


def invoke(client, harness_arn, prompt, actor, session=None):
    """Send one message and return (text, tools used, seconds, stop reason)."""
    start = time.monotonic()
    resp = client.invoke_harness(
        harnessArn=harness_arn,
        runtimeSessionId=session or str(uuid.uuid4()),
        actorId=actor,
        messages=[{"role": "user", "content": [{"text": prompt}]}],
    )
    text, tools, stop = [], [], ""
    for event in resp["stream"]:
        if "contentBlockStart" in event:
            tool = event["contentBlockStart"].get("start", {}).get("toolUse")
            if tool:
                tools.append(tool.get("name", "?"))
        elif "contentBlockDelta" in event:
            delta = event["contentBlockDelta"].get("delta", {})
            if "text" in delta:
                text.append(delta["text"])
        elif "messageStop" in event:
            stop = event["messageStop"].get("stopReason", stop)
        else:
            for err in ("runtimeClientError", "validationException", "internalServerException"):
                if err in event:
                    raise RuntimeError(f"{err}: {event[err].get('message', event[err])}")
    return "".join(text).strip(), tools, time.monotonic() - start, stop


# ---- commands ------------------------------------------------------------------------------

def cmd_harness_arn(name):
    print(find_harness(name)["arn"])


def cmd_gateway_url(name):
    print(find_gateway(name)["gatewayUrl"])


def cmd_gateway_arn(name):
    print(find_gateway(name)["gatewayArn"])


BURST_PEOPLE = [
    ("Aisha", "kopi-o siew dai"), ("Ben", "teh peng"), ("Chen", "kopi-c kosong"), ("Divya", "teh-o"),
    ("Elijah", "kopi gao"), ("Farah", "milo peng"), ("Gabriel", "kopi-o kosong peng"), ("Hui Min", "teh-c siew dai"),
    ("Irfan", "yuan yang"), ("Jia Hui", "kopi peng"), ("Kumar", "teh gao"), ("Li Ting", "kopi-c siew dai peng"),
    ("Mei", "teh-o peng"), ("Nadia", "kopi-o"), ("Omar", "teh"), ("Pei Shan", "kopi siew dai"),
    ("Qi Rui", "milo"), ("Rahul", "kopi-c peng"), ("Sara", "teh-c kosong"), ("Tan", "kopi-o gao"),
    ("Umar", "teh siew dai peng"), ("Vanessa", "kopi-c"), ("Wen Jie", "teh-o siew dai"), ("Xin Yi", "kopi po"),
    ("Yusuf", "teh peng siew dai"), ("Zara", "kopi-o peng"),
]


def cmd_burst(name, n):
    n = max(1, min(int(n), len(BURST_PEOPLE)))
    harness = find_harness(name)
    client = data_plane(pool=n + 5)
    gate = threading.Barrier(n)
    print(f"Sending {n} orders to {harness['harnessName']} at the same moment, one session each...\n")

    def one(i):
        person, drink = BURST_PEOPLE[i]
        gate.wait()  # line everyone up, then go together
        try:
            _text, tools, secs, stop = invoke(client, harness["arn"], f"One {drink} for me please. I'm {person}.", actor=person.lower().replace(" ", "-"))
            ordered = any(t.endswith("place_order") for t in tools)
            return person, drink, secs, ("ordered" if ordered else f"no order ({stop or 'check the reply'})")
        except Exception as exc:  # report and keep going; throttling shows up here
            return person, drink, None, f"error: {exc}"[:90]

    with ThreadPoolExecutor(max_workers=n) as pool:
        results = list(pool.map(one, range(n)))

    for person, drink, secs, outcome in results:
        print(f"  {person:<9} {drink:<22} {('%5.1fs' % secs) if secs else '   - '}  {outcome}")
    times = [r[2] for r in results if r[2]]
    if times:
        print(f"\n{len(times)} of {n} finished. Fastest {min(times):.1f}s, median {statistics.median(times):.1f}s, slowest {max(times):.1f}s.")
    if any("Throttl" in r[3] for r in results):
        print("Some calls were throttled. Try a smaller burst: kopi-burst.sh 10")


def cmd_ask(name, path):
    harness = find_harness(name)
    client = data_plane()
    with open(path, encoding="utf-8") as fh:
        questions = [q.strip() for q in fh if q.strip() and not q.lstrip().startswith("#")]
    for i, q in enumerate(questions, 1):
        print(f"\nQ{i}: {q}")
        try:
            text, tools, secs, _stop = invoke(client, harness["arn"], q, actor="finance")
            print(f"A{i}: {text}")
            print(f"    ({secs:.1f}s, tools: {', '.join(tools) or 'none'})")
        except Exception as exc:
            print(f"A{i}: error: {exc}")
    print(f"\nAsked {len(questions)} questions, each in its own session.")


def inventory(scenario):
    want = SCENARIOS.get(scenario)
    if not want:
        fail(f"Unknown scenario {scenario}. Use one of: {', '.join(SCENARIOS)}")
    c, found = control(), []
    if want.get("online_evals"):
        for o in paged(c.list_online_evaluation_configs, "onlineEvaluationConfigs"):
            if any(matches(o.get("onlineEvaluationConfigName"), w) for w in want["online_evals"]):
                found.append({"type": "online evaluation", "name": o["onlineEvaluationConfigName"], "id": o["onlineEvaluationConfigId"]})
    if want.get("evaluators"):
        for e in paged(c.list_evaluators, "evaluators"):
            if e.get("evaluatorType", "").upper() != "BUILTIN" and any(matches(e.get("evaluatorName"), w) for w in want["evaluators"]):
                found.append({"type": "evaluator", "name": e["evaluatorName"], "id": e["evaluatorId"]})
    if want.get("harnesses"):
        for h in paged(c.list_harnesses, "harnesses"):
            if any(matches(h.get("harnessName"), w) for w in want["harnesses"]):
                found.append({"type": "harness", "name": h["harnessName"], "id": h["harnessId"]})
    if want.get("gateways"):
        for g in paged(c.list_gateways, "items"):
            if any(matches(g.get("name"), w) for w in want["gateways"]):
                found.append({"type": "gateway", "name": g["name"], "id": g["gatewayId"]})
    if want.get("policy_engines"):
        for p in paged(c.list_policy_engines, "policyEngines"):
            if any(matches(p.get("name"), w) for w in want["policy_engines"]):
                found.append({"type": "policy engine", "name": p["name"], "id": p["policyEngineId"]})
    return found


def cmd_inventory(scenario):
    print(json.dumps(inventory(scenario)))


def wait_gone(check, label, timeout=600):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        try:
            if not check():
                return
        except ClientError as exc:
            if exc.response["Error"]["Code"] in ("ResourceNotFoundException", "NotFoundException"):
                return
            raise
        time.sleep(5)
    print(f"  {label} is still being deleted after {timeout // 60} minutes; carrying on.", file=sys.stderr)


def cmd_delete(scenario):
    """Delete in dependency order: online evals, evaluators, harnesses, gateways, policy engines."""
    c = control()
    for item in inventory(scenario):
        kind, name, rid = item["type"], item["name"], item["id"]
        print(f"  Deleting {kind} {name}...")
        try:
            if kind == "online evaluation":
                c.delete_online_evaluation_config(onlineEvaluationConfigId=rid)
                wait_gone(lambda: any(o["onlineEvaluationConfigId"] == rid for o in paged(c.list_online_evaluation_configs, "onlineEvaluationConfigs")), name)
            elif kind == "evaluator":
                c.delete_evaluator(evaluatorId=rid)
                wait_gone(lambda: any(e["evaluatorId"] == rid for e in paged(c.list_evaluators, "evaluators")), name)
            elif kind == "harness":
                c.delete_harness(harnessId=rid, deleteManagedMemory=True)
                wait_gone(lambda: any(h["harnessId"] == rid for h in paged(c.list_harnesses, "harnesses")), name)
            elif kind == "gateway":
                for t in paged(c.list_gateway_targets, "items", gatewayIdentifier=rid):
                    c.delete_gateway_target(gatewayIdentifier=rid, targetId=t["targetId"])
                wait_gone(lambda: bool(paged(c.list_gateway_targets, "items", gatewayIdentifier=rid)), f"{name} targets")
                c.delete_gateway(gatewayIdentifier=rid)
                wait_gone(lambda: bool(c.get_gateway(gatewayIdentifier=rid)), name)
            elif kind == "policy engine":
                for p in paged(c.list_policies, "policies", policyEngineId=rid):
                    c.delete_policy(policyEngineId=rid, policyId=p["policyId"])
                wait_gone(lambda: bool(paged(c.list_policies, "policies", policyEngineId=rid)), f"{name} policies")
                c.delete_policy_engine(policyEngineId=rid)
                wait_gone(lambda: any(p["policyEngineId"] == rid for p in paged(c.list_policy_engines, "policyEngines")), name)
        except ClientError as exc:
            fail(f"Could not delete {kind} {name}: {exc.response['Error'].get('Message', exc)}")
    print("  Done.")


COMMANDS = {
    "harness-arn": (cmd_harness_arn, 1),
    "gateway-url": (cmd_gateway_url, 1),
    "gateway-arn": (cmd_gateway_arn, 1),
    "burst": (cmd_burst, 2),
    "ask": (cmd_ask, 2),
    "inventory": (cmd_inventory, 1),
    "delete": (cmd_delete, 1),
}


def main(argv):
    if len(argv) < 2 or argv[1] not in COMMANDS:
        fail(__doc__, 2)
    fn, nargs = COMMANDS[argv[1]]
    if len(argv) - 2 != nargs:
        fail(f"{argv[1]} takes {nargs} argument(s). See the top of {argv[0]}.", 2)
    try:
        fn(*argv[2:])
    except ClientError as exc:
        err = exc.response["Error"]
        fail(f"{err.get('Code')}: {err.get('Message')}")


if __name__ == "__main__":
    main(sys.argv)
