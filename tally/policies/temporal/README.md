# Temporal policy: cap credits per conversation (draft)

**Status: draft for facilitators. Not tested in a real account yet, and not in the attendee guide.** Try it in jam-ai first. If it behaves as below, it can become an optional "if you finish early" step for Tally.

## What it does

The workshop's `small_credits` rule refuses any single credit over S$50, but splitting a credit into small ones gets round it. `credit-total-per-session.dogwood` adds a running total: it forbids `issue_credit` once the credits requested in the same policy session, including the current one, add up to more than S$50 within 24 hours. It's the "cumulative budget" pattern from the AWS docs, written in Dogwood (compatible with Cedar).

It only works within a **policy session**. The agent has to send a session ID in the `x-amzn-bedrock-agentcore-policy-session-id` header, and a new session starts a new total. So this limits a conversation, not a customer. The real per-customer cap belongs in the Tally API.

## Try it

You need the Tally scenario finished up to and including the Policy step (`tally_policies` attached to `tally-gw` in ENFORCE mode).

```bash
cd $WORKSHOP/tally/policies/temporal &&
uv run --quiet --script temporal.py install
```

This makes two changes in the account. Treat them as a change under the usual process:

1. Adds an inline policy `TallyTemporalPolicyWorkloadIdentity` to the Gateway's IAM role, granting `bedrock-agentcore:GetWorkloadAccessToken`. Temporal policies need it to tie a session to the caller.
2. Creates the policy `credit_total_per_session` in `tally_policies`.

Then clear the credits and start the agent **with a policy session**:

```bash
$WORKSHOP/scripts/tally.sh reset kettle &&
cd $WORKSHOP/tally/agent &&
./run.sh gateway --customer kettle --policy-session
```

Ask for these in one conversation, and note what happens:

| Ask | Running total | Expected |
|---|---|---|
| S$30 credit | 30 | Allowed |
| S$20 credit | 50 | Allowed (the rule is "more than 50") |
| S$10 credit | 60 | Refused by the temporal policy |
| S$500 credit | | Refused by `small_credits` (per call) |
| S$5 credit | 55 or 555 | Refused |

Then `exit`, start the agent again with `--policy-session` (a new session), and ask for S$30: it should be allowed, because the total starts again. That's the limitation to explain to attendees.

## Things to check while testing

- Does the policy reach `ACTIVE`? `temporal.py install` prints the status and any validation findings.
- Without `--policy-session`, calls should fail with a validation error once a temporal policy is on the engine. The docs say so; confirm it, because it affects anyone still running the agent without the flag.
- Are refused calls counted in the total? The docs say a denied call is recorded as an `error` event, not a `request`, so the S$500 shouldn't count. The last row of the table tells you.
- Do the guide's main steps still work after `remove`?

## Remove it

```bash
cd $WORKSHOP/tally/policies/temporal &&
uv run --quiet --script temporal.py remove
```

This deletes the policy and the inline IAM policy. Run the agent without `--policy-session` afterwards.

## Sources

- [Temporal policies](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/policy-temporal.html), including Region support (Singapore: yes) and quotas
- [Authoring temporal policies](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/policy-temporal-authoring.html), "Example: cumulative budget"
- [Policy sessions and identity propagation](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/policy-session-based-temporal.html)
- [IAM permissions for temporal policies](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/policy-permissions.html#policy-permissions-session-temporal)
- [Dogwood language guide](https://dogwood-policy.github.io/dogwood/index.html)
