#!/usr/bin/env python3
import os
import sys
import aws_cdk as cdk
from iac_stack import CovbChatbotStack

app = cdk.App()

# Get stack name from environment variable - required
env_name = os.environ.get("ENV_NAME")
if not env_name:
    print("ERROR: ENV_NAME environment variable is required!")
    print("Usage: export ENV_NAME=environment && cdk deploy")
    sys.exit(1)

stack_name = f"{env_name}-vb-chatbot"

CovbChatbotStack(app, stack_name,
    # Deploy to the customer's AWS account in Virginia
    env=cdk.Environment(account='152265074049', region='us-east-1'),
)

app.synth() 