# query_data.py
import json
import boto3
import os
import logging
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key, Attr

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
s3_client = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')
athena_client = boto3.client('athena')

# Get environment variables
S3_BUCKET = os.environ.get('S3_BUCKET')
DYNAMODB_TABLE = os.environ.get('DYNAMODB_TABLE')

# Initialize DynamoDB table
metadata_table = dynamodb.Table(DYNAMODB_TABLE)

def lambda_handler(event, context):
    """
    Lambda function to query data from the data lake.
    
    Supports different query types:
    1. Metadata lookup by ID
    2. Metadata search by data type, date range, tags, etc.
    3. Content retrieval from S3
    4. Athena SQL queries for complex analytics
    """
    try:
        logger.info("Received event: {}".format(json.dumps(event)))
        
        # Extract query parameters
        if 'queryStringParameters' in event and event['queryStringParameters']:
            query_params = event['queryStringParameters']
        elif 'body' in event and event['body']:
            try:
                body = json.loads(event['body'])
                query_params = body.get('query', {})
            except:
                query_params = {}
        else:
            query_params = {}
        
        # Determine query type
        query_type = query_params.get('type', 'metadata')
        
        if query_type == 'id':
            # Lookup by specific ID
            result = query_by_id(query_params.get('id'))
        
        elif query_type == 'metadata':
            # Search metadata based on criteria
            result = search_metadata(query_params)
        
        elif query_type == 'content':
            # Retrieve actual content from S3
            result = get_content(query_params.get('id'))
        
        elif query_type == 'sql':
            # Execute SQL query via Athena
            result = execute_sql_query(query_params.get('sql'))
        
        else:
            raise ValueError(f"Unsupported query type: {query_type}")
        
        # Return results
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(result)
        }
    
    except ClientError as e:
        logger.error(f"AWS error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'success': False,
                'message': f"AWS error: {str(e)}"
            })
        }
    except Exception as e:
        logger.error(f"Error processing query: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'success': False,
                'message': f"Error processing query: {str(e)}"
            })
        }

def query_by_id(data_id):
    """Query metadata by specific ID"""
    if not data_id:
        raise ValueError("ID parameter is required")
    
    response = metadata_table.get_item(Key={'id': data_id})
    
    if 'Item' not in response:
        return {
            'success': False,
            'message': f"No item found with ID: {data_id}"
        }
    
    return {
        'success': True,
        'metadata': response['Item']
    }

def search_metadata(params):
    """
    Search metadata based on different criteria
    Supports: dataType, dateRange, owner, source, tags
    """
    filter_expression = None
    
    # Build filter expression based on provided parameters
    if 'dataType' in params:
        filter_expression = Attr('dataType').eq(params['dataType'])
    
    if 'owner' in params:
        owner_expr = Attr('owner').eq(params['owner'])
        filter_expression = owner_expr if filter_expression is None else filter_expression & owner_expr
    
    if 'source' in params:
        source_expr = Attr('source').eq(params['source'])
        filter_expression = source_expr if filter_expression is None else filter_expression & source_expr
    
    if 'fromDate' in params and 'toDate' in params:
        date_expr = Attr('timestamp').between(params['fromDate'], params['toDate'])
        filter_expression = date_expr if filter_expression is None else filter_expression & date_expr
    
    if 'tags' in params:
        for tag in params['tags']:
            tag_expr = Attr('tags').contains(tag)
            filter_expression = tag_expr if filter_expression is None else filter_expression & tag_expr
    
    # Execute the query
    if filter_expression:
        response = metadata_table.scan(FilterExpression=filter_expression)
    else:
        # If no filters provided, return a limited set of most recent items
        response = metadata_table.scan(Limit=20)
    
    return {
        'success': True,
        'count': response['Count'],
        'items': response['Items']
    }

def get_content(data_id):
    """Retrieve the actual data content from S3 based on ID"""
    if not data_id:
        raise ValueError("ID parameter is required")
    
    # First, get metadata to find S3 location
    response = metadata_table.get_item(Key={'id': data_id})
    
    if 'Item' not in response:
        return {
            'success': False,
            'message': f"No item found with ID: {data_id}"
        }
    
    metadata = response['Item']
    
    # Parse S3 location
    s3_location = metadata['s3Location']
    if s3_location.startswith('s3://'):
        s3_location = s3_location[5:]  # Remove s3:// prefix
    
    parts = s3_location.split('/', 1)
    bucket = parts[0]
    key = parts[1]
    
    # Get object from S3
    response = s3_client.get_object(Bucket=bucket, Key=key)
    content = response['Body'].read().decode('utf-8')
    
    return {
        'success': True,
        'metadata': metadata,
        'content': json.loads(content)
    }

def execute_sql_query(sql_query):
    """Execute SQL query via Athena"""
    if not sql_query:
        raise ValueError("SQL query is required")
    
    # Start Athena query execution
    response = athena_client.start_query_execution(
        QueryString=sql_query,
        ResultConfiguration={
            'OutputLocation': f"s3://{S3_BUCKET}/athena-results/"
        }
    )
    
    query_execution_id = response['QueryExecutionId']
    
    # For simplicity, we're returning the execution ID
    # A real implementation would handle waiting for results
    # or implement an async pattern
    return {
        'success': True,
        'message': 'Query submitted to Athena',
        'queryExecutionId': query_execution_id,
        'note': 'Check Athena console for results or implement GetQueryResults in a follow-up call'
    }
