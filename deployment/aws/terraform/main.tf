terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

resource "aws_s3_bucket" "source_imports" {
  bucket = var.source_imports_bucket
}

resource "aws_s3_bucket" "fits_containers" {
  bucket = var.fits_containers_bucket
}

resource "aws_s3_bucket" "derived_reports" {
  bucket = var.derived_reports_bucket
}

resource "aws_sqs_queue" "jobs" {
  name = "${var.name_prefix}-jobs"
}

# ECS Fargate, ECR, RDS PostgreSQL, KMS, Secrets Manager, VPC endpoints and ALB
# are intentionally defined as module boundaries for the controlled deployment pack.
# Fill these in per client network and security requirements.
