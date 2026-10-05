permit(
  principal is AgentCore::IamEntity,
  action in [
    AgentCore::Action::"tally-api___get_invoice",
    AgentCore::Action::"tally-api___get_usage",
    AgentCore::Action::"tally-api___explain_invoice"
  ],
  resource == AgentCore::Gateway::"${GATEWAY_ARN}"
);
