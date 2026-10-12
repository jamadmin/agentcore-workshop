#!/usr/bin/env node
import { App, Tags } from 'aws-cdk-lib';
import { BackendsStack } from '../lib/backends-stack';

const app = new App();
const stack = new BackendsStack(app, 'AgentCoreWorkshopBackends', {
  env: { account: process.env.CDK_DEFAULT_ACCOUNT, region: process.env.CDK_DEFAULT_REGION ?? 'us-west-2' },
  description: 'Sample APIs for the AgentCore workshop (Kopi Run, Tally, Intake). Synthetic data only.',
});
Tags.of(stack).add('project', 'agentcore-workshop');
