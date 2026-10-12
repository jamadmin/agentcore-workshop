# /// script
# requires-python = ">=3.10"
# dependencies = ["boto3>=1.43"]
# ///
"""Try the temporal credit-total policy on the tally-gw Gateway. DRAFT for facilitators.

    uv run --quiet --script temporal.py install    add the IAM permission and the policy
    uv run --quiet --script temporal.py status     show the policy's state
    uv run --quiet --script temporal.py remove     take both away again

Run it with credentials for the account the workshop resources are in. It changes an IAM
role and a policy engine, so treat it as a change to that account.
"""
import json
import os
import pathlib
import sys
import time

import boto3

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3] / "scripts" / "lib"))
import agentcore as ac  # noqa: E402  (the workshop's lookup helpers)

REGION = ac.REGION
POLICY_NAME = "credit_total_per_session"
ROLE_POLICY_NAME = "TallyTemporalPolicyWorkloadIdentity"
HERE = pathlib.Path(__file__).resolve().parent


def engine():
    c = ac.control()
    found = ac.pick(ac.paged(c.list_policy_engines, "policyEngines"), "tally_policies", "name", "policy engine")
    return found["policyEngineId"]


def install():
    gw = ac.find_gateway("tally-gw")
    account = boto3.client("sts").get_caller_identity()["Account"]
    role_name = gw["roleArn"].split("/")[-1]

    # 1. Temporal policies need the Gateway role to mint a workload access token.
    statement = {
        "Version": "2012-10-17",
        "Statement": [{
            "Sid": "PolicySessionWorkloadIdentity",
            "Effect": "Allow",
            "Action": ["bedrock-agentcore:GetWorkloadAccessToken"],
            "Resource": [
                f"arn:aws:bedrock-agentcore:{REGION}:{account}:workload-identity-directory/default",
                f"arn:aws:bedrock-agentcore:{REGION}:{account}:workload-identity-directory/default/workload-identity/{gw['gatewayId']}*",
            ],
        }],
    }
    print(f"Adding GetWorkloadAccessToken to the Gateway role {role_name}...")
    boto3.client("iam").put_role_policy(RoleName=role_name, PolicyName=ROLE_POLICY_NAME, PolicyDocument=json.dumps(statement))

    # 2. The Dogwood policy itself, under definition.policy (not .cedar).
    text = (HERE / "credit-total-per-session.dogwood").read_text(encoding="utf-8")
    text = "\n".join(l for l in text.splitlines() if not l.lstrip().startswith("//"))
    text = text.replace("${GATEWAY_ARN}", gw["gatewayArn"])
    eid = engine()
    print(f"Creating policy {POLICY_NAME} in engine {eid}...")
    resp = ac.control().create_policy(
        policyEngineId=eid,
        name=POLICY_NAME,
        description="Workshop draft: no more than $50 of credits per policy session",
        validationMode="FAIL_ON_ANY_FINDINGS",
        definition={"policy": {"statement": text}},
    )
    pid = resp["policyId"]
    for _ in range(30):
        p = ac.control().get_policy(policyEngineId=eid, policyId=pid)
        if p["status"] not in ("CREATING", "UPDATING"):
            break
        time.sleep(4)
    print(f"Policy status: {p['status']}")
    for reason in p.get("statusReasons", []) or []:
        print(f"  {reason}")
    print("\nNow run the agent with a policy session:  ./run.sh gateway --customer kettle --policy-session")


def status():
    eid = engine()
    for p in ac.paged(ac.control().list_policies, "policies", policyEngineId=eid):
        print(f"{p['name']:<28} {p['status']}")


def remove():
    eid = engine()
    c = ac.control()
    for p in ac.paged(c.list_policies, "policies", policyEngineId=eid):
        if p["name"] == POLICY_NAME:
            print(f"Deleting policy {POLICY_NAME}...")
            c.delete_policy(policyEngineId=eid, policyId=p["policyId"])
    gw = ac.find_gateway("tally-gw")
    role_name = gw["roleArn"].split("/")[-1]
    iam = boto3.client("iam")
    try:
        iam.delete_role_policy(RoleName=role_name, PolicyName=ROLE_POLICY_NAME)
        print(f"Removed {ROLE_POLICY_NAME} from {role_name}.")
    except iam.exceptions.NoSuchEntityException:
        pass
    print("Done. Run the agent without --policy-session again.")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    {"install": install, "status": status, "remove": remove}.get(cmd, lambda: sys.exit(__doc__))()
