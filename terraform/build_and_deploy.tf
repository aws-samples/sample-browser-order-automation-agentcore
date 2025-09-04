# Get current AWS account ID and region
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# Build and push Docker image using null_resource
resource "null_resource" "docker_build_push" {
  triggers = {
    dockerfile_hash = filemd5("../Dockerfile")
    backend_hash    = sha256(join("", [for f in fileset("../backend", "**") : filesha256("../backend/${f}")]))
  }

  provisioner "local-exec" {
    command = <<-EOT
      # Login to ECR
      aws ecr get-login-password --region ${data.aws_region.current.name} | docker login --username AWS --password-stdin ${data.aws_caller_identity.current.account_id}.dkr.ecr.${data.aws_region.current.name}.amazonaws.com
      
      # Build and tag image
      docker build -t ${aws_ecr_repository.timecard_processor.repository_url}:latest ../
      
      # Push image
      docker push ${aws_ecr_repository.timecard_processor.repository_url}:latest
    EOT
    working_dir = path.module
  }

  depends_on = [aws_ecr_repository.timecard_processor]
}

# Build React app locally and upload to S3
resource "null_resource" "build_frontend" {
  triggers = {
    frontend_hash = sha256(join("", [for f in fileset("../frontend/src", "**") : filesha256("../frontend/src/${f}")]))
    package_json  = filemd5("../frontend/package.json")
  }

  provisioner "local-exec" {
    command = <<-EOT
      cd ../frontend
      npm ci
      npm run build
    EOT
  }
}

# Upload React build to S3
resource "null_resource" "upload_frontend" {
  depends_on = [null_resource.build_frontend]

  triggers = {
    frontend_hash = sha256(join("", [for f in fileset("../frontend/src", "**") : filesha256("../frontend/src/${f}")]))
    package_json  = filemd5("../frontend/package.json")
  }

  provisioner "local-exec" {
    command = <<-EOT
      aws s3 sync ../frontend/build/ s3://${aws_s3_bucket.static_assets.bucket}/ \
        --delete \
        --cache-control "public, max-age=31536000" \
        --exclude "*.html" \
        --exclude "service-worker.js" \
        --exclude "manifest.json"
      
      aws s3 sync ../frontend/build/ s3://${aws_s3_bucket.static_assets.bucket}/ \
        --cache-control "public, max-age=0, must-revalidate" \
        --include "*.html" \
        --include "service-worker.js" \
        --include "manifest.json"
    EOT
  }
}

# Invalidate CloudFront cache
resource "null_resource" "cloudfront_invalidation" {
  depends_on = [null_resource.upload_frontend]

  triggers = {
    frontend_hash = sha256(join("", [for f in fileset("../frontend/src", "**") : filesha256("../frontend/src/${f}")]))
    package_json  = filemd5("../frontend/package.json")
  }

  provisioner "local-exec" {
    command = <<-EOT
      aws cloudfront create-invalidation \
        --distribution-id ${aws_cloudfront_distribution.main.id} \
        --paths "/*"
    EOT
  }
}

# Force ECS service update after new image is pushed
resource "null_resource" "ecs_service_update" {
  depends_on = [null_resource.docker_build_push]

  triggers = {
    image_hash = null_resource.docker_build_push.id
  }

  provisioner "local-exec" {
    command = <<-EOT
      aws ecs update-service \
        --cluster ${aws_ecs_cluster.main.name} \
        --service ${aws_ecs_service.app.name} \
        --force-new-deployment \
        --region ${var.aws_region}
    EOT
  }
}
