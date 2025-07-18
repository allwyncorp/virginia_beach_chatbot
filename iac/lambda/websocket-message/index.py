import json
import os
import time
import uuid
from datetime import datetime

import boto3
from botocore.exceptions import ClientError
from botocore.config import Config

AWS_REGION                   = os.environ["AWS_REGION"]                                   # provided by Lambda
CHAT_HISTORY_TABLE           = os.environ["CHAT_HISTORY_TABLE"]                           # covb‑chat‑history
WEBSOCKET_CONNECTIONS_TABLE  = os.environ["WEBSOCKET_CONNECTIONS_TABLE"]                  # covb‑websocket‑connections
BEDROCK_INFERENCE_PROFILE_ARN = os.environ["BEDROCK_INFERENCE_PROFILE_ID"]                # arn:aws:bedrock:us-east-1:152265074049:inference-profile/us.anthropic.claude-sonnet-4-20250514-v1:0
KENDRA_INDEX_ID              = os.environ.get("KENDRA_INDEX_ID", "")                      # 955dcb11-48e6-45c5-abf0-101ad1f97092
PROCESSED_DATA_BUCKET        = os.environ.get("PROCESSED_DATA_BUCKET", "")                # covb-processed-data-v2-152265074049

#AWS clients
dynamodb       = boto3.resource("dynamodb", region_name=AWS_REGION)
bedrock_client = boto3.client(
    "bedrock-runtime",
    region_name=AWS_REGION,
    config=Config(user_agent_extra="Anthropic-Version=2023-05-31")
)
kendra_client  = boto3.client("kendra", region_name=AWS_REGION)

chat_history_table = dynamodb.Table(CHAT_HISTORY_TABLE)
connections_table  = dynamodb.Table(WEBSOCKET_CONNECTIONS_TABLE)


def send_websocket_message(connection_id, message_data, endpoint_url):
    """Send over WebSocket; skip if connectionId is invalid."""
    client = boto3.client(
        "apigatewaymanagementapi",
        region_name=AWS_REGION,
        endpoint_url=endpoint_url
    )
    try:
        client.post_to_connection(ConnectionId=connection_id,
                                  Data=json.dumps(message_data))
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") == "BadRequestException":
            print(f"[WARN] Invalid connectionId {connection_id}, skipping")
        else:
            print(f"Error sending WebSocket message: {e}")
            raise

def should_retrieve_knowledge(user_message: str) -> bool:
    """Use Claude Sonnet 4 to classify if Kendra lookup is needed."""
    prompt = (
        f"Human: You are a classifier that determines whether a user's question "
        f"requires retrieving specific knowledge from a KB.\n\n"
        f"Question: \"{user_message}\"\n\n"
        f"Respond only with \"true\" or \"false\".\nAssistant:"
    )
    try:
        resp = bedrock_client.invoke_model(
            modelId=BEDROCK_INFERENCE_PROFILE_ARN,
            contentType="application/json",
            accept="application/json",
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 10,
                "temperature": 0.1,
                "top_k": 1,
                "top_p": 1,
                "stop_sequences": ["\n\nHuman:", "\nHuman:", "Human:"]
            })
        )
        body = json.loads(resp["body"].read())
        text = (body.get("content") or [{"text": body.get("completion", "")}])[0]["text"].strip()
        return text.lower() == "true"
    except Exception as e:
        print(f"Error in should_retrieve_knowledge: {e}")
        return True

def search_kendra(user_message: str):
    """Query Kendra and return context snippets + citations."""
    if not KENDRA_INDEX_ID:
        return []
    try:
        resp = kendra_client.query(
            IndexId=KENDRA_INDEX_ID,
            QueryText=user_message,
            PageSize=5,
            AttributeFilter={
                "EqualsTo": {
                    "Key": "_language_code",
                    "Value": {"StringValue": "en"}
                }
            }
        )
        snippets, citations = [], []
        for item in resp.get("ResultItems", []):
            text = item.get("DocumentExcerpt", {}).get("Text")
            uri  = item.get("DocumentURI")
            title= item.get("DocumentTitle", {}).get("Text")
            if text:
                snippets.append(text)
            if uri and title:
                citations.append({"title": title, "url": uri})
        return [{"content": "\n\n".join(snippets), "citations": citations}] if snippets else []
    except Exception as e:
        print(f"Error searching Kendra: {e}")
        return []

def stream_response_with_context(connection_id, user_message, context_snippets, endpoint_url):
    """Stream a Bedrock completion with Kendra context via WebSocket."""
    if context_snippets:
        combined  = "\n\n".join(s["content"] for s in context_snippets)
        citations = [c for s in context_snippets for c in s.get("citations", [])]
        prompt    = (
            f"Human: Use only the provided context to answer.\n\n"
            f"Question: {user_message}\n\n"
            f"Context:\n{combined}\n\n"
            f"Assistant:"
        )
    else:
        citations = []
        prompt    = (
            f"Human: No context found.\n\n"
            f"Question: {user_message}\n\n"
            f"Assistant:"
        )

    try:
        send_websocket_message(connection_id, {"type":"stream_start","message":"Starting..."}, endpoint_url)

        stream = bedrock_client.invoke_model_with_response_stream(
            modelId=BEDROCK_INFERENCE_PROFILE_ARN,
            contentType="application/json",
            accept="application/json",
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "messages": [{"role":"user","content":prompt}],
                "max_tokens": 4000,
                "temperature": 0.5,
                "top_k": 250,
                "top_p": 1,
                "stop_sequences": ["\n\nHuman:", "\nHuman:", "Human:"]
            })
        )

        full, count = "", 0
        for event in stream["body"]:
            chunk = json.loads(event["chunk"]["bytes"].decode())
            if chunk.get("type") == "content_block_delta":
                text = chunk["delta"].get("text","")
                full += text
                count += 1
                send_websocket_message(connection_id, {
                    "type": "stream_chunk",
                    "content": text,
                    "chunk_number": count
                }, endpoint_url)
                time.sleep(0.05)

        send_websocket_message(connection_id, {
            "type": "stream_complete",
            "full_response": full,
            "total_chunks": count,
            "citations": citations
        }, endpoint_url)
        return full.strip()

    except Exception as e:
        print(f"Error in stream_response_with_context: {e}")
        send_websocket_message(connection_id, {
            "type": "stream_error",
            "error": "Technical issue, please try again later."
        }, endpoint_url)
        return "Sorry, an error occurred."

def stream_general_response(connection_id, user_message, endpoint_url):
    """Stream a general Bedrock completion (no Kendra)."""
    prompt = (
        f"Human: You are a helpful assistant.\n\n"
        f"Question: {user_message}\n\n"
        f"Assistant:"
    )
    try:
        send_websocket_message(connection_id, {"type":"stream_start","message":"Starting..."}, endpoint_url)

        stream = bedrock_client.invoke_model_with_response_stream(
            modelId=BEDROCK_INFERENCE_PROFILE_ARN,
            contentType="application/json",
            accept="application/json",
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "messages": [{"role":"user","content":prompt}],
                "max_tokens": 4000,
                "temperature": 0.7,
                "top_k": 250,
                "top_p": 1,
                "stop_sequences": ["\n\nHuman:", "\nHuman:", "Human:"]
            })
        )
        full, count = "", 0
        for event in stream["body"]:
            chunk = json.loads(event["chunk"]["bytes"].decode())
            if chunk.get("type") == "content_block_delta":
                text = chunk["delta"].get("text","")
                full += text
                count += 1
                send_websocket_message(connection_id, {
                    "type":"stream_chunk","content":text,"chunk_number":count
                }, endpoint_url)
                time.sleep(0.05)

        send_websocket_message(connection_id, {
            "type":"stream_complete","full_response":full,"total_chunks":count
        }, endpoint_url)
        return full.strip()

    except Exception as e:
        print(f"Error in stream_general_response: {e}")
        send_websocket_message(connection_id, {
            "type":"stream_error","error":"Technical issue, please try again later."
        }, endpoint_url)
        return "Sorry, an error occurred."

def save_chat_history(session_id, user_message, bot_response):
    """Save conversation to DynamoDB with 24h TTL."""
    try:
        ts  = datetime.utcnow().isoformat()
        ttl = int(time.time()) + 24*3600
        chat_history_table.put_item(Item={
            "sessionId": session_id,
            "timestamp": ts,
            "userMessage": user_message,
            "botResponse": bot_response,
            "messageId": str(uuid.uuid4()),
            "ttl": ttl
        })
    except Exception as e:
        print(f"Error saving chat history: {e}")

# ─── Lambda handler ────────────────────────────────────────────────────────────

def handler(event, context):
    print("Event:", json.dumps(event))
    try:
        rc            = event["requestContext"]
        connection_id = rc["connectionId"]
        endpoint_url  = f"https://{rc['domainName']}/{rc['stage']}"

        body         = json.loads(event.get("body","{}"))
        user_message = body.get("message","")
        session_id   = body.get("sessionId", f"session-{connection_id}")

        if not user_message:
            send_websocket_message(connection_id, {"type":"error","error":"No message provided"}, endpoint_url)
            return {"statusCode":400}

        send_websocket_message(connection_id, {"type":"message_received","message":"Processing..."}, endpoint_url)

        if should_retrieve_knowledge(user_message):
            snippets     = search_kendra(user_message)
            bot_response = stream_response_with_context(connection_id, user_message, snippets, endpoint_url)
        else:
            bot_response = stream_general_response(connection_id, user_message, endpoint_url)

        save_chat_history(session_id, user_message, bot_response)
        return {"statusCode":200}

    except Exception as e:
        print(f"Handler error: {e}")
        try:
            send_websocket_message(connection_id,{"type":"error","error":"Internal server error."},endpoint_url)
        except:
            pass
        return {"statusCode":500}
