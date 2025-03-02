# serverless-DataLake-AWS
a serverless data lake architecture built on AWS services











# AWS Serverless Data Lake with API Gateway, Lambda & S3

##  Project Overview
This project implements a **fully serverless data lake** architecture on AWS. It is designed for efficient data ingestion, transformation, and querying using **API Gateway, Lambda, S3, DynamoDB, OpenSearch, Athena, and Glue**.

##  Key Features
- **API Gateway** to expose RESTful API endpoints.
- **AWS Lambda** for event-driven data processing.
- **Amazon S3** for data storage.
- **AWS Glue** for metadata cataloging.
- **Amazon Athena** for SQL-based querying.
- **Amazon DynamoDB** for NoSQL storage.
- **Amazon OpenSearch** for full-text search and indexing.
- **Amazon CloudWatch** for monitoring and logging.
- **IAM Roles & Cognito** for authentication and access control.

##  Architecture

![Architecture Diagram](./architecture.png)

## 📂 Project Structure
```plaintext
├── terraform/                  # Infrastructure as Code (Terraform)
│   ├── main.tf                 # AWS resource definitions
│   ├── variables.tf             # Variables for configuration
│   ├── outputs.tf               # Output values
│   ├── providers.tf             # AWS provider configuration
├── lambdas/                    # Lambda function code
│   ├── ingest_data.py           # Lambda function to process incoming data
│   ├── query_data.py            # Lambda function for querying data
│   ├── index_data.py            # Lambda function to index data in OpenSearch
├── scripts/                     # Helper scripts
│   ├── deploy.sh                # Script to deploy infrastructure
│   ├── cleanup.sh               # Script to remove all resources
├── README.md                    # Project documentation
```

## 🛠️ Setup & Deployment
### 1️⃣ Prerequisites
- **AWS Account** with permissions for IAM, Lambda, S3, API Gateway, and DynamoDB.
- **Terraform installed** (v1.5+ recommended).
- **AWS CLI configured** with necessary access credentials.

### 2️⃣ Deployment Steps
#### **Step 1: Clone the Repository**
```bash
git clone https://github.com/your-github/aws-data-lake.git
cd aws-data-lake
```

#### **Step 2: Deploy with Terraform**
```bash
cd terraform
terraform init
terraform apply -auto-approve
```

#### **Step 3: Deploy Lambda Functions**
```bash
cd lambdas
zip -r ingest_data.zip ingest_data.py
aws lambda create-function --function-name ingestData \  
    --runtime python3.9 --role <IAM_ROLE_ARN> --handler ingest_data.lambda_handler \
    --zip-file fileb://ingest_data.zip
```

#### **Step 4: Test the API Gateway Endpoint**
```bash
curl -X POST https://your-api-gateway-id.execute-api.us-east-1.amazonaws.com/prod/ingest \
    -H "Content-Type: application/json" -d '{"message": "Hello, World!"}'
```

## 📊 Monitoring & Logs
- Use **AWS CloudWatch Logs** to monitor Lambda executions.
- **CloudWatch Metrics** for API Gateway and Lambda performance.

## 📌 Future Enhancements
- Implement real-time streaming with **Kinesis**.
- Add **Machine Learning models** for data analytics.

## 📜 License
This project is licensed under the **MIT License**.

## 👨‍💻 Author
**[Your Name]** - AWS DevOps Engineer & Freelancer

