#!/usr/bin/env python3
"""
Lambda function to index data in OpenSearch from S3 data lake.
This function is triggered when new files are uploaded to the 'raw/' prefix in the S3 bucket.
It processes the data and indexes it in OpenSearch for search capabilities.
"""

import os
import json
import boto3
import urllib.parse
import logging
import pandas as pd
from io import StringIO, BytesIO
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Get environment variables
BUCKET_NAME = os.environ.get('BUCKET_NAME')
ENVIRONMENT = os.environ.get('ENVIRONMENT')
OPENSEARCH_DOMAIN_NAME = f"data-lake-search-{ENVIRONMENT}"
REGION = os.environ.get('AWS_REGION', 'us-east-1')

# Initialize AWS clients
s3 = boto3.client('s3')
opensearch_client = boto3.client('opensearch')

def get_opensearch_endpoint():
    """Get the OpenSearch domain endpoint."""
    try:
        response = opensearch_client.describe_domain(
            DomainName=OPENSEARCH_DOMAIN_NAME
        )
        endpoint = response['DomainStatus']['Endpoint']
        return f"https://{endpoint}"
    except Exception as e:
        logger.error(f"Error getting OpenSearch endpoint: {str(e)}")
        raise

def get_opensearch_client(endpoint):
    """Create and return an OpenSearch client with AWS authentication."""
    session = boto3.Session()
    credentials = session.get_credentials()
    aws_auth = AWS4Auth(
        credentials.access_key,
        credentials.secret_key,
        REGION,
        'es',
        session_token=credentials.token
    )
    
    return OpenSearch(
        hosts=[{'host': endpoint.replace('https://', ''), 'port': 443}],
        http_auth=aws_auth,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection
    )

def detect_file_type(key):
    """Detect file type based on extension."""
    if key.endswith('.csv'):
        return 'csv'
    elif key.endswith('.json'):
        return 'json'
    elif key.endswith('.parquet'):
        return 'parquet'
    else:
        return 'unknown'

def read_file_content(bucket, key):
    """Read file content from S3 based on file type."""
    file_type = detect_file_type(key)
    
    try:
        obj = s3.get_object(Bucket=bucket, Key=key)
        content = obj['Body']
        
        if file_type == 'csv':
            # For CSV files
            data = content.read().decode('utf-8')
            df = pd.read_csv(StringIO(data))
        elif file_type == 'json':
            # For JSON files
            data = content.read().decode('utf-8')
            if data.strip().startswith('['):
                # List of JSON objects
                df = pd.read_json(StringIO(data))
            else:
                # Newline-delimited JSON
                df = pd.read_json(StringIO(data), lines=True)
        elif file_type == 'parquet':
            # For Parquet files
            df = pd.read_parquet(BytesIO(content.read()))
        else:
            logger.warning(f"Unsupported file type for indexing: {file_type}")
            return None
            
        return df
    except Exception as e:
        logger.error(f"Error reading file content: {str(e)}")
        raise

def create_index_if_not_exists(client, index_name):
    """Create index in OpenSearch if it doesn't exist."""
    try:
        if not client.indices.exists(index=index_name):
            logger.info(f"Creating index: {index_name}")
            
            # Basic index mapping
            index_body = {
                'settings': {
                    'number_of_shards': 1,
                    'number_of_replicas': 1
                },
                'mappings': {
                    'properties': {
                        'timestamp': {'type': 'date'},
                        'processed_timestamp': {'type': 'date'}
                    }
                }
            }
            
            client.indices.create(index=index_name, body=index_body)
            logger.info(f"Index created: {index_name}")
    except Exception as e:
        logger.error(f"Error creating index: {str(e)}")
        raise

def index_data(client, index_name, df):
    """Index data in OpenSearch."""
    try:
        # Add timestamp for indexing
        df['processed_timestamp'] = pd.Timestamp.now().isoformat()
        
        # Convert DataFrame to list of dictionaries for bulk indexing
        records = df.to_dict(orient='records')
        
        # Bulk index the data
        bulk_body = []
        for i, record in enumerate(records):
            # Handle NaN values - OpenSearch doesn't accept NaN
            cleaned_record = {}
            for k, v in record.items():
                if pd.isna(v):
                    cleaned_record[k] = None
                else:
                    cleaned_record[k] = v
                    
            # Add index operation to bulk operation
            bulk_body.append({"index": {"_index": index_name, "_id": str(i)}})
            bulk_body.append(cleaned_record)
        
        if bulk_body:
            response = client.bulk(body=bulk_body)
            
            # Check for errors
            if response.get('errors', False):
                for item in response['items']:
                    if 'error' in item['index']:
                        logger.error(f"Error indexing document: {json.dumps(item['index']['error'])}")
            
            logger.info(f"Indexed {len(records)} documents in {index_name}")
            return len(records)
        return 0
    except Exception as e:
        logger.error(f"Error indexing data: {str(e)}")
        raise

def process_file(bucket, key):
    """Process file and index in OpenSearch."""
    try:
        # Extract dataset name from key for index name
        path_parts = key.split('/')
        
        if len(path_parts) < 2:
            logger.warning(f"Skipping file with insufficient path depth: {key}")
            return
            
        # Use the directory name after 'raw/' as the index name
        if len(path_parts) >= 3 and path_parts[0] == 'raw':
            dataset_name = path_parts[1].lower()
        else:
            # Fallback - use filename without extension
            filename = os.path.basename(key)
            dataset_name = os.path.splitext(filename)[0].lower()
        
        # Clean index name - OpenSearch requires lowercase
        index_name = f"{dataset_name}_{ENVIRONMENT}".replace('-', '_')
        
        # Get OpenSearch endpoint and create client
        endpoint = get_opensearch_endpoint()
        os_client = get_opensearch_client(endpoint)
        
        # Create index if not exists
        create_index_if_not_exists(os_client, index_name)
        
        # Read and process file content
        df = read_file_content(bucket, key)
        
        if df is not None:
            # Index the data
            num_indexed = index_data(os_client, index_name, df)
            
            # Process the data and save to processed/
            processed_key = key.replace('raw/', 'processed/')
            
            # Create directory structure if needed
            directory = os.path.dirname(processed_key)
            if directory:
                try:
                    s3.put_object(Bucket=bucket, Key=f"{directory}/")
                except Exception as e:
                    logger.warning(f"Error creating directory: {str(e)}")
            
            # Save processed file (in this example, we're just moving it)
            if processed_key.endswith('.csv'):
                csv_buffer = StringIO()
                df.to_csv(csv_buffer, index=False)
                s3.put_object(Bucket=bucket, Key=processed_key, Body=csv_buffer.getvalue())
            elif processed_key.endswith('.json'):
                json_buffer = StringIO()
                df.to_json(json_buffer, orient='records')
                s3.put_object(Bucket=bucket, Key=processed_key, Body=json_buffer.getvalue())
            elif processed_key.endswith('.parquet'):
                parquet_buffer = BytesIO()
                df.to_parquet(parquet_buffer)
                s3.put_object(Bucket=bucket, Key=processed_key, Body=parquet_buffer.getvalue())
            
            logger.info(f"Processed file saved to {processed_key}")
            
            return {
                'status': 'success',
                'file': key,
                'index': index_name,
                'records_indexed': num_indexed,
                'processed_file': processed_key
            }
    except Exception as e:
        logger.error(f"Error processing file {key}: {str(e)}")
        raise

def lambda_handler(event, context):
    """Lambda function handler."""
    logger.info(f"Received event: {json.dumps(event)}")
    
    try:
        # Process each record (S3 event notification)
        for record in event.get('Records', []):
            if record.get('eventSource') == 'aws:s3' and record.get('eventName', '').startswith('ObjectCreated:'):
                # Get bucket and key information
                bucket = record['s3']['bucket']['name']
                key = urllib.parse.unquote_plus(record['s3']['object']['key'])
                
                logger.info(f"Processing file: s3://{bucket}/{key}")
                
                # Skip directory markers
                if key.endswith('/'):
                    logger.info(f"Skipping directory marker: {key}")
                    continue
                
                # Process the file
                result = process_file(bucket, key)
                
                if result:
                    logger.info(f"Processing result: {json.dumps(result)}")
        
        return {
            'statusCode': 200,
            'body': json.dumps('Processing completed successfully')
        }
    except Exception as e:
        logger.error(f"Error in lambda_handler: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps(f'Error: {str(e)}')
        }
