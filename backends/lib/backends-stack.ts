import * as path from 'path';
import { CfnOutput, Duration, RemovalPolicy, Stack, StackProps } from 'aws-cdk-lib';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as logs from 'aws-cdk-lib/aws-logs';
import { Construct } from 'constructs';

// Function names are fixed: env.sh, the scripts and the guide all look them up by name.
export class BackendsStack extends Stack {
  constructor(scope: Construct, id: string, props?: StackProps) {
    super(scope, id, props);

    const runTable = new dynamodb.Table(this, 'KopiRunTable', {
      tableName: 'agentcore-workshop-kopi-run',
      partitionKey: { name: 'pk', type: dynamodb.AttributeType.STRING },
      sortKey: { name: 'sk', type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: RemovalPolicy.DESTROY,
    });

    const creditsTable = new dynamodb.Table(this, 'TallyCreditsTable', {
      tableName: 'agentcore-workshop-tally-credits',
      partitionKey: { name: 'customer_id', type: dynamodb.AttributeType.STRING },
      sortKey: { name: 'credit_id', type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: RemovalPolicy.DESTROY,
    });

    const api = (name: string, dir: string, environment: Record<string, string> = {}) =>
      new lambda.Function(this, `${dir}Api`, {
        functionName: `agentcore-workshop-${name}-api`,
        runtime: lambda.Runtime.PYTHON_3_12,
        handler: 'handler.lambda_handler',
        code: lambda.Code.fromAsset(path.join(__dirname, '..', name), { exclude: ['__pycache__', '*.pyc'] }),
        timeout: Duration.seconds(15),
        memorySize: 256,
        environment,
        logGroup: new logs.LogGroup(this, `${dir}Logs`, {
          logGroupName: `/aws/lambda/agentcore-workshop-${name}-api`,
          retention: logs.RetentionDays.ONE_WEEK,
          removalPolicy: RemovalPolicy.DESTROY,
        }),
      });

    const kopi = api('kopi', 'Kopi', { RUN_TABLE: runTable.tableName });
    const tally = api('tally', 'Tally', { CREDITS_TABLE: creditsTable.tableName });
    const intake = api('intake', 'Intake');
    runTable.grantReadWriteData(kopi);
    creditsTable.grantReadWriteData(tally);

    new CfnOutput(this, 'KopiApiArn', { value: kopi.functionArn });
    new CfnOutput(this, 'TallyApiArn', { value: tally.functionArn });
    new CfnOutput(this, 'IntakeApiArn', { value: intake.functionArn });
  }
}
