#!/bin/bash

# cleanup.sh - Script to remove all resources
# Usage: ./scripts/cleanup.sh [environment]

set -e

# Default to dev environment if not specified
ENVIRONMENT=${1:-dev}

# Load environment variables if .env file exists
ENV_FILE=".env.$ENVIRONMENT"
if [ -f "$ENV_FILE" ]; then
    echo "Loading configuration from $ENV_FILE"
    source "$ENV_FILE"
else
    echo "Error: Environment file $ENV_FILE not found!"
    echo "Please specify an environment that has been deployed."
    exit 1
fi

echo "Starting cleanup of serverless data lake resources in $ENVIRONMENT environment..."

# Delete Lambda function
echo "Deleting Lambda function: $LAMBDA_FUNCTION"
aws lambda delete-function --function-name "$LAMBDA_FUNCTION" --region "$REGION" || echo "Lambda function already deleted or not found."

# Delete OpenSearch domain
echo "Deleting OpenSearch domain: $OPENSEARCH_DOMAIN"
aws opensearch delete-domain --domain-name "$OPENSEARCH_DOMAIN" --region "$REGION" || echo "OpenSearch domain already deleted or not found."

# Empty and delete S3 bucket
echo "Emptying and deleting S3 bucket: $BUCKET_NAME"
aws s3 rm "s3://$BUCKET_NAME" --recursive --region "$REGION" || echo "Bucket already empty or not found."
aws s3api delete-bucket --bucket "$BUCKET_NAME" --region "$REGION" || echo "Bucket already deleted or not found."

# Delete IAM role and detach policies
ROLE_NAME="lambda-data-lake-role-$ENVIRONMENT"
echo "Detaching policies and deleting IAM role: $ROLE_NAME"
aws iam detach-role-policy --role-name "$ROLE_NAME" --policy-arn "arn:aws:iam::aws:policy/AmazonS3FullAccess" || echo "Policy already detached or not found."
aws iam detach-role-policy --role-name "$ROLE_NAME" --policy-arn "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole" || echo "Policy already detached or not found."
aws iam detach-role-policy --role-name "$ROLE_NAME" --policy-arn "arn:aws:iam::aws:policy/AmazonOpenSearchServiceFullAccess" || echo "Policy already detached or not found."
aws iam delete-role --role-name "$ROLE_NAME" || echo "Role already deleted or not found."

# Delete CloudWatch dashboard
DASHBOARD_NAME="DataLakeDashboard-$ENVIRONMENT"
echo "Deleting CloudWatch dashboard: $DASHBOARD_NAME"
aws cloudwatch delete-dashboards --dashboard-names "$DASHBOARD_NAME" --region "$REGION" || echo "Dashboard already deleted or not found."

# Delete CloudWatch log groups
echo "Deleting CloudWatch log groups for Lambda function"
aws logs delete-log-group --log-group-name "/aws/lambda/$LAMBDA_FUNCTION" --region "$REGION" || echo "Log group already deleted or not found."

# Delete environment file
echo "Deleting environment file"
rm -f "$ENV_FILE"

echo "Cleanup completed successfully!"
