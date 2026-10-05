# AgentCore workshop code

Code and files for **Build, deploy and operate agents with AWS** (AWS Startups x JAM, Singapore, 20 October 2026). The step-by-step guide is a separate site; this repo is what you clone in the setup step.

```bash
cd ~
git clone https://github.com/jamadmin/agentcore-workshop.git agentcore-workshop
cd agentcore-workshop
source scripts/env.sh
scripts/check-setup.sh
```

`env.sh` only affects the terminal you run it in. It doesn't touch `~/.bashrc` or any other file. Every script loads it for itself, so scripts work in a fresh terminal too.

## What's here

| Path | What it's for |
|---|---|
| `scripts/env.sh` | Sets `WORKSHOP`, `AWS_REGION`, the three API ARNs and the `newsession` command |
| `scripts/check-setup.sh` | Checks tools, credentials, region, one model call, the three APIs and Transaction Search |
| `scripts/enable-transaction-search.sh` | Turns on CloudWatch Transaction Search for the account |
| `scripts/kopi.sh run\|reset` | Reads or clears today's Kopi Run order list |
| `scripts/kopi-burst.sh [n]` | Sends n orders to `kopi_agent` at once, one session each |
| `scripts/tally.sh credits <id>` | Lists credits issued to a Tally customer |
| `scripts/intake-ask.sh <harness> <file>` | Asks each question in its own session |
| `scripts/set-prompt.sh <harness> <file>` | Replaces a harness's system prompt in a CLI project |
| `scripts/gateway-url.sh`, `gateway-arn.sh` | Finds a gateway by name |
| `scripts/catch-up.sh <scenario>` | Jumps a scenario to its finished state |
| `kopi-run/` | Scenario 1: system prompt and tool list (with the bug) |
| `tally/` | Scenario 2: the Tally team's agent, its tool list and two Cedar policies |
| `intake/` | Scenario 3: two system prompts, tool list, questions and the `AmountCheck` evaluator |
| `solutions/` | Finished tool lists that `catch-up.sh` uses |
| `backends/` | The three sample APIs (Lambda and DynamoDB, synthetic data) as a CDK app |

The scripts find AgentCore resources by name through the AWS APIs, so they work whether you built something in the console or with the CLI. The CLI puts the project name in front of some names (a harness called `kopi_agent` in project `KopiRun` is deployed as `KopiRun_kopi_agent`); the scripts accept either.

The Python helpers run through `uv`, which fetches a recent `boto3` the first time. Nothing is installed into the system Python.

## Running it in your own account

Workshop accounts already have the sample APIs. In your own account, deploy them first (CDK must be bootstrapped in the region, which `agentcore deploy` needs anyway):

```bash
scripts/deploy-backends.sh
source scripts/env.sh
```

When you're done, follow the clean-up section on the guide's wrap-up page, then run `scripts/destroy-backends.sh`.

Never put access keys, tokens or customer data in any file here. The scripts use the credentials already in your environment.

## For facilitators

**Tests (offline, no AWS calls):**

```bash
cd backends && python3 -m unittest discover -s tests -v && cd ..
uv run --with boto3 python -m unittest discover -s scripts/tests -v
```

The backend tests check the numbers the story depends on: Kettle & Co's March invoice comes to $4,812.00 and should have been $1,200.00; two plus five on a string quantity gives 25; only the Nordlicht invoice is below 0.9 confidence. The script tests stub every AWS call and check each request against the real API model.

**Resetting an account between dry runs:** `scripts/kopi.sh reset` and `scripts/tally.sh reset kettle`.

**Workshop Studio:** the account template has to create the three APIs with exactly these function names, because everything looks them up by name: `agentcore-workshop-kopi-api`, `agentcore-workshop-tally-api`, `agentcore-workshop-intake-api`. `cd backends && npm install && npx cdk synth` produces the CloudFormation template and the Lambda code assets in `cdk.out/` for the event's template.

**The data:**

| Scenario | What's planted |
|---|---|
| Kopi Run | `place_order` adds quantities without a type check, so `"2" + "5"` is `"25"`. Marcus's past orders show a kopi-c kosong peng |
| Tally | Kettle & Co (`kettle`): Starter subscription never closed when Scale started on 14 March. March is billed on both: $310 + $3,980 + $522 = $4,812. Correct would be $130 + $548 + $522 = $1,200. `issue_credit` has no limit |
| Intake | Nordlicht GmbH `INV-1041`: document says `100,00 EUR`, extracted as 10000.00 at 0.62 confidence. Their previous invoices were about €100 |
