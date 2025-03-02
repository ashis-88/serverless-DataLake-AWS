# ingest_data.py
import json
import boto3
import os
import uuid
import datetime
import logging
from botocore.exceptions import ClientError

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
s3_client = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')

# Get environment variables
S3_BUCKET = os.environ.get('S3_BUCKET')
DYNAMODB_TABLE = os.environ.get('DYNAMODB_TABLE')

# Initialize DynamoDB table
metadata_table = dynamodb.Table(DYNAMODB_TABLE)

def lambda_handler(event, context):
    """
    Lambda function to process and ingest incoming data into the data lake.
    
    This function:
    1. Receives data from the API Gateway
    2. Generates a unique ID for the data
    3. Stores the raw data in S3
    4. Creates metadata entry in DynamoDB
    5. Returns the ID and storage location
    """
    try:
        logger.info("Received event: {}".format(json.dumps(event)))
        
        # Extract data from event
        # For API Gateway proxy integration
        if 'body' in event:
            try:
                body = json.loads(event['body'])
            except:
                body = event['body']
        else:
            body = event
        
        # Generate a unique ID for this data
        data_id = str(uuid.uuid4())
        timestamp = datetime.datetime.now().isoformat()
        
        # Extract data details
        data_type = body.get('dataType', 'unknown')
        source = body.get('source', 'api')
        owner = body.get('owner', 'system')
        
        # For demo purposes, generate random data if none provided
        if 'data' not in body:
            logger.info("No data provided, generating sample data")
            sample_data = generate_sample_data(data_type)
            body['data'] = sample_data
        
        # Prepare data for storage
        data_content = json.dumps(body['data'])
        
        # S3 key with folder structure for organization
        s3_key = f"{data_type}/{timestamp[:10]}/{data_id}.json"
        
        # Store raw data in S3
        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=s3_key,
            Body=data_content,
            ContentType='application/json'
        )
        
        # Create metadata entry in DynamoDB
        metadata_item = {
            'id': data_id,
            'timestamp': timestamp,
            'dataType': data_type,
            'source': source,
            'owner': owner,
            's3Location': f"s3://{S3_BUCKET}/{s3_key}",
            'sizeBytes': len(data_content),
            'status': 'ingested'
        }
        
        # Add optional metadata if available
        if 'tags' in body:
            metadata_item['tags'] = body['tags']
        if 'description' in body:
            metadata_item['description'] = body['description']
        
        # Store metadata in DynamoDB
        metadata_table.put_item(Item=metadata_item)
        
        logger.info(f"Successfully ingested data with ID: {data_id}")
        
        # Return success response
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'success': True,
                'dataId': data_id,
                's3Location': f"s3://{S3_BUCKET}/{s3_key}",
                'message': 'Data successfully ingested'
            })
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
        logger.error(f"Error processing data: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'success': False,
                'message': f"Error processing data: {str(e)}"
            })
        }

def generate_sample_data(data_type):
    """Generate sample data based on the data type"""
    if data_type == 'sales':
        return {
            'date': datetime.datetime.now().strftime('%Y-%m-%d'),
            'items': [
                {'product': 'Widget A', 'quantity': 5, 'price': 10.99},
                {'product': 'Gadget B', 'quantity': 2, 'price': 24.95},
                {'product': 'Tool C', 'quantity': 1, 'price': 34.50}
            ],
            'total': 126.34,
            'customer': {
                'id': f"CUST-{uuid.uuid4().hex[:8]}",
                'region': 'Northeast'
            }
        }
    elif data_type == 'user':
        return {
            'userId': f"USER-{uuid.uuid4().hex[:8]}",
            'name': 'Sample User',
            'email': 'user@example.com',
            'preferences': {
                'theme': 'dark',
                'notifications': True
            },
            'lastLogin': datetime.datetime.now().isoformat()
        }
    elif data_type == 'metrics':
        return {
            'timestamp': datetime.datetime.now().isoformat(),
            'cpu': 42.5,
            'memory': 68.3,
            'disk': 56.2,
            'network': {
                'in': 1024,
                'out': 2048
            }
        }
    else:
        # Generic sample data
        return {
            'timestamp': datetime.datetime.now().isoformat(),
            'sample': True,
            'value': 12345,
            'message': f"This is sample data of type: {data_type}"
        }
