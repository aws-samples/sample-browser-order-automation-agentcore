# S3 bucket for static assets (React app)
resource "aws_s3_bucket" "static_assets" {
  bucket = "${var.project_name}-static-assets-${random_id.bucket_suffix.hex}"

  tags = var.tags
}

resource "random_id" "bucket_suffix" {
  byte_length = 4
}

resource "aws_s3_bucket_versioning" "static_assets" {
  bucket = aws_s3_bucket.static_assets.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "static_assets" {
  bucket = aws_s3_bucket.static_assets.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "static_assets" {
  bucket = aws_s3_bucket.static_assets.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# S3 bucket for application data/uploads
resource "aws_s3_bucket" "app_data" {
  bucket = "${var.project_name}-app-data-${random_id.bucket_suffix.hex}"

  tags = var.tags
}

resource "aws_s3_bucket_versioning" "app_data" {
  bucket = aws_s3_bucket.app_data.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "app_data" {
  bucket = aws_s3_bucket.app_data.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "app_data" {
  bucket = aws_s3_bucket.app_data.id

  block_public_acls       = true
  block_public_policy     = true  # Allow bucket policy for presigned URLs
  ignore_public_acls      = true
  restrict_public_buckets = true  # Allow presigned URL access
}

# S3 bucket CORS configuration for direct uploads
resource "aws_s3_bucket_cors_configuration" "app_data" {
  bucket = aws_s3_bucket.app_data.id

  cors_rule {
    allowed_headers = ["*"]
    allowed_methods = ["GET", "POST", "PUT", "DELETE", "HEAD"]
    allowed_origins = ["*"]
    expose_headers  = [
      "ETag", 
      "x-amz-meta-original-filename", 
      "x-amz-meta-upload-timestamp",
      "x-amz-request-id",
      "x-amz-id-2",
      "x-amz-version-id",
      "x-amz-server-side-encryption",
      "Content-Length",
      "Content-Type"
    ]
    max_age_seconds = 86400
  }
}

# S3 bucket lifecycle configuration for app data
resource "aws_s3_bucket_lifecycle_configuration" "app_data" {
  bucket = aws_s3_bucket.app_data.id

  rule {
    id     = "cleanup_uploads"
    status = "Enabled"

    filter {
      prefix = ""
    }

    expiration {
      days = 30
    }

    noncurrent_version_expiration {
      noncurrent_days = 7
    }
  }
}