"""
API Gateway Lambda function that handles chat requests and converts responses to Server-Sent Events (SSE).
"""
import json
import os
import boto3
from botocore.exceptions import ClientError

lambda_client = boto3.client('lambda', region_name=os.environ.get('AWS_REGION'))

CHAT_HANDLER_LAMBDA_ARN = os.environ.get('CHAT_HANDLER_LAMBDA_ARN')

# Extract function name from ARN
def get_function_name_from_arn(arn):
    """Extract function name from Lambda ARN"""
    if not arn:
        return None
    return arn.split(':')[-1]

CHAT_HANDLER_FUNCTION_NAME = get_function_name_from_arn(CHAT_HANDLER_LAMBDA_ARN)


def create_sse_response(data, event_type='message'):
    """Create a Server-Sent Event response"""
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


def handler(event, context):
    """Main Lambda handler function"""
    
    print(f"Received event: {json.dumps(event)}")
    print(f"CHAT_HANDLER_LAMBDA_ARN: {CHAT_HANDLER_LAMBDA_ARN}")
    print(f"CHAT_HANDLER_FUNCTION_NAME: {CHAT_HANDLER_FUNCTION_NAME}")
    
    try:
        # Parse the request body
        if event.get('body'):
            body = json.loads(event['body'])
        else:
            body = event
        
        user_message = body.get('message', '')
        session_id = body.get('sessionId', 'default-session')
        
        print(f"Processing message: '{user_message}' for session: {session_id}")
        
        if not CHAT_HANDLER_FUNCTION_NAME:
            raise Exception("CHAT_HANDLER_LAMBDA_ARN environment variable not set")
        
        # Prepare payload for chat-handler Lambda
        payload = {
            'inputTranscript': user_message,
            'sessionId': session_id,
        }
        
        print(f"Invoking chat-handler with payload: {json.dumps(payload)}")
        
        # Invoke the chat-handler Lambda
        response = lambda_client.invoke(
            FunctionName=CHAT_HANDLER_FUNCTION_NAME,
            InvocationType='RequestResponse',
            Payload=json.dumps(payload)
        )
        
        print(f"Chat-handler response status: {response['StatusCode']}")
        
        # Parse the response from chat-handler
        response_payload = json.loads(response['Payload'].read())
        print(f"Chat-handler response payload: {json.dumps(response_payload)}")
        
        # Extract the bot response
        if 'messages' in response_payload and response_payload['messages']:
            bot_message = response_payload['messages'][0]['content']
        else:
            bot_message = "I'm sorry, I couldn't process your request."
        
        print(f"Bot response: {bot_message}")
        
        # Convert the response to SSE format for streaming
        sse_data = {
            'type': 'message',
            'content': bot_message,
            'sessionId': session_id
        }
        
        sse_response = create_sse_response(sse_data)
        
        # Return the SSE response
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'text/event-stream',
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type',
                'Access-Control-Allow-Methods': 'POST, OPTIONS',
            },
            'body': sse_response
        }
        
    except Exception as error:
        print(f"Error in chat-api: {error}")
        
        # Return error as SSE
        error_data = {
            'type': 'error',
            'content': 'I\'m sorry, I encountered a technical issue. Please try again later.',
            'sessionId': session_id if 'session_id' in locals() else 'unknown'
        }
        
        sse_response = create_sse_response(error_data, 'error')
        
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'text/event-stream',
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type',
                'Access-Control-Allow-Methods': 'POST, OPTIONS',
            },
            'body': sse_response
        } 