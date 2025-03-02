# outputs.tf
output "api_url" {
  description = "API Gateway URL"
  value       = "${aws_api_gateway_deployment.deployment.invoke_url}/${aws_api_gateway_resource.resource.path_part}"
}

output "cognito_user_pool_id" {
  description = "Cognito User Pool ID"
  value       = aws_cognito_user_pool.user_pool.id
}

output "cognito_app_client_id" {
  description = "Cognito App Client ID"
  value       = aws_cognito_user_pool_client.user_pool_client.id
}

output "s3_bucket" {
  description = "S3 Data Lake Bucket Name"
  value       = aws_s3_bucket.data_lake.bucket
}

output "s3_bucket_arn" {
  description = "S3 Data Lake Bucket ARN"
  value       = aws_s3_bucket.data_lake.arn
}

output "dynamodb_table" {
  description = "DynamoDB Metadata Table Name"
  value       = aws_dynamodb_table.metadata_table.name
}

output "elasticsearch_endpoint" {
  description = "Elasticsearch Domain Endpoint"
  value       = aws_elasticsearch_domain.es_domain.endpoint
}

output "elasticsearch_kibana_endpoint" {
  description = "Elasticsearch Kibana Endpoint"
  value       = aws_elasticsearch_domain.es_domain.kibana_endpoint
}

output "glue_database" {
  description = "Glue Catalog Database Name"
  value       = aws_glue_catalog_database.glue_database.name
}

output "athena_workgroup" {
  description = "Athena Workgroup Name"
  value       = aws_athena_workgroup.analytics.name
}

output "lambda_api_function_name" {
  description = "Lambda API Handler Function Name"
  value       = aws_lambda_function.api_handler.function_name
}

output "lambda_processor_function_name" {
  description = "Lambda Data Processor Function Name"
  value       = aws_lambda_function.data_processor.function_name
}

output "cloudwatch_dashboard_url" {
  description = "CloudWatch Dashboard URL"
  value       = "https://console.aws.amazon.com/cloudwatch/home?region=${var.aws_region}#dashboards:name=${aws_cloudwatch_dashboard.main_dashboard.dashboard_name}"
}
