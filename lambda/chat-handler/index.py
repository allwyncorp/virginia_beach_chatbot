"""
This is the central handler for the chatbot. It receives events from Amazon Lex,
orchestrates calls to Kendra and Bedrock, and manages conversation state in DynamoDB.
"""
import json
import os
import boto3
from botocore.exceptions import ClientError

# Initialize AWS clients
kendra_client = boto3.client('kendra', region_name=os.environ.get('AWS_REGION'))
bedrock_client = boto3.client('bedrock-runtime', region_name=os.environ.get('AWS_REGION'))

KENDRA_INDEX_ID = os.environ.get('KENDRA_INDEX_ID')
BEDROCK_MODEL_ID = os.environ.get('BEDROCK_MODEL_ID')

# Check if Kendra is configured
KENDRA_ENABLED = KENDRA_INDEX_ID and KENDRA_INDEX_ID != ''

# TEMPORARY for TESTING 
FAKE_KENDRA_CONTEXT = """
Parking is available in the 25th Street Municipal Garage, located at 209 25th St, Virginia Beach, VA 23451.
The garage is open 24 hours a day, 7 days a week. The rate is $2.00 per hour, with a daily maximum of $20.00.
Special event parking rates may apply. Payment can be made via credit card at the exit gate.
Overnight parking is permitted.
"""



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
        return [FAKE_KENDRA_CONTEXT.strip()]
    
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


def generate_response_with_context(user_message, context_snippets):
    """Generate response using Bedrock with context"""
    if context_snippets:
        context = '\n\n'.join(context_snippets)
        prompt = f"""
Human: You are a helpful assistant for the City of Virginia Beach. Use the following excerpts from the official city website to answer the user's question. Do not use any other information. If the answer is not in the excerpts, say "I'm sorry, I couldn't find information about that on the city's website."

Here is the user's question:
<question>
{user_message}
</question>

Here are the relevant excerpts from the website:
<context>
{context}
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

        bedrock_response = bedrock_client.invoke_model(**bedrock_params)
        response_body = json.loads(bedrock_response['body'].read())
        generated_text = response_body['completion']

        print(f'Bedrock generated response: {generated_text}')
        return generated_text.strip()
        
    except Exception as error:
        print(f"Error generating response with context: {error}")
        return "I'm sorry, I encountered a technical issue. Please try again later."


def generate_general_response(user_message):
    """Generate general response without knowledge retrieval"""
    prompt = f"""
Human: You are a helpful and friendly assistant for the City of Virginia Beach. The user has asked a general question that doesn't require specific city knowledge. Respond in a helpful, conversational manner as a city representative.

Here is the user's question:
<question>
{user_message}
</question>

Assistant:"""

    try:
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

        bedrock_response = bedrock_client.invoke_model(**bedrock_params)
        response_body = json.loads(bedrock_response['body'].read())
        generated_text = response_body['completion']

        print(f'Bedrock generated general response: {generated_text}')
        return generated_text.strip()
        
    except Exception as error:
        print(f"Error generating general response: {error}")
        return "I'm sorry, I encountered a technical issue. Please try again later."


def handler(event, context):
    """Main Lambda handler function"""

    user_message = event.get('inputTranscript')
    session_id = event.get('sessionId')

    try:
        # Step 1: Determine if knowledge retrieval is needed
        needs_knowledge = should_retrieve_knowledge(user_message)
        
        if needs_knowledge:
            # Step 2: Search Kendra for relevant information
            context_snippets = search_kendra(user_message)
            
            # Step 3: Generate response with context
            response = generate_response_with_context(user_message, context_snippets)
        else:
            # Step 4: Generate general response without knowledge retrieval
            response = generate_general_response(user_message)

        # Return the response in the format expected by the chat-api
        return {
            'messages': [
                {
                    'contentType': 'PlainText',
                    'content': response,
                },
            ],
        }

    except Exception as error:
        print(f"Error in chat handler: {error}")
        return {
            'messages': [
                {
                    'contentType': 'PlainText',
                    'content': "I'm sorry, I encountered a technical issue. Please try again later.",
                },
            ],
        }


def form_lex_response(event, message):
    """Format response for Amazon Lex"""
    return {
        'sessionState': {
            'dialogAction': {
                'type': 'Close',
            },
            'intent': {
                'name': event['sessionState']['intent']['name'],
                'state': 'Fulfilled',
            },
        },
        'messages': [
            {
                'contentType': 'PlainText',
                'content': message,
            },
        ],
    } 