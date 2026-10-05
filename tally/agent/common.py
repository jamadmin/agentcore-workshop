"""Shared by agent.py and agent_gateway.py: model, prompt, session tracing and the chat loop."""
import argparse
import os
import uuid
from pathlib import Path

from opentelemetry import baggage, context
from strands.models import BedrockModel

MODEL_ID = os.environ.get("TALLY_MODEL_ID", "global.anthropic.claude-sonnet-4-6")
HERE = Path(__file__).resolve().parent


def parse_args():
    parser = argparse.ArgumentParser(description="Tally billing support agent")
    parser.add_argument("--customer", required=True, help="Customer ID, for example kettle")
    return parser.parse_args()


def model():
    return BedrockModel(model_id=MODEL_ID, region_name=os.environ.get("AWS_REGION", "ap-southeast-1"))


def system_prompt(customer_id):
    return (HERE / "system-prompt.md").read_text(encoding="utf-8").replace("{customer_id}", customer_id)


def start_session():
    """One session per run, so CloudWatch groups each conversation's traces together."""
    session_id = str(uuid.uuid4())
    context.attach(baggage.set_baggage("session.id", session_id))
    return session_id


def chat(agent, session_id):
    print(f"Tally billing assistant (session {session_id[:8]}). Type exit to leave.\n")
    while True:
        try:
            message = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not message:
            continue
        if message.lower() in ("exit", "quit"):
            break
        print("tally> ", end="", flush=True)
        try:
            agent(message)
        except Exception as exc:
            print(f"\n[error] {exc}")
        print("\n")
