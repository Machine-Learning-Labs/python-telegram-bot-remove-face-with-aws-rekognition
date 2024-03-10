provider "aws" {
  region = "us-east-1"  # Replace with your desired AWS region
}

resource "aws_dynamodb_table" "example_table" {
  name           = "example-table"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "user_id"
  attribute {
    name = "user_id"
    type = "N"
  }
  attribute {
    name = "credits"
    type = "N"
  }
}
