"""
WebSocket disconnect handler for removing connection information from DynamoDB.
"""
import json
import os
import boto3
from botocore.exceptions import ClientError

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(os.environ['WEBSOCKET_CONNECTIONS_TABLE'])

def handler(event, context):
    """Handle WebSocket disconnection events"""
    
    print(f"WebSocket disconnect event: {json.dumps(event)}")
    
    connection_id = event['requestContext']['connectionId']
    
    try:
        # Remove connection information from DynamoDB
        table.delete_item(
            Key={
                'connectionId': connection_id
            }
        )
        
        print(f"Removed connection {connection_id} from DynamoDB")
        
        return {
            'statusCode': 200,
            'body': 'Disconnected'
        }
        
    except ClientError as e:
        print(f"Error removing connection: {e}")
        return {
            'statusCode': 500,
            'body': 'Failed to disconnect'
        }
