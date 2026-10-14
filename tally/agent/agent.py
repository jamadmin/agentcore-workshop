"""Tally's billing support agent, as the Tally team wrote it.

The tools are plain Python functions that call the Tally backend directly with
boto3, using whatever AWS credentials the host has. Nothing limits issue_credit.
Run it with ./run.sh before --customer kettle
"""
import json
import os

import boto3
from strands import Agent, tool

from common import chat, model, parse_args, start_session, system_prompt

FUNCTION = os.environ.get("TALLY_API_FUNCTION", "agentcore-workshop-tally-api")
_lambda = boto3.client("lambda", region_name=os.environ.get("AWS_REGION", "us-east-1"))


def call_backend(name, **args):
    resp = _lambda.invoke(FunctionName=FUNCTION, Payload=json.dumps({"tool": name, **args}))
    return resp["Payload"].read().decode("utf-8")


@tool
def get_invoice(customer_id: str, invoice_id: str) -> str:
    """Get an invoice with its line items and total.

    Args:
        customer_id: The customer's ID.
        invoice_id: For example INV-2026-03.
    """
    return call_backend("get_invoice", customer_id=customer_id, invoice_id=invoice_id)


@tool
def get_usage(customer_id: str, month: str) -> str:
    """Get how many people at a customer used the software in one month.

    Args:
        customer_id: The customer's ID.
        month: The month as YYYY-MM.
    """
    return call_backend("get_usage", customer_id=customer_id, month=month)


@tool
def issue_credit(customer_id: str, amount: int, reason: str) -> str:
    """Issue a credit to a customer's account. It is applied to their next invoice.

    Args:
        customer_id: The customer's ID.
        amount: Credit in whole Singapore dollars.
        reason: Why the credit is being issued.
    """
    return call_backend("issue_credit", customer_id=customer_id, amount=amount, reason=reason)


def main():
    args = parse_args()
    session_id = start_session()
    agent = Agent(
        model=model(),
        system_prompt=system_prompt(args.customer),
        tools=[get_invoice, get_usage, issue_credit],
        trace_attributes={"session.id": session_id, "customer.id": args.customer},
    )
    chat(agent, session_id)


if __name__ == "__main__":
    main()
