import json
import boto3
import os

def lambda_handler(event, context):
    try:
        body = json.loads(event['body'])
        message = body['message']
        session_id = body.get('sessionId', 'web-session')
        bot_id = os.environ['LEX_BOT_ID']
        bot_alias_id = os.environ['LEX_BOT_ALIAS_ID']
        region = os.environ.get('AWS_REGION', 'us-east-1')

        lex = boto3.client('lexv2-runtime', region_name=region)
        response = lex.recognize_text(
            botId=bot_id,
            botAliasId=bot_alias_id,
            localeId='en_US',
            sessionId=session_id,
            text=message
        )
        return {
            'statusCode': 200,
            'headers': {'Access-Control-Allow-Origin': '*'},
            'body': json.dumps(response)
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': {'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'error': str(e)})
        } 