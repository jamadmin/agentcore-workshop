"""Offline tests for scripts/lib/agentcore.py. Every AWS call is stubbed with botocore's
Stubber. The client still validates every request against the real API model, so a
wrong parameter name fails here rather than in the room. The fake responses are kept
short, so response validation is switched off.

    uv run --with boto3 python -m unittest discover -s scripts/tests -v
"""
import importlib.util
import io
import json
import pathlib
import unittest
from contextlib import redirect_stdout
from datetime import datetime
from unittest import mock

import boto3
from botocore.stub import ANY, Stubber

# Requests are still validated by the client; only the stubbed responses skip validation.
Stubber._validate_operation_response = lambda self, operation_name, service_response: None

SPEC = importlib.util.spec_from_file_location("agentcore_helpers", pathlib.Path(__file__).resolve().parents[1] / "lib" / "agentcore.py")
ac = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ac)

NOW = datetime(2026, 10, 20, 9, 0, 0)
ACCOUNT = "111122223333"
HARNESS_ARN = f"arn:aws:bedrock-agentcore:ap-southeast-1:{ACCOUNT}:harness/KopiRun_kopi_agent-abcdef1234"


class StubbedTest(unittest.TestCase):
    def setUp(self):
        session = boto3.session.Session(region_name="ap-southeast-1", aws_access_key_id="x", aws_secret_access_key="y")
        self.ctrl = session.client("bedrock-agentcore-control")
        self.stub = Stubber(self.ctrl)
        self.stub.activate()
        patcher = mock.patch.object(ac, "control", return_value=self.ctrl)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.stub.deactivate)

    def harness_list(self, name="KopiRun_kopi_agent", status="READY"):
        self.stub.add_response("list_harnesses", {"harnesses": [
            {"harnessId": "KopiRun_kopi_agent-abcdef1234", "harnessName": name, "arn": HARNESS_ARN, "status": status, "createdAt": NOW, "updatedAt": NOW},
        ]}, {})

    def gateway_list(self, name="tally-gw"):
        self.stub.add_response("list_gateways", {"items": [
            {"gatewayId": "tally-gw-abcdefghij", "name": name, "status": "READY", "createdAt": NOW, "updatedAt": NOW, "authorizerType": "AWS_IAM"},
        ]}, {})

    def get_gateway(self, name="tally-gw", status="READY"):
        self.stub.add_response("get_gateway", {
            "gatewayArn": f"arn:aws:bedrock-agentcore:ap-southeast-1:{ACCOUNT}:gateway/tally-gw-abcdefghij",
            "gatewayId": "tally-gw-abcdefghij", "gatewayUrl": "https://tally-gw-abcdefghij.gateway.bedrock-agentcore.ap-southeast-1.amazonaws.com/mcp",
            "name": name, "status": status, "createdAt": NOW, "updatedAt": NOW, "authorizerType": "AWS_IAM", "protocolType": "MCP",
        }, {"gatewayIdentifier": "tally-gw-abcdefghij"})


class LookupTests(StubbedTest):
    def test_matching_rules(self):
        self.assertTrue(ac.matches("kopi_agent", "kopi_agent"))
        self.assertTrue(ac.matches("KopiRun_kopi_agent", "kopi_agent"))
        self.assertTrue(ac.matches("TallyTools-tally-gw", "tally-gw"))
        self.assertFalse(ac.matches("intake_agent", "kopi_agent"))
        self.assertFalse(ac.matches("my-tally-gw2", "tally-gw"))

    def test_harness_arn_with_cli_prefix(self):
        self.harness_list()
        out = io.StringIO()
        with redirect_stdout(out):
            ac.cmd_harness_arn("kopi_agent")
        self.assertEqual(out.getvalue().strip(), HARNESS_ARN)

    def test_harness_not_ready(self):
        self.harness_list(status="CREATING")
        with self.assertRaises(SystemExit):
            ac.find_harness("kopi_agent")

    def test_gateway_url_and_arn(self):
        self.gateway_list()
        self.get_gateway()
        out = io.StringIO()
        with redirect_stdout(out):
            ac.cmd_gateway_url("tally-gw")
        self.assertTrue(out.getvalue().startswith("https://"))
        self.gateway_list(name="TallyTools-tally-gw")
        self.get_gateway(name="TallyTools-tally-gw")
        out = io.StringIO()
        with redirect_stdout(out):
            ac.cmd_gateway_arn("tally-gw")
        self.assertIn(":gateway/", out.getvalue())

    def test_missing_gateway(self):
        self.stub.add_response("list_gateways", {"items": []}, {})
        with self.assertRaises(SystemExit):
            ac.find_gateway("tally-gw")


class InventoryAndDeleteTests(StubbedTest):
    def test_intake_inventory_and_delete_order(self):
        def inventory_calls():
            self.stub.add_response("list_online_evaluation_configs", {"onlineEvaluationConfigs": [
                {"onlineEvaluationConfigArn": "arn:x", "onlineEvaluationConfigId": "intake_live-abcd123456", "onlineEvaluationConfigName": "intake_live", "status": "ACTIVE", "executionStatus": "ENABLED", "createdAt": NOW, "updatedAt": NOW}]}, {})
            self.stub.add_response("list_evaluators", {"evaluators": [
                {"evaluatorArn": "arn:x", "evaluatorId": "AmountCheck-abcd123456", "evaluatorName": "AmountCheck", "evaluatorType": "Custom", "status": "ACTIVE", "createdAt": NOW, "updatedAt": NOW},
                {"evaluatorArn": "arn:y", "evaluatorId": "Builtin.Correctness", "evaluatorName": "Builtin.Correctness", "evaluatorType": "Builtin", "status": "ACTIVE", "createdAt": NOW, "updatedAt": NOW}]}, {})
            self.stub.add_response("list_harnesses", {"harnesses": [
                {"harnessId": "intake_agent-abcdef1234", "harnessName": "intake_agent", "arn": "arn:z", "status": "READY", "createdAt": NOW, "updatedAt": NOW}]}, {})
            self.stub.add_response("list_gateways", {"items": [
                {"gatewayId": "intake-gw-abcdefghij", "name": "intake-gw", "status": "READY", "createdAt": NOW, "updatedAt": NOW, "authorizerType": "AWS_IAM"}]}, {})

        inventory_calls()
        found = ac.inventory("intake")
        self.assertEqual([i["type"] for i in found], ["online evaluation", "evaluator", "harness", "gateway"])

        inventory_calls()
        self.stub.add_response("delete_online_evaluation_config", {"onlineEvaluationConfigArn": "arn:x", "onlineEvaluationConfigId": "intake_live-abcd123456", "status": "DELETING"}, {"onlineEvaluationConfigId": "intake_live-abcd123456"})
        self.stub.add_response("list_online_evaluation_configs", {"onlineEvaluationConfigs": []}, {})
        self.stub.add_response("delete_evaluator", {"evaluatorArn": "arn:x", "evaluatorId": "AmountCheck-abcd123456", "status": "DELETING"}, {"evaluatorId": "AmountCheck-abcd123456"})
        self.stub.add_response("list_evaluators", {"evaluators": []}, {})
        self.stub.add_response("delete_harness", {"harness": {
            "harnessId": "intake_agent-abcdef1234", "harnessName": "intake_agent", "arn": "arn:z", "status": "DELETING",
            "executionRoleArn": f"arn:aws:iam::{ACCOUNT}:role/r", "createdAt": NOW, "updatedAt": NOW,
            "model": {"bedrockModelConfig": {"modelId": "global.anthropic.claude-sonnet-4-6"}},
            "systemPrompt": [{"text": "x"}], "tools": [], "skills": [], "allowedTools": ["*"],
            "truncation": {"strategy": "sliding_window"}, "environment": {"agentCoreRuntimeEnvironment": {}},
        }}, {"harnessId": "intake_agent-abcdef1234", "deleteManagedMemory": True})
        self.stub.add_response("list_harnesses", {"harnesses": []}, {})
        self.stub.add_response("list_gateway_targets", {"items": [
            {"targetId": "TGT0000001", "name": "intake-api", "status": "READY", "createdAt": NOW, "updatedAt": NOW}]}, {"gatewayIdentifier": "intake-gw-abcdefghij"})
        self.stub.add_response("delete_gateway_target", {"gatewayArn": "arn:g", "targetId": "TGT0000001", "status": "DELETING"},
                               {"gatewayIdentifier": "intake-gw-abcdefghij", "targetId": "TGT0000001"})
        self.stub.add_response("list_gateway_targets", {"items": []}, {"gatewayIdentifier": "intake-gw-abcdefghij"})
        self.stub.add_response("delete_gateway", {"gatewayId": "intake-gw-abcdefghij", "status": "DELETING"}, {"gatewayIdentifier": "intake-gw-abcdefghij"})
        self.stub.add_client_error("get_gateway", "ResourceNotFoundException", expected_params={"gatewayIdentifier": "intake-gw-abcdefghij"})
        with redirect_stdout(io.StringIO()):
            ac.cmd_delete("intake")
        self.stub.assert_no_pending_responses()

    def test_tally_policy_engine_delete(self):
        self.stub.add_response("list_gateways", {"items": []}, {})
        self.stub.add_response("list_policy_engines", {"policyEngines": [
            {"policyEngineId": "tally_policies-abcd123456", "name": "TallyTools_tally_policies", "createdAt": NOW, "updatedAt": NOW, "policyEngineArn": "arn:p", "status": "ACTIVE"}]}, {})
        self.stub.add_response("list_policies", {"policies": [
            {"policyId": "allow_reads-abcd123456", "name": "allow_reads", "policyEngineId": "tally_policies-abcd123456", "createdAt": NOW, "updatedAt": NOW, "policyArn": "arn:p1", "status": "ACTIVE",
             "definition": {"cedar": {"statement": "permit(principal, action, resource);"}}}]}, {"policyEngineId": "tally_policies-abcd123456"})
        self.stub.add_response("delete_policy", {"policyId": "allow_reads-abcd123456", "name": "allow_reads", "policyEngineId": "tally_policies-abcd123456", "createdAt": NOW, "updatedAt": NOW,
                                                 "policyArn": "arn:p1", "status": "DELETING", "definition": {"cedar": {"statement": "x"}}},
                               {"policyEngineId": "tally_policies-abcd123456", "policyId": "allow_reads-abcd123456"})
        self.stub.add_response("list_policies", {"policies": []}, {"policyEngineId": "tally_policies-abcd123456"})
        self.stub.add_response("delete_policy_engine", {"policyEngineId": "tally_policies-abcd123456", "name": "TallyTools_tally_policies", "createdAt": NOW, "updatedAt": NOW,
                                                        "policyEngineArn": "arn:p", "status": "DELETING"}, {"policyEngineId": "tally_policies-abcd123456"})
        self.stub.add_response("list_policy_engines", {"policyEngines": []}, {})
        with redirect_stdout(io.StringIO()):
            ac.cmd_delete("tally")
        self.stub.assert_no_pending_responses()


class InvokeTests(unittest.TestCase):
    def test_invoke_request_shape_and_stream(self):
        session = boto3.session.Session(region_name="ap-southeast-1", aws_access_key_id="x", aws_secret_access_key="y")
        client = session.client("bedrock-agentcore")
        events = [
            {"messageStart": {"role": "assistant"}},
            {"contentBlockStart": {"contentBlockIndex": 1, "start": {"toolUse": {"toolUseId": "t1", "name": "kopi-api___place_order", "type": "tool_use"}}}},
            {"contentBlockDelta": {"contentBlockIndex": 2, "delta": {"text": "Done, one kopi-o for Aisha."}}},
            {"messageStop": {"stopReason": "end_turn"}},
        ]
        with mock.patch.object(client, "invoke_harness", return_value={"stream": events}) as call:
            text, tools, secs, stop = ac.invoke(client, HARNESS_ARN, "One kopi-o for me please.", actor="aisha", session="s" * 36)
        self.assertEqual(text, "Done, one kopi-o for Aisha.")
        self.assertEqual(tools, ["kopi-api___place_order"])
        self.assertEqual(stop, "end_turn")
        # Check the request we'd send against the real API model
        kwargs = call.call_args.kwargs
        model = client.meta.service_model.operation_model("InvokeHarness")
        from botocore.validate import validate_parameters
        validate_parameters(kwargs, model.input_shape)
        self.assertGreaterEqual(len(kwargs["runtimeSessionId"]), 33)

    def test_runtime_error_event_raises(self):
        with self.assertRaises(RuntimeError):
            client = mock.Mock()
            client.invoke_harness.return_value = {"stream": [{"runtimeClientError": {"message": "boom"}}]}
            ac.invoke(client, HARNESS_ARN, "hi", actor="a")


if __name__ == "__main__":
    unittest.main()
