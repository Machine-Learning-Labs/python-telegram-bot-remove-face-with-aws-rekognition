provider "aws" {
  region = "eu-central-1"  # Replace with your desired AWS region
}

resource "aws_dynamodb_table" "bot_table" {
  name           = "bot-faceremoverbot"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "user_id"
  
  attribute {
    name = "user_id"
    type = "S"
  }
}
