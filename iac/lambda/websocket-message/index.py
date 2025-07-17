"""
WebSocket message handler with real streaming from Bedrock.
"""
import json
import os
import boto3
import time
import uuid
from botocore.exceptions import ClientError
from botocore.config import Config
from datetime import datetime

# Initialize AWS clients
dynamodb = boto3.resource('dynamodb')
bedrock_client = boto3.client('bedrock-runtime', region_name=os.environ.get('AWS_REGION'))
kendra_client = boto3.client('kendra', region_name=os.environ.get('AWS_REGION'))
apigateway_client = boto3.client('apigatewaymanagementapi', region_name=os.environ.get('AWS_REGION'))

# Environment variables
CHAT_HISTORY_TABLE = os.environ.get('CHAT_HISTORY_TABLE')
WEBSOCKET_CONNECTIONS_TABLE = os.environ.get('WEBSOCKET_CONNECTIONS_TABLE')
BEDROCK_MODEL_ID = os.environ.get('BEDROCK_MODEL_ID', 'anthropic.claude-instant-v1')
KENDRA_INDEX_ID = os.environ.get('KENDRA_INDEX_ID')
PROCESSED_DATA_BUCKET = os.environ.get('PROCESSED_DATA_BUCKET')

# Initialize DynamoDB tables
chat_history_table = dynamodb.Table(CHAT_HISTORY_TABLE)
connections_table = dynamodb.Table(WEBSOCKET_CONNECTIONS_TABLE)

# Check if Kendra is configured
KENDRA_ENABLED = KENDRA_INDEX_ID and KENDRA_INDEX_ID != ''

# TEMPORARY for TESTING 
FAKE_KENDRA_CONTEXT_PARKING = {
    "content": """Parking is available in the 25th Street Municipal Garage, located at 209 25th St, Virginia Beach, VA 23451.

The garage is open 24 hours a day, 7 days a week. The rate is $2.00 per hour, with a daily maximum of $20.00.

Special event parking rates may apply. Payment can be made via credit card at the exit gate.

Overnight parking is permitted.""",
    "citations": [
        {
            "url": "https://pw.virginiabeach.gov/city-property/parking",
            "sourceTitle": "Municipal Parking Information"
        }
    ]
}

FAKE_KENDRA_CONTEXT_LIBRARY = {
    "content": """Library permits are required for hosting events at Virginia Beach Public Library facilities.

Applications must be submitted at least 30 days in advance and include a detailed event plan.

Permit fees vary based on room size and duration, ranging from $50-$200 per event.

Insurance requirements may apply for events with more than 50 attendees.""",
    "citations": [
        {
            "paragraph": 0,
            "url": "https://libraries.virginiabeach.gov/books-more/digital-library",
            "sourceTitle": "Library Event Permits"
        },
        {
            "paragraph": 2,
            "url": "https://libraries.virginiabeach.gov/library-account/pay-my-fines-fees",
            "sourceTitle": "Library Permit Fees"
        }
    ]
}

FAKE_KENDRA_CONTEXT_NO_CITATIONS = {
    "content": """This is general information about Virginia Beach services.

The city offers various programs and activities for residents.

Contact the city office for more details about specific services.""",
    "citations": []
}

def send_websocket_message(connection_id, message_data, endpoint_url):
    """Send message to WebSocket client"""
    try:
        # Create API Gateway client with the correct endpoint
        apigateway_client = boto3.client('apigatewaymanagementapi', 
                                        region_name=os.environ.get('AWS_REGION'),
                                        endpoint_url=endpoint_url)
        
        apigateway_client.post_to_connection(
            ConnectionId=connection_id,
            Data=json.dumps(message_data)
        )
        return True
    except Exception as e:
        print(f"Error sending WebSocket message: {e}")
        return False

def should_retrieve_knowledge(user_message):
    """Use LLM to determine if knowledge retrieval is needed"""
    prompt = f"""
Human: You are a classifier that determines if a user's question requires retrieving specific knowledge from a knowledge base about the City of Virginia Beach.

The knowledge base contains information about:
- City services and departments
- Local government procedures
- City ordinances and regulations
- Municipal facilities and locations
- City events and programs
- Local business information
- City contact information

Question: "{user_message}"

Respond with ONLY "true" if the question requires specific knowledge about City of Virginia Beach services, procedures, locations, or information that would be found in official city documents or knowledge base.

Respond with ONLY "false" if the question is:
- A general greeting (hi, hello, how are you)
- A general conversation starter
- A question that doesn't require specific city knowledge
- A question that can be answered with general knowledge

Assistant:"""

    try:
        bedrock_params = {
            'modelId': BEDROCK_MODEL_ID,
            'contentType': 'application/json',
            'accept': 'application/json',
            'body': json.dumps({
                'prompt': prompt,
                'max_tokens_to_sample': 10,
                'temperature': 0.1,
                'top_k': 1,
                'top_p': 1,
                'stop_sequences': ['\n\nHuman:', '\nHuman:', 'Human:', '\n\n', '\n'],
            }),
        }

        bedrock_response = bedrock_client.invoke_model(**bedrock_params)
        response_body = json.loads(bedrock_response['body'].read())
        result = response_body['completion'].strip().lower()
        
        print(f"Knowledge retrieval decision for '{user_message}': {result}")
        return result == 'true'
        
    except Exception as error:
        print(f"Error in knowledge retrieval decision: {error}")
        # Default to true if there's an error
        return True

def search_kendra(user_message):
    """Search Kendra for relevant information"""
    if not KENDRA_ENABLED:
        print("Kendra is not configured; using FAKE_KENDRA_CONTEXT for testing")
        
        # Return different contexts based on the user's question
        user_message_lower = user_message.lower()
        
        if 'parking' in user_message_lower:
            print("Using parking context with 1 citation")
            return [FAKE_KENDRA_CONTEXT_PARKING]
        elif 'library' in user_message_lower or 'permit' in user_message_lower:
            print("Using library context with 2 citations")
            return [FAKE_KENDRA_CONTEXT_LIBRARY]
        else:
            print("Using general context with no citations")
            return [FAKE_KENDRA_CONTEXT_NO_CITATIONS]
    
    try:
        print(f'Querying Kendra with message: "{user_message}"')
        kendra_params = {
            'IndexId': KENDRA_INDEX_ID,
            'QueryText': user_message,
        }
        kendra_response = kendra_client.query(**kendra_params)
        print(f'Kendra Response: {json.dumps(kendra_response, indent=2)}')

        context_snippets = []
        if kendra_response.get('ResultItems'):
            for item in kendra_response['ResultItems']:
                if item.get('DocumentExcerpt', {}).get('Text'):
                    context_snippets.append(item['DocumentExcerpt']['Text'])
        
        return context_snippets
        
    except Exception as error:
        print(f"Error searching Kendra: {error}")
        return []

def stream_response_with_context(connection_id, user_message, context_snippets, endpoint_url):
    """Stream response using Bedrock with context"""
    if context_snippets:
        # Handle structured context with citations
        citations = []
        context_text = ""
        
        for snippet in context_snippets:
            if isinstance(snippet, dict) and 'content' in snippet and 'citations' in snippet:
                # Structured context with citations
                print(f"Found structured snippet with citations: {snippet['citations']}")
                context_text += snippet['content'] + "\n\n"
                citations.extend(snippet['citations'])
            else:
                # Plain text context
                print("Found plain text snippet")
                context_text += str(snippet) + "\n\n"
        
        context_text = context_text.strip()
        print(f"Final context_text length: {len(context_text)}")
        print(f"Final citations: {citations}")
        
        prompt = f"""
Human: You are a professional assistant for the City of Virginia Beach. Answer the user's question using only the provided information from the city's official sources. Provide clear, concise, and professional responses without mentioning "excerpts" or "based on excerpts." If the information is not available in the provided context, politely inform them that you don't have specific information about that topic and suggest contacting the city directly.

Here is the user's question:
<question>
{user_message}
</question>

Here is the relevant information from the city's official sources:
<context>
{context_text}
</context>

Assistant:"""
    else:
        prompt = f"""
Human: You are a helpful assistant for the City of Virginia Beach. The user asked a question that should be answered using city knowledge, but no relevant information was found in the knowledge base.

Here is the user's question:
<question>
{user_message}
</question>

Please respond that you couldn't find specific information about this topic in the city's knowledge base and suggest they contact the city directly or visit the website.

Assistant:"""

    try:
        # Use Bedrock streaming API
        bedrock_params = {
            'modelId': BEDROCK_MODEL_ID,
            'contentType': 'application/json',
            'accept': 'application/json',
            'body': json.dumps({
                'prompt': prompt,
                'max_tokens_to_sample': 4000,
                'temperature': 0.5,
                'top_k': 250,
                'top_p': 1,
                'stop_sequences': ['\n\nHuman:'],
            }),
        }

        # Send start message
        send_websocket_message(connection_id, {
            'type': 'stream_start',
            'message': 'Starting response generation...'
        }, endpoint_url)

        # Invoke Bedrock with streaming
        response = bedrock_client.invoke_model_with_response_stream(**bedrock_params)
        
        full_response = ""
        chunk_count = 0
        
        for event in response['body']:
            chunk = json.loads(event['chunk']['bytes'].decode())
            
            if 'completion' in chunk:
                completion = chunk['completion']
                full_response += completion
                chunk_count += 1
                
                # Send chunk to WebSocket client
                send_websocket_message(connection_id, {
                    'type': 'stream_chunk',
                    'content': completion,
                    'chunk_number': chunk_count
                }, endpoint_url)
                
                # Small delay to make streaming visible
                time.sleep(0.05)
        
        # Send completion message with citations if available
        completion_data = {
            'type': 'stream_complete',
            'full_response': full_response,
            'total_chunks': chunk_count
        }
        
        # Include citations in the response if available
        if citations:
            print(f"Including citations in response: {citations}")
            completion_data['full_response'] = json.dumps({
                'content': full_response,
                'citations': citations
            })
        else:
            print("No citations to include in response")
        
        send_websocket_message(connection_id, completion_data, endpoint_url)
        
        return full_response.strip()
        
    except Exception as error:
        print(f"Error streaming response with context: {error}")
        error_message = "I'm sorry, I encountered a technical issue. Please try again later."
        send_websocket_message(connection_id, {
            'type': 'stream_error',
            'error': error_message
        }, endpoint_url)
        return error_message

def stream_general_response(connection_id, user_message, endpoint_url):
    """Stream general response without knowledge retrieval"""
    prompt = f"""
Human: You are a professional assistant for the City of Virginia Beach. The user has asked a general question that doesn't require specific city knowledge. Respond in a helpful, professional manner as a city representative.

Here is the user's question:
<question>
{user_message}
</question>

Assistant:"""

    try:
        # Use Bedrock streaming API
        bedrock_params = {
            'modelId': BEDROCK_MODEL_ID,
            'contentType': 'application/json',
            'accept': 'application/json',
            'body': json.dumps({
                'prompt': prompt,
                'max_tokens_to_sample': 4000,
                'temperature': 0.7,
                'top_k': 250,
                'top_p': 1,
                'stop_sequences': ['\n\nHuman:'],
            }),
        }

        # Send start message
        send_websocket_message(connection_id, {
            'type': 'stream_start',
            'message': 'Starting response generation...'
        }, endpoint_url)

        # Invoke Bedrock with streaming
        response = bedrock_client.invoke_model_with_response_stream(**bedrock_params)
        
        full_response = ""
        chunk_count = 0
        
        for event in response['body']:
            chunk = json.loads(event['chunk']['bytes'].decode())
            
            if 'completion' in chunk:
                completion = chunk['completion']
                full_response += completion
                chunk_count += 1
                
                # Send chunk to WebSocket client
                send_websocket_message(connection_id, {
                    'type': 'stream_chunk',
                    'content': completion,
                    'chunk_number': chunk_count
                }, endpoint_url)
                
                # Small delay to make streaming visible
                time.sleep(0.05)
        
        # Send completion message
        send_websocket_message(connection_id, {
            'type': 'stream_complete',
            'full_response': full_response,
            'total_chunks': chunk_count
        }, endpoint_url)
        
        return full_response.strip()
        
    except Exception as error:
        print(f"Error streaming general response: {error}")
        error_message = "I'm sorry, I encountered a technical issue. Please try again later."
        send_websocket_message(connection_id, {
            'type': 'stream_error',
            'error': error_message
        }, endpoint_url)
        return error_message

def save_chat_history(session_id, user_message, bot_response):
    """Save chat history to DynamoDB"""
    try:
        # Human-readable timestamp for display
        timestamp = datetime.utcnow().isoformat()
        # Unix timestamp for TTL (required by DynamoDB)
        ttl = int(time.time()) + (24 * 60 * 60)  # 24 hours from now
        
        chat_history_table.put_item(
            Item={
                'sessionId': session_id,
                'timestamp': timestamp,
                'userMessage': user_message,
                'botResponse': bot_response,
                'messageId': str(uuid.uuid4()),
                'ttl': ttl,
            }
        )
        print(f"Saved chat history for session {session_id}")
    except Exception as e:
        print(f"Error saving chat history: {e}")

def handler(event, context):
    """Main WebSocket message handler"""
    
    print(f"WebSocket message event: {json.dumps(event)}")
    
    try:
        # Extract connection information
        connection_id = event['requestContext']['connectionId']
        endpoint_url = f"https://{event['requestContext']['domainName']}/{event['requestContext']['stage']}"
        
        # Parse the message
        body = json.loads(event['body'])
        user_message = body.get('message', '')
        session_id = body.get('sessionId', f'session-{connection_id}')
        
        print(f"Processing message: '{user_message}' for session: {session_id}")
        
        if not user_message:
            send_websocket_message(connection_id, {
                'type': 'error',
                'error': 'No message provided'
            }, endpoint_url)
            return {'statusCode': 400}
        
        # Send acknowledgment
        send_websocket_message(connection_id, {
            'type': 'message_received',
            'message': 'Processing your request...'
        }, endpoint_url)
        
        # Step 1: Determine if knowledge retrieval is needed
        needs_knowledge = should_retrieve_knowledge(user_message)
        print(f"Knowledge retrieval decision: {needs_knowledge}")
        
        # TEMPORARY: Force knowledge retrieval for testing citations
        if 'parking' in user_message.lower() or 'library' in user_message.lower() or 'permit' in user_message.lower():
            needs_knowledge = True
            print("Forcing knowledge retrieval for parking/library-related question")
        
        if needs_knowledge:
            # Step 2: Search Kendra for relevant information
            context_snippets = search_kendra(user_message)
            
            # Step 3: Stream response with context
            bot_response = stream_response_with_context(connection_id, user_message, context_snippets, endpoint_url)
        else:
            # Step 4: Stream general response without knowledge retrieval
            bot_response = stream_general_response(connection_id, user_message, endpoint_url)
        
        # Save chat history
        save_chat_history(session_id, user_message, bot_response)
        
        return {'statusCode': 200}
        
    except Exception as error:
        print(f"Error in WebSocket message handler: {error}")
        
        # Try to send error message to client
        try:
            connection_id = event['requestContext']['connectionId']
            endpoint_url = f"https://{event['requestContext']['domainName']}/{event['requestContext']['stage']}"
            
            send_websocket_message(connection_id, {
                'type': 'error',
                'error': 'I\'m sorry, I encountered a technical issue. Please try again later.'
            }, endpoint_url)
        except:
            pass
        
        return {'statusCode': 500}