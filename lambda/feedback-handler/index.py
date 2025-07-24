import os
import json
import uuid
import boto3
from datetime import datetime

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["FEEDBACK_TABLE"])

def handler(event, context):
    route_key = event.get("requestContext", {}).get("routeKey")
    connection_id = event["requestContext"]["connectionId"]

    if route_key == "$connect":
        return {"statusCode": 200}

    elif route_key == "$disconnect":
        return {"statusCode": 200}

    elif route_key == "submitFeedback":
        try:
            body = json.loads(event.get("body", "{}"))
            data = body.get("data", {})

            feedback_raw = data.get("feedback")
            feedback_cleaned = (
                "positive" if feedback_raw == "up" else
                "negative" if feedback_raw == "down" else
                "unknown"
            )

            feedback_id = str(uuid.uuid4())
            item = {
                "FeedbackId": feedback_id,
                #"SessionId": data.get("sessionId", "unknown"),
                #"ResponseId": data.get("responseId", "unknown"),
                "MessageText": data.get("messageText", ""),
                "Feedback": feedback_cleaned,
                "Timestamp": datetime.utcnow().isoformat(),
                #"ConnectionId": connection_id,
            }

            table.put_item(Item=item)

            return {
                "statusCode": 200,
                "body": json.dumps({"success": True})
            }

        except Exception as e:
            print("Error:", e)
            return {
                "statusCode": 500,
                "body": json.dumps({"error": str(e)})
            }

    return {"statusCode": 400, "body": "Unsupported route"}
