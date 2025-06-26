import os
from aws_cdk import (
    Stack,
    Duration,
    RemovalPolicy,
    CfnOutput,
)
from constructs import Construct
import aws_cdk.aws_s3 as s3
import aws_cdk.aws_iam as iam
import aws_cdk.aws_lambda as lambda_
import aws_cdk.aws_events as events
import aws_cdk.aws_events_targets as targets
import aws_cdk.aws_dynamodb as dynamodb
import aws_cdk.aws_kendra as kendra
import aws_cdk.aws_lex as lex
import aws_cdk.aws_cloudfront as cloudfront
import aws_cdk.aws_s3_deployment as s3deploy
import aws_cdk.aws_cloudfront_origins as origins
import aws_cdk.aws_apigateway as apigateway
from aws_cdk.aws_apigateway import MockIntegration, IntegrationResponse, MethodResponse, PassthroughBehavior


class CovbChatbotStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # 1. Processed Data S3 Bucket
        processed_data_bucket = s3.Bucket(self, "CovbProcessedDataBucket",
            bucket_name=f"covb-processed-data-{self.account}",
            versioned=True,
            encryption=s3.BucketEncryption.S3_MANAGED,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )

        # 2. Data Ingestion Lambda IAM Role
        data_ingestion_lambda_role = iam.Role(self, "CovbDataIngestionLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole"),
            ],
        )
        processed_data_bucket.grant_write(data_ingestion_lambda_role)

        # 3. Data Ingestion Lambda Function
        data_ingestion_lambda = lambda_.Function(self, "CovbDataIngestionLambda",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="index.handler",
            code=lambda_.Code.from_asset(os.path.join(os.path.dirname(__file__), "../lambda/data-ingestion")),
            role=data_ingestion_lambda_role,
            environment={
                "PROCESSED_DATA_BUCKET": processed_data_bucket.bucket_name,
            },
            timeout=Duration.minutes(5),
        )

        # 4. Scheduled EventBridge Rule
        scheduled_crawl_rule = events.Rule(self, "CovbScheduledCrawlRule",
            schedule=events.Schedule.rate(Duration.days(1)),
        )
        scheduled_crawl_rule.add_target(targets.LambdaFunction(data_ingestion_lambda))

        # --- CHAT FLOW RESOURCES ---

        # 5. DynamoDB Table for Chat History (as per diagram)
        chat_history_table = dynamodb.Table(self, "CovbChatHistoryTable",
            partition_key=dynamodb.Attribute(name="SessionId", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
        )

        # --- KENDRA RESOURCES (TEMPORARILY DISABLED) ---
        """
        # 6. Kendra Index
        kendra_index = kendra.CfnIndex(self, "CovbKendraIndex",
            name="CovbVirginiaBeachIndex",
            edition="DEVELOPER_EDITION",
            role_arn=kendra_service_role.role_arn,
        )

        # 7. Kendra Data Source
        kendra_data_source = kendra.CfnDataSource(self, "CovbKendraDataSource",
            index_id=kendra_index.ref,
            name="CovbVirginiaBeachDataSource",
            type="S3",
            data_source_configuration={
                "s3Configuration": {
                    "bucketArn": data_bucket.bucket_arn,
                    "inclusionPrefixes": ["documents/"],
                },
            },
            role_arn=kendra_service_role.role_arn,
        )
        """

        # 8. Chat Handler Lambda Function
        chat_handler_lambda_role = iam.Role(self, "CovbChatHandlerLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
        )
        chat_handler_lambda_role.add_managed_policy(iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole"))
        
        # Grant DynamoDB permissions
        chat_history_table.grant_read_write_data(chat_handler_lambda_role)
        
        # Grant Bedrock permissions
        chat_handler_lambda_role.add_to_policy(iam.PolicyStatement(
            actions=["bedrock:InvokeModel"],
            resources=["*"],
        ))

        chat_handler_lambda = lambda_.Function(self, "CovbChatHandlerLambda",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="index.handler",
            code=lambda_.Code.from_asset(os.path.join(os.path.dirname(__file__), "../lambda/chat-handler")),
            role=chat_handler_lambda_role,
            timeout=Duration.seconds(30),
            environment={
                "CHAT_HISTORY_TABLE": chat_history_table.table_name,
                # "KENDRA_INDEX_ID": kendra_index.attr_id,  # Temporarily disabled
                "BEDROCK_MODEL_ID": "anthropic.claude-instant-v1",
            },
        )

        # 9. Lex Bot (as per diagram)
        lex_role = iam.Role(self, "CovbLexRole",
            assumed_by=iam.ServicePrincipal("lexv2.amazonaws.com"),
        )
        lex_role.add_to_policy(iam.PolicyStatement(
            actions=["lambda:InvokeFunction"],
            resources=[chat_handler_lambda.function_arn],
        ))

        fallback_intent = {
            "name": "FallbackIntent",
            "description": "Default fallback intent when no other intent is matched.",
            "parentIntentSignature": "AMAZON.FallbackIntent",
            "fulfillmentCodeHook": {
                "enabled": True
            }
        }

        dummy_intent = {
            "name": "DummyIntent",
            "description": "A dummy intent to satisfy Lex build requirements. Does not have a fulfillment hook.",
            "sampleUtterances": [{"utterance": "hello"}],
        }
        
        bot = lex.CfnBot(self, "CovbLexBot",
            name="CovbVirginiaBeachChatbot",
            role_arn=lex_role.role_arn,
            data_privacy={"ChildDirected": False},
            idle_session_ttl_in_seconds=300,
            bot_locales=[{
                "localeId": "en_US",
                "nluConfidenceThreshold": 0.40,
                "intents": [fallback_intent, dummy_intent],
                "voiceSettings": {
                    "voiceId": "Joanna" 
                }
            }],
        )

        # Create Bot Alias (required for Lex V2)
        bot_alias = lex.CfnBotAlias(self, "CovbLexBotAlias",
            bot_alias_name="LATEST",
            bot_id=bot.attr_id,
            bot_alias_locale_settings=[{
                "botAliasLocaleSetting": {
                    "enabled": True,
                    "codeHookSpecification": {
                        "lambdaCodeHook": {
                            "codeHookInterfaceVersion": "1.0",
                            "lambdaArn": chat_handler_lambda.function_arn
                        }
                    }
                },
                "localeId": "en_US"
            }]
        )

        # Grant Lex permission to invoke the Lambda
        chat_handler_lambda.add_permission("CovbLexPermission",
            principal=iam.ServicePrincipal("lexv2.amazonaws.com"),
            action="lambda:InvokeFunction",
            source_arn=f"arn:{self.partition}:lex:{self.region}:{self.account}:bot-alias/{bot.attr_id}/{bot_alias.attr_bot_alias_id}/*",
        )

        # --- Cfn Outputs ---
        CfnOutput(self, "CovbDataBucketNameOutput",
            value=processed_data_bucket.bucket_name,
            description="S3 Bucket for storing crawled data",
        )

        CfnOutput(self, "CovbChatHistoryTableNameOutput",
            value=chat_history_table.table_name,
            description="DynamoDB table for chat history",
        )

        CfnOutput(self, "CovbChatHandlerLambdaArnOutput",
            value=chat_handler_lambda.function_arn,
            description="Chat Handler Lambda ARN",
        )

        CfnOutput(self, "CovbLexBotNameOutput",
            value=bot.name,
            description="Lex Bot Name",
        )

        CfnOutput(self, "CovbLexBotIdOutput",
            value=bot.attr_id,
            description="Lex Bot ID",
        )

        CfnOutput(self, "CovbLexBotAliasIdOutput",
            value=bot_alias.attr_bot_alias_id,
            description="Lex Bot Alias ID",
        )

        # --- UI CREDENTIALS ---

        # 13. Create a dedicated IAM user for the UI
        ui_user = iam.User(self, "CovbUIAccessUser")

        # 14. Grant the user permission to talk to the Lex bot
        ui_user.add_to_policy(iam.PolicyStatement(
            actions=["lex:*"],
            resources=["*"],
        ))

        # 15. Create access keys for the user
        access_key = iam.CfnAccessKey(self, "CovbUIAccessKey",
            user_name=ui_user.user_name,
        )
        

        # 10. S3 Bucket for UI (Made public for testing)
        ui_bucket = s3.Bucket(self, "CovbUIBucket",
            website_index_document="index.html",
            public_read_access=True,
            block_public_access=s3.BlockPublicAccess(
                block_public_acls=False,
                block_public_policy=False,
                ignore_public_acls=False,
                restrict_public_buckets=False,
            ),
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )

        # 11. CloudFront Distribution
        distribution = cloudfront.Distribution(self, "CovbCloudFrontDistribution",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.S3Origin(ui_bucket),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
            ),
            default_root_object="index.html",
            error_responses=[
                cloudfront.ErrorResponse(
                    http_status=403,
                    response_http_status=200,
                    response_page_path="/index.html",
                    ttl=Duration.seconds(0)
                ),
                cloudfront.ErrorResponse(
                    http_status=404,
                    response_http_status=200,
                    response_page_path="/index.html",
                    ttl=Duration.seconds(0)
                )
            ]
        )

        # Deploy the actual UI from the ui/build folder (built React app)
        s3deploy.BucketDeployment(self, "CovbDeployUI",
            sources=[s3deploy.Source.asset(os.path.join(os.path.dirname(__file__), "../ui/build"))],
            destination_bucket=ui_bucket,
            distribution=distribution,
            distribution_paths=["/*"],
        )

        # Create a config file with Bot IDs for the UI
        config_content = f"""
{{
  "botId": "{bot.attr_id}",
  "botAliasId": "{bot_alias.attr_bot_alias_id}",
  "region": "{self.region}"
}}
"""
        
        # Deploy the config file
        s3deploy.BucketDeployment(self, "CovbDeployConfig",
            sources=[s3deploy.Source.data("config.json", config_content)],
            destination_bucket=ui_bucket,
            distribution=distribution,
            distribution_paths=["/config.json"],
        )

        CfnOutput(self, "CovbCloudFrontDistributionUrlOutput",
            value=f"https://{distribution.distribution_domain_name}",
            description="CloudFront Distribution URL for UI",
        )

        CfnOutput(self, "CovbUIBucketNameOutput",
            value=ui_bucket.bucket_name,
            description="S3 Bucket name for UI hosting",
        )

        CfnOutput(self, "CovbUIAccessKeyIdOutput",
            value=access_key.ref,
            description="Access Key ID for the UI user",
        )

        CfnOutput(self, "CovbUISecretAccessKeyOutput",
            value=access_key.attr_secret_access_key,
            description="Secret Access Key for the UI user",
        )

        # Temporarily disabled Kendra outputs
        """
        CfnOutput(self, "CovbKendraIndexIdOutput",
            value=kendra_index.attr_id,
            description="Kendra Index ID",
        )

        CfnOutput(self, "CovbKendraDataSourceIdOutput",
            value=kendra_data_source.attr_id,
            description="Kendra Data Source ID",
        )
        """

        chat_api_lambda = lambda_.Function(self, "CovbChatApiLambda",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="index.lambda_handler",
            code=lambda_.Code.from_asset(os.path.join(os.path.dirname(__file__), "../lambda/chat-api")),
            environment={
                "LEX_BOT_ID": bot.attr_id,
                "LEX_BOT_ALIAS_ID": bot_alias.attr_bot_alias_id,
            },
            timeout=Duration.seconds(30),
        )
        api = apigateway.LambdaRestApi(self, "CovbChatApi",
            handler=chat_api_lambda,
            proxy=False
        )
        chat_resource = api.root.add_resource("chat")
        chat_resource.add_method("POST")  # POST /chat
        chat_resource.add_method(
            "OPTIONS",
            MockIntegration(
                integration_responses=[
                    IntegrationResponse(
                        status_code="200",
                        response_parameters={
                            "method.response.header.Access-Control-Allow-Headers": "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'",
                            "method.response.header.Access-Control-Allow-Origin": "'*'",
                            "method.response.header.Access-Control-Allow-Methods": "'OPTIONS,POST'"
                        }
                    )
                ],
                passthrough_behavior=PassthroughBehavior.NEVER,
                request_templates={"application/json": "{\"statusCode\": 200}"}
            ),
            method_responses=[
                MethodResponse(
                    status_code="200",
                    response_parameters={
                        "method.response.header.Access-Control-Allow-Headers": True,
                        "method.response.header.Access-Control-Allow-Methods": True,
                        "method.response.header.Access-Control-Allow-Origin": True,
                    }
                )
            ]
        )
        CfnOutput(self, "CovbChatApiUrlOutput",
            value=api.url,
            description="API Gateway endpoint for chat",
        )

        chat_api_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=["lex:RecognizeText"],
                resources=[f"arn:aws:lex:{self.region}:{self.account}:bot-alias/{bot.attr_id}/{bot_alias.attr_bot_alias_id}"]
            )
        ) 