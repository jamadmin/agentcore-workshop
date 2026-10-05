#!/usr/bin/env bash
# Turns on CloudWatch Transaction Search for this account and region: lets X-Ray write
# spans to CloudWatch Logs, then sends trace segments there. Safe to run twice.
set -euo pipefail
source "$(dirname "$0")/lib/common.sh"

account="$(aws sts get-caller-identity --query Account --output text)"
current="$(aws xray get-trace-segment-destination --query '[Destination,Status]' --output text 2>/dev/null || true)"
if [[ "$current" == CloudWatchLogs* ]]; then
  echo "Transaction Search is already on ($current)."
  exit 0
fi

policy=$(cat <<JSON
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "TransactionSearchXRayAccess",
      "Effect": "Allow",
      "Principal": { "Service": "xray.amazonaws.com" },
      "Action": "logs:PutLogEvents",
      "Resource": [
        "arn:aws:logs:${AWS_REGION}:${account}:log-group:aws/spans:*",
        "arn:aws:logs:${AWS_REGION}:${account}:log-group:/aws/application-signals/data:*"
      ],
      "Condition": {
        "ArnLike": { "aws:SourceArn": "arn:aws:xray:${AWS_REGION}:${account}:*" },
        "StringEquals": { "aws:SourceAccount": "${account}" }
      }
    }
  ]
}
JSON
)

echo "Allowing X-Ray to write spans to CloudWatch Logs..."
aws logs put-resource-policy --policy-name TransactionSearchXRayAccess --policy-document "$policy" >/dev/null

echo "Sending trace segments to CloudWatch Logs..."
aws xray update-trace-segment-destination --destination CloudWatchLogs >/dev/null

echo
aws xray get-trace-segment-destination --query '{Destination:Destination,Status:Status}' --output table
echo "It takes up to ten minutes to start indexing. Carry on with the next step."
