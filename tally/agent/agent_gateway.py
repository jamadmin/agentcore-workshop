"""Tally's billing support agent, with its tools behind an AgentCore Gateway.

Same agent, same model, same prompt. The Python tool functions are gone: the
agent lists its tools from the Gateway over MCP and signs every request with
AWS credentials (SigV4). Policy on the Gateway decides which calls go through.
Run it with ./run.sh gateway --customer kettle
"""
import os

from mcp_proxy_for_aws.client import aws_iam_streamablehttp_client
from strands import Agent
from strands.tools.mcp import MCPClient
from strands.types.exceptions import MCPClientInitializationError

from common import chat, model, parse_args, start_session, system_prompt


def main():
    args = parse_args()
    session_id = start_session()

    # Temporal policies (optional extension) group calls by a policy session ID the caller sends.
    # Off by default: with a session ID and a policy engine attached, the Gateway role also needs
    # bedrock-agentcore:GetWorkloadAccessToken. See tally/policies/temporal/README.md.
    headers = {"x-amzn-bedrock-agentcore-policy-session-id": session_id} if args.policy_session else None
    if headers:
        print(f"Policy session {session_id} (temporal policies see this conversation's history)")

    gateway = MCPClient(lambda: aws_iam_streamablehttp_client(
        endpoint=os.environ["TALLY_GATEWAY_URL"],
        aws_region=os.environ["AWS_REGION"],
        aws_service="bedrock-agentcore",
        headers=headers,
    ))

    try:
        gateway.start()
    except MCPClientInitializationError as exc:
        raise SystemExit(
            f"Couldn't connect to the Gateway at {os.environ['TALLY_GATEWAY_URL']}.\n"
            "Check it shows Ready, that the URL ends in /mcp, and that your AWS credentials haven't expired "
            f"(aws sts get-caller-identity).\nDetail: {exc}"
        )

    try:
        agent = Agent(
            model=model(),
            system_prompt=system_prompt(args.customer),
            tools=gateway.list_tools_sync(),
            trace_attributes={"session.id": session_id, "customer.id": args.customer},
        )
        chat(agent, session_id)
    finally:
        gateway.stop(None, None, None)


if __name__ == "__main__":
    main()
