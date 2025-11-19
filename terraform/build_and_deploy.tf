# Get current AWS account ID and region
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# Build and push Docker image using null_resource
resource "null_resource" "docker_build_push" {
  triggers = {
    dockerfile_hash = filemd5("../Dockerfile")
    backend_hash    = sha256(join("", [for f in fileset("../backend", "**") : filesha256("../backend/${f}") if !can(regex("\\.(db|sqlite|sqlite3)$", f))]))
  }

  provisioner "local-exec" {
    command = <<-EOT
      # Login to ECR
      aws ecr get-login-password --region ${data.aws_region.current.name} | docker login --username AWS --password-stdin ${data.aws_caller_identity.current.account_id}.dkr.ecr.${data.aws_region.current.name}.amazonaws.com
      
      # Build and tag image
      docker build -t ${aws_ecr_repository.order_automation.repository_url}:latest ../
      
      # Push image
      docker push ${aws_ecr_repository.order_automation.repository_url}:latest
    EOT
    working_dir = path.module
  }

  depends_on = [aws_ecr_repository.order_automation]
}

# Build React app in isolated environment and upload to S3
resource "null_resource" "build_frontend" {
  triggers = {
    frontend_hash = sha256(join("", [for f in fileset("../frontend/src", "**") : filesha256("../frontend/src/${f}")]))
    package_json  = filemd5("../frontend/package.json")
  }

  provisioner "local-exec" {
    command = <<-EOT
      echo "Building frontend in isolated terraform build directory..."
      
      # Create isolated build directory
      BUILD_DIR="../.terraform-build/frontend"
      rm -rf "$BUILD_DIR"
      mkdir -p "$BUILD_DIR"
      
      # Copy frontend source to isolated directory
      echo "Copying frontend source..."
      cp -r ../frontend/* "$BUILD_DIR/"
      
      cd "$BUILD_DIR"
      
      # Clean any existing build artifacts
      rm -rf build node_modules/.cache
      
      # Install dependencies in isolated directory
      echo "Installing dependencies..."
      npm ci --production=false
      
      # Build the project with production settings
      echo "Building React app for production..."
      GENERATE_SOURCEMAP=false npm run build
      
      # Verify build output
      if [ ! -d "build" ]; then
        echo "ERROR: Build directory not created"
        exit 1
      fi
      
      echo "Frontend build completed successfully"
      ls -la build/
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
      echo "Uploading frontend to S3..."
      
      # Use isolated build directory
      BUILD_DIR="../.terraform-build/frontend/build"
      
      # Verify build directory exists
      if [ ! -d "$BUILD_DIR" ]; then
        echo "ERROR: Build directory not found at $BUILD_DIR"
        exit 1
      fi
      
      # Upload static assets with long cache
      aws s3 sync "$BUILD_DIR/" s3://${aws_s3_bucket.static_assets.bucket}/ \
        --delete \
        --cache-control "public, max-age=31536000" \
        --exclude "*.html" \
        --exclude "service-worker.js" \
        --exclude "manifest.json"
      
      # Upload HTML and service worker with no cache
      aws s3 sync "$BUILD_DIR/" s3://${aws_s3_bucket.static_assets.bucket}/ \
        --cache-control "public, max-age=0, must-revalidate" \
        --include "*.html" \
        --include "service-worker.js" \
        --include "manifest.json"
      
      echo "Frontend upload completed"
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
      echo "Creating CloudFront invalidation..."
      INVALIDATION_ID=$(aws cloudfront create-invalidation \
        --distribution-id ${aws_cloudfront_distribution.main.id} \
        --paths "/*" \
        --query 'Invalidation.Id' \
        --output text)
      
      echo "CloudFront invalidation created: $INVALIDATION_ID"
      
      # Wait for invalidation to complete (optional, but ensures cache is cleared)
      echo "Waiting for invalidation to complete..."
      aws cloudfront wait invalidation-completed \
        --distribution-id ${aws_cloudfront_distribution.main.id} \
        --id $INVALIDATION_ID
      
      echo "CloudFront invalidation completed"
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
