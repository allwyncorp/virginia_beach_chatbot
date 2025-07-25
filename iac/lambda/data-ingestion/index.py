import json
import boto3
import os

def handler(event, context):
    """
    Handle data ingestion events
    """
    print(f"Data ingestion event: {json.dumps(event)}")
    
    try:
        # Process the incoming data
        # This could be from S3, API Gateway, or other sources
        
        # Store processed data in DynamoDB
        dynamodb = boto3.resource('dynamodb')
        table = dynamodb.Table(os.environ['DATA_TABLE'])
        
        # Example processing - adapt based on your needs
        for record in event.get('Records', []):
            # Process each record
            processed_data = {
                'id': context.aws_request_id,
                'data': record,
                'timestamp': context.aws_request_id
            }
            
            table.put_item(Item=processed_data)
        
        return {
            'statusCode': 200,
            'body': json.dumps('Data processed successfully')
        }
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps('Failed to process data')
        }
