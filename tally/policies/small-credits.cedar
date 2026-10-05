permit(
  principal is AgentCore::IamEntity,
  action == AgentCore::Action::"tally-api___issue_credit",
  resource == AgentCore::Gateway::"${GATEWAY_ARN}"
) when {
  context.input.amount <= 50
};
