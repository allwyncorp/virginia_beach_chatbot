"""
WebSocket connect handler for storing connection information in DynamoDB.
"""
import json
import os
import boto3
import time
from datetime import datetime
from botocore.exceptions import ClientError

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(os.environ['WEBSOCKET_CONNECTIONS_TABLE'])

def handler(event, context):
    """Handle WebSocket connection events"""
    
    print(f"WebSocket connect event: {json.dumps(event)}")
    
    connection_id = event['requestContext']['connectionId']
    
    try:
        # Store connection information in DynamoDB
        table.put_item(
            Item={
                'connectionId': connection_id,
                'timestamp': datetime.utcnow().isoformat(),  
                'ttl': int(time.time()) + 86400,  # 24 hours TTL (Unix timestamp required)
            }
        )
        
        print(f"Stored connection {connection_id} in DynamoDB")
        
        return {
            'statusCode': 200,
            'body': 'Connected'
        }
        
    except ClientError as e:
        print(f"Error storing connection: {e}")
        return {
            'statusCode': 500,
            'body': 'Failed to connect'
        }
