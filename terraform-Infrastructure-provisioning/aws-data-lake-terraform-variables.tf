# variables.tf
variable "aws_region" {
  description = "AWS region to deploy resources"
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Name of the project"
  type        = string
  default     = "data-lake"
}

variable "environment" {
  description = "Environment (dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "tags" {
  description = "Common tags for all resources"
  type        = map(string)
  default = {
    Project     = "data-lake"
    Environment = "dev"
    ManagedBy   = "terraform"
  }
}

# S3 variables
variable "s3_versioning" {
  description = "Enable versioning for S3 bucket"
  type        = bool
  default     = true
}

# Cognito variables
variable "cognito_password_policy" {
  description = "Password policy for Cognito users"
  type = object({
    minimum_length    = number
    require_lowercase = bool
    require_uppercase = bool
    require_numbers   = bool
    require_symbols   = bool
  })
  default = {
    minimum_length    = 8
    require_lowercase = true
    require_uppercase = true
    require_numbers   = true
    require_symbols   = true
  }
}

# DynamoDB variables
variable "dynamodb_billing_mode" {
  description = "DynamoDB billing mode"
  type        = string
  default     = "PAY_PER_REQUEST"
}

# ElasticSearch variables
variable "elasticsearch_version" {
  description = "ElasticSearch version"
  type        = string
  default     = "7.10"
}

variable "elasticsearch_instance_type" {
  description = "ElasticSearch instance type"
  type        = string
  default     = "t3.small.elasticsearch"
}

# Lambda variables
variable "lambda_runtime_api" {
  description = "Runtime for API Lambda function"
  type        = string
  default     = "nodejs14.x"
}

variable "lambda_runtime_processor" {
  description = "Runtime for processor Lambda function"
  type        = string
  default     = "python3.9"
}

# CloudWatch variables
variable "log_retention_days" {
  description = "Number of days to retain CloudWatch logs"
  type        = number
  default     = 14
}
