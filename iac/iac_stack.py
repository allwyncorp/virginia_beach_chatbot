#!/usr/bin/env python3
import os
import json
import aws_cdk as cdk
from aws_cdk import (
    Stack,
    aws_lambda as _lambda,
    aws_apigatewayv2 as apigatewayv2,
    aws_apigatewayv2_integrations as apigatewayv2_integrations,
    aws_dynamodb as dynamodb,
    aws_s3 as s3,
    aws_iam as iam,
    aws_logs as logs,
    aws_cloudfront as cloudfront,
    aws_cloudfront_origins as origins,
    aws_s3_deployment as s3_deployment,
    Duration,
    RemovalPolicy,
    CfnOutput,
)
from constructs import Construct


class CovbChatbotStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # S3 bucket for processed data
        self.processed_data_bucket = s3.Bucket(
            self, "ProcessedDataBucket",
            bucket_name=f"covb-processed-data-v2-{self.account}",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )

        # S3 bucket for UI hosting
        self.ui_bucket = s3.Bucket(
            self, "UIBucket",
            bucket_name=f"covb-ui-v2-{self.account}",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            public_read_access=True,
            block_public_access=s3.BlockPublicAccess(
                block_public_acls=False,
                block_public_policy=False,
                ignore_public_acls=False,
                restrict_public_buckets=False
            ),
            website_index_document="index.html",
            website_error_document="index.html",
        )

        # DynamoDB table for chat history
        self.chat_history_table = dynamodb.Table(
            self, "ChatHistoryTable",
            table_name="covb-chat-history",
            partition_key=dynamodb.Attribute(
                name="sessionId",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="timestamp",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
            time_to_live_attribute="ttl",
        )

        # DynamoDB table for WebSocket connections
        self.websocket_connections_table = dynamodb.Table(
            self, "WebSocketConnectionsTable",
            table_name="covb-websocket-connections",
            partition_key=dynamodb.Attribute(
                name="connectionId",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
            time_to_live_attribute="ttl",
        )

        # Common Lambda execution role
        lambda_role = iam.Role(
            self, "LambdaExecutionRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonBedrockFullAccess"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonKendraFullAccess"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonAPIGatewayInvokeFullAccess"),
            ]
        )

        # Add specific permissions
        lambda_role.add_to_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "dynamodb:GetItem",
                "dynamodb:PutItem",
                "dynamodb:UpdateItem",
                "dynamodb:DeleteItem",
                "dynamodb:Query",
                "dynamodb:Scan",
            ],
            resources=[
                self.chat_history_table.table_arn,
                self.websocket_connections_table.table_arn,
            ]
        ))

        lambda_role.add_to_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "s3:GetObject",
                "s3:PutObject",
                "s3:DeleteObject",
                "s3:ListBucket",
            ],
            resources=[
                self.processed_data_bucket.bucket_arn,
                f"{self.processed_data_bucket.bucket_arn}/*",
            ]
        ))

        # Add specific Bedrock permissions for Claude Sonnet 4
        lambda_role.add_to_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "bedrock:InvokeModel",
                "bedrock:InvokeModelWithResponseStream",
            ],
            resources=[
                "arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-sonnet-4-20250514-v1:0",
            ]
        ))

        # Create CloudWatch Logs role for the account
        cloudwatch_logs_role = iam.Role(
            self, "CloudWatchLogsRole",
            role_name="CloudWatchLogsRole",
            assumed_by=iam.ServicePrincipal("logs.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("CloudWatchLogsFullAccess"),
            ],
            description="Role for CloudWatch Logs to access Lambda log groups"
        )

        # Add CloudWatch Logs permissions to Lambda role
        lambda_role.add_to_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "logs:CreateLogGroup",
                "logs:CreateLogStream",
                "logs:PutLogEvents",
                "logs:DescribeLogGroups",
                "logs:DescribeLogStreams",
            ],
            resources=[
                f"arn:aws:logs:{self.region}:{self.account}:log-group:/aws/lambda/*",
                f"arn:aws:logs:{self.region}:{self.account}:log-group:/aws/lambda/*:*",
            ]
        ))



        # WebSocket Lambda functions
        websocket_connect_handler = _lambda.Function(
            self, "WebSocketConnectHandler",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="index.handler",
            code=_lambda.Code.from_asset("lambda/websocket-connect"),
            role=lambda_role,
            environment={
                "WEBSOCKET_CONNECTIONS_TABLE": self.websocket_connections_table.table_name,
            },
            timeout=Duration.seconds(30),
        )

        websocket_disconnect_handler = _lambda.Function(
            self, "WebSocketDisconnectHandler",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="index.handler",
            code=_lambda.Code.from_asset("lambda/websocket-disconnect"),
            role=lambda_role,
            environment={
                "WEBSOCKET_CONNECTIONS_TABLE": self.websocket_connections_table.table_name,
            },
            timeout=Duration.seconds(30),
        )

        websocket_message_handler = _lambda.Function(
            self, "WebSocketMessageHandler",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="index.handler",
            code=_lambda.Code.from_asset("lambda/websocket-message"),
            role=lambda_role,
            environment={
                "CHAT_HISTORY_TABLE": self.chat_history_table.table_name,
                "WEBSOCKET_CONNECTIONS_TABLE": self.websocket_connections_table.table_name,
                "BEDROCK_INFERENCE_PROFILE_ID": "arn:aws:bedrock:us-east-1:152265074049:inference-profile/us.anthropic.claude-sonnet-4-20250514-v1:0",
                "KENDRA_INDEX_ID": "955dcb11-48e6-45c5-abf0-101ad1f97092",
                "PROCESSED_DATA_BUCKET": self.processed_data_bucket.bucket_name,
            },
            timeout=Duration.seconds(300),  # 5 minutes for streaming
            memory_size=1024,
        )

        # Data ingestion Lambda
        data_ingestion_handler = _lambda.Function(
            self, "DataIngestionHandler",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="index.handler",
            code=_lambda.Code.from_asset("lambda/data-ingestion"),
            role=lambda_role,
            environment={
                "PROCESSED_DATA_BUCKET": self.processed_data_bucket.bucket_name,
            },
            timeout=Duration.seconds(900),  # 15 minutes
            memory_size=512,
        )

        # WebSocket API Gateway v2
        websocket_api = apigatewayv2.WebSocketApi(
            self, "WebSocketAPI",
            connect_route_options=apigatewayv2.WebSocketRouteOptions(
                integration=apigatewayv2_integrations.WebSocketLambdaIntegration(
                    "ConnectIntegration",
                    websocket_connect_handler
                )
            ),
            disconnect_route_options=apigatewayv2.WebSocketRouteOptions(
                integration=apigatewayv2_integrations.WebSocketLambdaIntegration(
                    "DisconnectIntegration",
                    websocket_disconnect_handler
                )
            ),
            default_route_options=apigatewayv2.WebSocketRouteOptions(
                integration=apigatewayv2_integrations.WebSocketLambdaIntegration(
                    "MessageIntegration",
                    websocket_message_handler
                )
            ),
        )

        websocket_stage = apigatewayv2.WebSocketStage(
            self, "WebSocketStage",
            web_socket_api=websocket_api,
            stage_name="prod",
            auto_deploy=True,
        )

        # Grant permissions to WebSocket Lambda functions
        websocket_connect_handler.add_permission(
            "WebSocketConnectPermission",
            principal=iam.ServicePrincipal("apigateway.amazonaws.com"),
            source_arn=f"arn:aws:execute-api:{self.region}:{self.account}:{websocket_api.api_id}/*",
        )

        websocket_disconnect_handler.add_permission(
            "WebSocketDisconnectPermission",
            principal=iam.ServicePrincipal("apigateway.amazonaws.com"),
            source_arn=f"arn:aws:execute-api:{self.region}:{self.account}:{websocket_api.api_id}/*",
        )

        websocket_message_handler.add_permission(
            "WebSocketMessagePermission",
            principal=iam.ServicePrincipal("apigateway.amazonaws.com"),
            source_arn=f"arn:aws:execute-api:{self.region}:{self.account}:{websocket_api.api_id}/*",
        )

        # Add specific permission for the Lambda to manage WebSocket connections
        websocket_message_handler.add_permission(
            "WebSocketManageConnectionsPermission",
            principal=iam.ServicePrincipal("apigateway.amazonaws.com"),
            source_arn=f"arn:aws:execute-api:{self.region}:{self.account}:{websocket_api.api_id}/*",
        )

        # Add WebSocket API Gateway permissions to Lambda role
        # This is the CORRECT configuration that should work
        lambda_role.add_to_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "execute-api:ManageConnections",
            ],
            resources=[
                f"arn:aws:execute-api:{self.region}:{self.account}:{websocket_api.api_id}/prod/POST/@connections/*",
            ]
        ))

        # CloudFront distribution for UI
        cloudfront_distribution = cloudfront.Distribution(
            self, "CloudFrontDistribution",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.S3Origin(self.ui_bucket),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                cache_policy=cloudfront.CachePolicy.CACHING_OPTIMIZED,
            ),
            error_responses=[
                cloudfront.ErrorResponse(
                    http_status=403,
                    response_http_status=200,
                    response_page_path="/index.html",
                ),
                cloudfront.ErrorResponse(
                    http_status=404,
                    response_http_status=200,
                    response_page_path="/index.html",
                ),
            ],
        )

        # Deploy UI to S3
        s3_deployment.BucketDeployment(
            self, "UIDeployment",
            sources=[s3_deployment.Source.asset("../ui/build")],
            destination_bucket=self.ui_bucket,
            distribution=cloudfront_distribution,
            distribution_paths=["/*"],
        )

        # Outputs
        CfnOutput(
            self, "WebSocketEndpoint",
            value=websocket_stage.url,
            description="WebSocket API Gateway endpoint",
        )

        CfnOutput(
            self, "CloudFrontURL",
            value=f"https://{cloudfront_distribution.distribution_domain_name}",
            description="CloudFront URL for the web interface",
        )

        CfnOutput(
            self, "UIBucketName",
            value=self.ui_bucket.bucket_name,
            description="S3 bucket name for UI hosting",
        )

        CfnOutput(
            self, "ChatHistoryTableName",
            value=self.chat_history_table.table_name,
            description="DynamoDB table name for chat history",
        )

        CfnOutput(
            self, "WebSocketConnectionsTableName",
            value=self.websocket_connections_table.table_name,
            description="DynamoDB table name for WebSocket connections",
        ) 