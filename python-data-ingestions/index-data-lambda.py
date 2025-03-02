# index_data.py
import json
import boto3
import os
import logging
import requests
from requests_aws4auth import AWS4Auth
import datetime
import base64

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
s3_client = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')
session = boto3.Session()
credentials = session.get_credentials()
region = os.environ.get('AWS_REGION', 'us-east-1')

# Get environment variables
S3_BUCKET = os.environ.get('S3_BUCKET')
DYNAMODB_TABLE = os.environ.get('DYNAMODB_TABLE')
ES_ENDPOINT = os.environ.get('ES_ENDPOINT')

# Initialize DynamoDB table
metadata_table = dynamodb.Table(DYNAMODB_TABLE)

# Create AWS authentication for Elasticsearch
awsauth = AWS4Auth(
    credentials.access_key,
    credentials.secret_key,
    region,
    'es',
    session_token=credentials.token
)

def lambda_handler(event, context):
    """
    Lambda function to index data in Elasticsearch/OpenSearch.
    This function can be triggered by:
    1. S3 put events (automatically index new data)
    2. DynamoDB streams (index when metadata is updated)
    3. Direct API calls (for on-demand indexing)
    """
    try:
        logger.info("Received event: {}".format(json.dumps(event)))
        
        # Handle different event sources
        if 'Records' in event:
            # Process S3 or DynamoDB events
            for record in event['Records']:
                if 's3' in record:
                    # S3 event
                    bucket = record['s3']['bucket']['name']
                    key = record['s3']['object']['key']
                    index_s3_object(bucket, key)
                
                elif 'dynamodb' in record:
                    # DynamoDB stream event
                    if 'NewImage' in record['dynamodb']:
                        # Convert DynamoDB JSON to regular JSON
                        item = convert_dynamodb_to_json(record['dynamodb']['NewImage'])
                        index_metadata(item)
        
        elif 'body' in event:
            # Direct API call
            try:
                body = json.loads(event['body'])
                if 'id' in body:
                    # Index specific item by ID
                    return index_by_id(body['id'])
                elif 'dataType' in body:
                    # Bulk index by data type
                    return bulk_index_by_type(body['dataType'])
                else:
                    raise ValueError("Request must include 'id' or 'dataType'")
            except Exception as e:
                logger.error(f"Error processing API request: {str(e)}")
                return {
                    'statusCode': 400,
                    'body': json.dumps({
                        'success': False,
                        'message': f"Invalid request: {str(e)}"
                    })
                }
        
        else:
            # Direct invocation with specific parameters
            if 'id' in event:
                return index_by_id(event['id'])
            elif 'dataType' in event:
                return bulk_index_by_type(event['dataType'])
            elif 'reindexAll' in event and event['reindexAll']:
                return reindex_all()
            else:
                raise ValueError("Event must include 'id', 'dataType', or 'reindexAll'")
        
        # Return success for event-based triggers
        return {
            'statusCode': 200,
            'body': json.dumps({
                'success': True,
                'message': 'Indexing completed successfully'
            })
        }
    
    except Exception as e:
        logger.error(f"Error during indexing: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'success': False,
                'message': f"Indexing error: {str(e)}"
            })
        }

def index_s3_object(bucket, key):
    """Index a specific object from S3"""
    logger.info(f"Indexing S3 object: {bucket}/{key}")
    
    # Get the object from S3
    response = s3_client.get_object(Bucket=bucket, Key=key)
    content = response['Body'].read().decode('utf-8')
    
    # Parse the JSON content
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        logger.warning(f"Object is not JSON, skipping indexing: {bucket}/{key}")
        return
    
    # Extract file name (should be the data ID)
    file_name = os.path.basename(key)
    data_id = os.path.splitext(file_name)[0]
    
    # Get metadata from DynamoDB
    metadata_response = metadata_table.get_item(Key={'id': data_id})
    
    if 'Item' not in metadata_response:
        logger.warning(f"No metadata found for ID: {data_id}")
        metadata = {
            'id': data_id,
            's3Location': f"s3://{bucket}/{key}"
        }
    else:
        metadata = metadata_response['Item']
    
    # Combine metadata with data for indexing
    index_data = {
        'metadata': metadata,
        'content': data,
        'indexed_at': datetime.datetime.now().isoformat()
    }
    
    # Determine index name (use data type or default)
    data_type = metadata.get('dataType', 'unknown')
    index_name = f"data-{data_type}"
    
    # Index in Elasticsearch
    index_in_elasticsearch(index_name, data_id, index_data)
    
    # Update metadata to mark as indexed
    metadata_table.update_item(
        Key={'id': data_id},
        UpdateExpression="SET indexed = :indexed, indexedAt = :indexedAt",
        ExpressionAttributeValues={
            ':indexed': True,
            ':indexedAt': datetime.datetime.now().isoformat()
        }
    )
    
    logger.info(f"Successfully indexed S3 object: {bucket}/{key}")

def index_metadata(metadata):
    """Index metadata without retrieving content"""
    logger.info(f"Indexing metadata for ID: {metadata['id']}")
    
    # Determine index name (use data type or default)
    data_type = metadata.get('dataType', 'unknown')
    index_name = f"metadata-{data_type}"
    
    # Index in Elasticsearch
    index_in_elasticsearch(index_name, metadata['id'], metadata)
    
    logger.info(f"Successfully indexed metadata for ID: {metadata['id']}")

def index_by_id(data_id):
    """Index a specific item by ID"""
    logger.info(f"Indexing data for ID: {data_id}")
    
    # Get metadata from DynamoDB
    response = metadata_table.get_item(Key={'id': data_id})
    
    if 'Item' not in response:
        return {
            'statusCode': 404,
            'body': json.dumps({
                'success': False,
                'message': f"No item found with ID: {data_id}"
            })
        }
    
    metadata = response['Item']
    
    # Parse S3 location
    s3_location = metadata['s3Location']
    if s3_location.startswith('s3://'):
        s3_location = s3_location[5:]  # Remove s3:// prefix
    
    parts = s3_location.split('/', 1)
    bucket = parts[0]
    key = parts[1]
    
    # Get content from S3
    s3_response = s3_client.get_object(Bucket=bucket, Key=key)
    content = s3_response['Body'].read().decode('utf-8')
    
    # Combine metadata with content
    index_data = {
        'metadata': metadata,
        'content': json.loads(content),
        'indexed_at': datetime.datetime.now().isoformat()
    }
    
    # Determine index name
    data_type = metadata.get('dataType', 'unknown')
    index_name = f"data-{data_type}"
    
    # Index in Elasticsearch
    index_in_elasticsearch(index_name, data_id, index_data)
    
    # Update metadata
    metadata_table.update_item(
        Key={'id': data_id},
        UpdateExpression="SET indexed = :indexed, indexedAt = :indexedAt",
        ExpressionAttributeValues={
            ':indexed': True,
            ':indexedAt': datetime.datetime.now().isoformat()
        }
    )
    
    return {
        'statusCode': 200,
        'body': json.dumps({
            'success': True,
            'message': f"Successfully indexed data for ID: {data_id}"
        })
    }

def bulk_index_by_type(data_type):
    """Index all items of a specific data type"""
    logger.info(f"Bulk indexing data of type: {data_type}")
    
    # Query DynamoDB for items of this data type
    response = metadata_table.scan(
        FilterExpression="dataType = :dataType",
        ExpressionAttributeValues={":dataType": data_type}
    )
    
    items = response['Items']
    indexed_count = 0
    
    # Process each item
    for metadata in items:
        try:
            # Parse S3 location
            s3_location = metadata['s3Location']
            if s3_location.startswith('s3://'):
                s3_location = s3_location[5:]
            
            parts = s3_location.split('/', 1)
            bucket = parts[0]
            key = parts[1]
            
            # Get content from S3
            s3_response = s3_client.get_object(Bucket=bucket, Key=key)
            content = s3_response['Body'].read().decode('utf-8')
            
            # Combine metadata with content
            index_data = {
                'metadata': metadata,
                'content': json.loads(content),
                'indexed_at': datetime.datetime.now().isoformat()
            }
            
            # Index in Elasticsearch
            index_name = f"data-{data_type}"
            index_in_elasticsearch(index_name, metadata['id'], index_data)
            
            # Update metadata
            metadata_table.update_item(
                Key={'id': metadata['id']},
                UpdateExpression="SET indexed = :indexed, indexedAt = :indexedAt",
                ExpressionAttributeValues={
                    ':indexed': True,
                    ':indexedAt': datetime.datetime.now().isoformat()
                }
            )
            
            indexed_count += 1
        
        except Exception as e:
            logger.error(f"Error indexing item {metadata['id']}: {str(e)}")
    
    return {
        'statusCode': 200,
        'body': json.dumps({
            'success': True,
            'message': f"Bulk indexing completed",
            'totalItems': len(items),
            'indexedItems': indexed_count
        })
    }

def reindex_all():
    """Reindex all items in the data lake"""
    logger.info("Starting full reindexing of all data")
    
    # Scan DynamoDB for all items
    response = metadata_table.scan()
    items = response['Items']
    indexed_count = 0
    
    # Process items by data type for more efficient indexing
    data_types = {}
    for metadata in items:
        data_type = metadata.get('dataType', 'unknown')
        if data_type not in data_types:
            data_types[data_type] = []
        data_types[data_type].append(metadata)
    
    # Process each data type
    for data_type, type_items in data_types.items():
        logger.info(f"Reindexing {len(type_items)} items of type: {data_type}")
        
        for metadata in type_items:
            try:
                # Parse S3 location
                s3_location = metadata['s3Location']
                if s3_location.startswith('s3://'):
                    s3_location = s3_location[5:]
                
                parts = s3_location.split('/', 1)
                bucket = parts[0]
                key = parts[1]
                
                # Get content from S3
                s3_response = s3_client.get_object(Bucket=bucket, Key=key)
                content = s3_response['Body'].read().decode('utf-8')
                
                # Combine metadata with content
                index_data = {
                    'metadata': metadata,
                    'content': json.loads(content),
                    'indexed_at': datetime.datetime.now().isoformat()
                }
                
                # Index in Elasticsearch
                index_name = f"data-{data_type}"
                index_in_elasticsearch(index_name, metadata['id'], index_data)
                
                # Update metadata
                metadata_table.update_item(
                    Key={'id': metadata['id']},
                    UpdateExpression="SET indexed = :indexed, indexedAt = :indexedAt",
                    ExpressionAttributeValues={
                        ':indexed': True,
                        ':indexedAt': datetime.datetime.now().isoformat()
                    }
                )
                
                indexed_count += 1
            
            except Exception as e:
                logger.error(f"Error indexing item {metadata['id']}: {str(e)}")
    
    return {
        'statusCode': 200,
        'body': json.dumps({
            'success': True,
            'message': "Full reindexing completed",
            'totalItems': len(items),
            'indexedItems': indexed_count,
            'dataTypes': list(data_types.keys())
        })
    }

def index_in_elasticsearch(index_name, document_id, document):
    """Helper function to index data in Elasticsearch"""
    if not ES_ENDPOINT:
        logger.warning("ES_ENDPOINT environment variable not set, skipping indexing")
        return
    
    # Ensure index name is lowercase
    index_name = index_name.lower()
    
    # Prepare the Elasticsearch URL
    url = f"https://{ES_ENDPOINT}/{index_name}/_doc/{document_id}"
    
    # Send the request to Elasticsearch
    headers = {"Content-Type": "application/json"}
    response = requests.put(url, auth=awsauth, json=document, headers=headers)
    
    # Check for successful response
    if response.status_code >= 200 and response.status_code < 300:
        logger.info(f"Successfully indexed document {document_id} in {index_name}")
    else:
        logger.error(f"Error indexing document: {response.text}")
        raise Exception(f"Elasticsearch indexing failed: {response.text}")

def convert_dynamodb_to_json(dynamodb_item):
    """Convert DynamoDB JSON format to regular JSON"""
    result = {}
    for key, value in dynamodb_item.items():
        result[key] = parse_dynamodb_value(value)
    return result

def parse_dynamodb_value(dynamodb_value):
    """Parse a DynamoDB value to regular Python/JSON value"""
    if 'S' in dynamodb_value:
        return dynamodb_value['S']
    elif 'N' in dynamodb_value:
        return float(dynamodb_value['N'])
    elif 'BOOL' in dynamodb_value:
        return dynamodb_value['BOOL']
    elif 'NULL' in dynamodb_value:
        return None
    elif 'L' in dynamodb_value:
        return [parse_dynamodb_value(item) for item in dynamodb_value['L']]
    elif 'M' in dynamodb_value:
        return convert_dynamodb_to_json(dynamodb_value['M'])
    elif 'SS' in dynamodb_value:
        return set(dynamodb_value['SS'])
    elif 'NS' in dynamodb_value:
        return set([float(n) for n in dynamodb_value['NS']])
    elif 'BS' in dynamodb_value:
        return set([base64.b64decode(b) for b in dynamodb_value['BS']])
    else:
        return None
