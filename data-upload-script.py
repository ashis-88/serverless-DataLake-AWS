#!/usr/bin/env python3
"""
Script to upload sample data to the data lake for testing purposes.
"""

import os
import sys
import argparse
import boto3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

def load_env_file(env_file):
    """Load environment variables from .env file."""
    env_vars = {}
    try:
        with open(env_file, 'r') as f:
            for line in f:
                if '=' in line:
                    key, value = line.strip().split('=', 1)
                    env_vars[key] = value
        return env_vars
    except FileNotFoundError:
        print(f"Error: Environment file {env_file} not found!")
        sys.exit(1)

def create_sample_sales_data(num_records=1000):
    """Create sample sales data for testing."""
    # Create date range for the last 30 days
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)
    dates = pd.date_range(start=start_date, end=end_date, periods=num_records)
    
    # Create products
    products = ['Laptop', 'Smartphone', 'Tablet', 'Headphones', 'Monitor', 'Keyboard', 'Mouse', 'Speaker']
    
    # Create regions
    regions = ['North', 'South', 'East', 'West', 'Central']
    
    # Create sample data
    data = {
        'transaction_id': [f'TXN-{i:06d}' for i in range(1, num_records + 1)],
        'date': dates,
        'product': np.random.choice(products, num_records),
        'region': np.random.choice(regions, num_records),
        'quantity': np.random.randint(1, 10, num_records),
        'unit_price': np.random.uniform(10.0, 1000.0, num_records).round(2),
    }
    
    # Calculate total price
    df = pd.DataFrame(data)
    df['total_price'] = (df['quantity'] * df['unit_price']).round(2)
    
    return df

def create_sample_customer_data(num_records=500):
    """Create sample customer data for testing."""
    # Create customer IDs
    customer_ids = [f'CUST-{i:05d}' for i in range(1, num_records + 1)]
    
    # Create names
    first_names = ['John', 'Jane', 'Michael', 'Emily', 'David', 'Sarah', 'Robert', 'Lisa', 'William', 'Jessica']
    last_names = ['Smith', 'Johnson', 'Williams', 'Jones', 'Brown', 'Davis', 'Miller', 'Wilson', 'Moore', 'Taylor']
    
    # Create regions
    regions = ['North', 'South', 'East', 'West', 'Central']
    
    # Create segments
    segments = ['Premium', 'Standard', 'Basic']
    
    # Create join dates
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365 * 3)  # Last 3 years
    join_dates = pd.date_range(start=start_date, end=end_date, periods=num_records)
    
    # Create sample data
    data = {
        'customer_id': customer_ids,
        'first_name': np.random.choice(first_names, num_records),
        'last_name': np.random.choice(last_names, num_records),
        'email': [f'{fname.lower()}.{lname.lower()}@example.com' for fname, lname in zip(
            np.random.choice(first_names, num_records), 
            np.random.choice(last_names, num_records)
        )],
        'region': np.random.choice(regions, num_records),
        'segment': np.random.choice(segments, num_records, p=[0.2, 0.5, 0.3]),
        'join_date': join_dates,
        'lifetime_value': np.random.uniform(100.0, 10000.0, num_records).round(2),
    }
    
    return pd.DataFrame(data)

def create_sample_product_data(num_records=100):
    """Create sample product data for testing."""
    # Create product IDs
    product_ids = [f'PROD-{i:04d}' for i in range(1, num_records + 1)]
    
    # Create product names
    product_types = ['Laptop', 'Smartphone', 'Tablet', 'Headphones', 'Monitor', 'Keyboard', 'Mouse', 'Speaker']
    brands = ['TechPro', 'Electronica', 'GadgetCo', 'DigiPlus', 'SmartTech', 'FutureBrand']
    
    # Create categories
    categories = ['Electronics', 'Computing', 'Audio', 'Accessories']
    
    # Create sample data
    data = {
        'product_id': product_ids,
        'product_name': [f'{np.random.choice(brands)} {np.random.choice(product_types)} {np.random.choice(["Pro", "Lite", "Plus", "Max", ""])}' for _ in range(num_records)],
        'category': np.random.choice(categories, num_records),
        'price': np.random.uniform(10.0, 2000.0, num_records).round(2),
        'in_stock': np.random.choice([True, False], num_records, p=[0.8, 0.2]),
        'stock_quantity': np.random.randint(0, 1000, num_records),
        'launch_date': pd.date_range(start='2020-01-01', end='2023-12-31', periods=num_records),
    }
    
    return pd.DataFrame(data)

def upload_sample_data(bucket_name, file_format='csv'):
    """Upload sample datasets to the S3 bucket."""
    s3 = boto3.client('s3')
    
    # Create sample datasets
    sales_data = create_sample_sales_data(1000)
    customer_data = create_sample_customer_data(500)
    product_data = create_sample_product_data(100)
    
    # Create local directory for temporary files
    os.makedirs('temp', exist_ok=True)
    
    datasets = {
        'sales': sales_data,
        'customers': customer_data,
        'products': product_data
    }
    
    uploaded_files = []
    
    for name, df in datasets.items():
        local_path = f'temp/{name}.{file_format}'
        s3_key = f'raw/{name}/{name}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.{file_format}'
        
        # Save to local file
        if file_format == 'csv':
            df.to_csv(local_path, index=False)
        elif file_format == 'json':
            df.to_json(local_path, orient='records', lines=True)
        elif file_format == 'parquet':
            df.to_parquet(local_path, index=False)
        else:
            raise ValueError(f"Unsupported file format: {file_format}")
        
        # Upload to S3
        print(f"Uploading {local_path} to s3://{bucket_name}/{s3_key}")
        s3.upload_file(local_path, bucket_name, s3_key)
        uploaded_files.append(s3_key)
    
    # Clean up temporary files
    for name in datasets.keys():
        os.remove(f'temp/{name}.{file_format}')
    
    return uploaded_files

def main():
    parser = argparse.ArgumentParser(description='Upload sample data to data lake')
    parser.add_argument('--environment', '-e', default='dev', help='Environment (dev, test, prod)')
    parser.add_argument('--format', '-f', choices=['csv', 'json', 'parquet'], default='csv', help='File format')
    args = parser.parse_args()
    
    # Load environment variables
    env_file = f'.env.{args.environment}'
    env_vars = load_env_file(env_file)
    
    # Get bucket name
    bucket_name = env_vars.get('BUCKET_NAME')
    if not bucket_name:
        print(f"Error: BUCKET_NAME not found in {env_file}")
        sys.exit(1)
    
    # Upload sample data
    try:
        uploaded_files = upload_sample_data(bucket_name, args.format)
        print(f"Successfully uploaded {len(uploaded_files)} files to s3://{bucket_name}/")
        for file in uploaded_files:
            print(f"  - {file}")
    except Exception as e:
        print(f"Error uploading sample data: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    main()
