#!/bin/bash

# deploy.sh - Script to deploy serverless data lake infrastructure
# Usage: ./scripts/deploy.sh [environment]

set -e

# Default to dev environment if not specified
ENVIRONMENT=${1:-dev}
STACK_NAME="serverless-data-lake-$ENVIRONMENT"
BUCKET_NAME="data-lake-$ENVIRONMENT-$(openssl rand -hex 4)"
REGION="us-east-1"

echo "Deploying serverless data lake to $ENVIRONMENT environment..."

# Create S3 bucket for data lake storage
echo "Creating S3 bucket: $BUCKET_NAME"
aws s3api create-bucket --bucket $BUCKET_NAME --region $REGION

# Create S3 folder structure
echo "Setting up data lake folder structure..."
aws s3api put-object --bucket $BUCKET_NAME --key raw/
aws s3api put-object --bucket $BUCKET_NAME --key processed/
aws s3api put-object --bucket $BUCKET_NAME --key curated/

# Create Lambda execution role
ROLE_NAME="lambda-data-lake-role-$ENVIRONMENT"
echo "Creating IAM role: $ROLE_NAME"
aws iam create-role \
    --role-name $ROLE_NAME \
    --assume-role-policy-document '{
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Principal": {"Service": "lambda.amazonaws.com"},
            "Action": "sts:AssumeRole"
        }]
    }'

# Attach policies to the role
echo "Attaching policies to IAM role..."
aws iam attach-role-policy \
    --role-name $ROLE_NAME \
    --policy-arn "arn:aws:iam::aws:policy/AmazonS3FullAccess"

aws iam attach-role-policy \
    --role-name $ROLE_NAME \
    --policy-arn "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"

aws iam attach-role-policy \
    --role-name $ROLE_NAME \
    --policy-arn "arn:aws:iam::aws:policy/AmazonOpenSearchServiceFullAccess"

# Wait for role creation to propagate
echo "Waiting for IAM role to propagate..."
sleep 15

# Get role ARN
ROLE_ARN=$(aws iam get-role --role-name $ROLE_NAME --query "Role.Arn" --output text)

# Package Lambda function
echo "Packaging Lambda function..."
pip install -r requirements.txt -t ./package
cp index_data.py ./package
cd package && zip -r ../lambda_function.zip . && cd ..

# Deploy Lambda function
echo "Deploying Lambda function..."
aws lambda create-function \
    --function-name "IndexDataFunction-$ENVIRONMENT" \
    --runtime python3.9 \
    --role "$ROLE_ARN" \
    --handler "index_data.lambda_handler" \
    --zip-file fileb://lambda_function.zip \
    --environment "Variables={BUCKET_NAME=$BUCKET_NAME,ENVIRONMENT=$ENVIRONMENT}" \
    --timeout 60 \
    --memory-size 256

# Clean up temporary files
rm -rf package lambda_function.zip

# Create OpenSearch domain
DOMAIN_NAME="data-lake-search-$ENVIRONMENT"
echo "Creating OpenSearch domain: $DOMAIN_NAME"
aws opensearch create-domain \
    --domain-name $DOMAIN_NAME \
    --engine-version "OpenSearch_1.3" \
    --cluster-config InstanceType=t3.small.search,InstanceCount=1 \
    --ebs-options EBSEnabled=true,VolumeType=gp2,VolumeSize=10 \
    --access-policies '{
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"AWS": "*"},
                "Action": "es:*",
                "Resource": "*"
            }
        ]
    }'

# Set up S3 trigger for Lambda
echo "Setting up S3 trigger for Lambda function..."
aws lambda add-permission \
    --function-name "IndexDataFunction-$ENVIRONMENT" \
    --statement-id "AllowS3Invoke" \
    --action "lambda:InvokeFunction" \
    --principal s3.amazonaws.com \
    --source-arn "arn:aws:s3:::$BUCKET_NAME"

# Create S3 notification configuration
aws s3api put-bucket-notification-configuration \
    --bucket $BUCKET_NAME \
    --notification-configuration '{
        "LambdaFunctionConfigurations": [
            {
                "LambdaFunctionArn": "'"$(aws lambda get-function --function-name IndexDataFunction-$ENVIRONMENT --query 'Configuration.FunctionArn' --output text)"'",
                "Events": ["s3:ObjectCreated:*"],
                "Filter": {
                    "Key": {
                        "FilterRules": [
                            {
                                "Name": "prefix",
                                "Value": "raw/"
                            }
                        ]
                    }
                }
            }
        ]
    }'

# Create CloudWatch dashboard for monitoring
DASHBOARD_NAME="DataLakeDashboard-$ENVIRONMENT"
echo "Creating CloudWatch dashboard: $DASHBOARD_NAME"
aws cloudwatch put-dashboard \
    --dashboard-name $DASHBOARD_NAME \
    --dashboard-body '{
        "widgets": [
            {
                "type": "metric",
                "x": 0,
                "y": 0,
                "width": 12,
                "height": 6,
                "properties": {
                    "metrics": [
                        [ "AWS/Lambda", "Invocations", "FunctionName", "IndexDataFunction-'"$ENVIRONMENT"'" ],
                        [ ".", "Errors", ".", "." ],
                        [ ".", "Duration", ".", "." ]
                    ],
                    "view": "timeSeries",
                    "stacked": false,
                    "region": "'"$REGION"'",
                    "stat": "Sum",
                    "period": 300,
                    "title": "Lambda Function Metrics"
                }
            },
            {
                "type": "metric",
                "x": 0,
                "y": 6,
                "width": 12,
                "height": 6,
                "properties": {
                    "metrics": [
                        [ "AWS/S3", "BucketSizeBytes", "BucketName", "'"$BUCKET_NAME"'", "StorageType", "StandardStorage" ],
                        [ ".", "NumberOfObjects", ".", ".", ".", "AllStorageTypes" ]
                    ],
                    "view": "timeSeries",
                    "stacked": false,
                    "region": "'"$REGION"'",
                    "stat": "Average",
                    "period": 86400,
                    "title": "S3 Bucket Metrics"
                }
            }
        ]
    }'

echo "Saving deployment information..."
cat > .env.$ENVIRONMENT << EOF
ENVIRONMENT=$ENVIRONMENT
BUCKET_NAME=$BUCKET_NAME
OPENSEARCH_DOMAIN=$DOMAIN_NAME
LAMBDA_FUNCTION=IndexDataFunction-$ENVIRONMENT
REGION=$REGION
DEPLOYMENT_TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
EOF

echo "Serverless data lake deployment completed successfully!"
echo "Configuration saved to .env.$ENVIRONMENT"
