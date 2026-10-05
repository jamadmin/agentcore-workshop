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

from common import chat, model, parse_args, start_session, system_prompt


def main():
    args = parse_args()
    session_id = start_session()

    gateway = MCPClient(lambda: aws_iam_streamablehttp_client(
        endpoint=os.environ["TALLY_GATEWAY_URL"],
        aws_region=os.environ["AWS_REGION"],
        aws_service="bedrock-agentcore",
    ))

    with gateway:
        agent = Agent(
            model=model(),
            system_prompt=system_prompt(args.customer),
            tools=gateway.list_tools_sync(),
            trace_attributes={"session.id": session_id, "customer.id": args.customer},
        )
        chat(agent, session_id)


if __name__ == "__main__":
    main()
