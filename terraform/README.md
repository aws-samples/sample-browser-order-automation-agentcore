# Order Automation System - Terraform Infrastructure

This Terraform configuration provides complete AWS deployment for the Order Automation System. It automates infrastructure creation, Docker image build/push, React app build/upload, CloudFront cache invalidation, and ECS service updates.

## 🏗️ Infrastructure Components

### Networking
- **VPC**: Isolated network environment
- **Public/Private Subnets**: High availability across 2 AZs
- **Internet Gateway & NAT Gateways**: Internet connectivity
- **Route Tables**: Traffic routing

### Compute
- **ECS Fargate Cluster**: Serverless container execution
- **Auto Scaling**: CPU/memory-based automatic scaling
- **Application Load Balancer**: Traffic distribution
- **Target Groups**: Health checks included

### Storage
- **ECR Repository**: Docker image storage
- **S3 Buckets**: 
  - Static assets (React app)
  - Application data (upload files)
- **CloudFront**: Global CDN

### Security
- **Security Groups**: Network security
- **IAM Roles**: Least privilege principle
- **S3 Bucket Policies**: Secure access

## 🚀 Deployment Guide

### 1. Prerequisites

```bash
# Install Terraform (1.0+)
brew install terraform

# Install and configure AWS CLI
brew install awscli
aws configure

# Install Docker
brew install docker

# Install Node.js (for React builds)
brew install node
```

### 2. AWS Permissions Setup

Required AWS service permissions:
- VPC, EC2, ECS, ECR
- S3, CloudFront
- IAM, Application Auto Scaling
- CloudWatch Logs
- Amazon Bedrock (for application runtime)

### 3. Deploy Infrastructure

```bash
# 1. Navigate to terraform directory
cd terraform

# 2. Create configuration file
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars to customize settings

# 3. Initialize Terraform
terraform init

# 4. Review deployment plan
terraform plan

# 5. Deploy infrastructure (everything automated!)
terraform apply
```

### 4. Deployment Process

Terraform automatically performs these tasks:

1. **Infrastructure Creation**: VPC, ECS, ECR, ALB, S3, CloudFront, etc.
2. **Docker Image Build**: Multi-stage build combining React + Flask
3. **Push to ECR**: Automatic authentication and upload
4. **React App Build**: Executes `npm run build`
5. **Upload to S3**: Optimized cache headers
6. **CloudFront Invalidation**: Immediate update reflection
7. **ECS Service Update**: Rolling update with new image

## ⚙️ Configuration Options

### Key terraform.tfvars Settings

```hcl
# Project basics
project_name = "order-automation"
environment  = "prod"
aws_region   = "us-west-2"

# Custom domain (optional)
domain_name     = "order.yourdomain.com"
certificate_arn = "arn:aws:acm:us-east-1:123456789012:certificate/..."

# ECS resource configuration
ecs_task_cpu      = 512    # CPU units
ecs_task_memory   = 1024   # MB
ecs_desired_count = 2      # Default task count
ecs_min_capacity  = 1      # Minimum tasks
ecs_max_capacity  = 10     # Maximum tasks

# Auto scaling
enable_auto_scaling = true

# CloudFront pricing
cloudfront_price_class = "PriceClass_100"  # US, Canada, Europe
```

### Environment-Specific Deployments

```bash
# Development environment
terraform workspace new dev
terraform apply -var-file="dev.tfvars"

# Staging environment
terraform workspace new staging
terraform apply -var-file="staging.tfvars"

# Production environment
terraform workspace new prod
terraform apply -var-file="prod.tfvars"
```

## 🔄 Updates and Redeployment

### Automatic Redeployment on Code Changes

Terraform detects these changes and automatically redeploys:

- **Backend code changes**: Python file modifications
- **Frontend code changes**: React source file modifications
- **Dockerfile changes**: Container configuration changes
- **package.json changes**: Dependency updates

```bash
# Apply changes
terraform apply
```

### Manual Redeployment

```bash
# Rebuild specific resources
terraform apply -target=docker_image.app
terraform apply -target=null_resource.upload_frontend

# Force ECS service restart
terraform apply -target=null_resource.ecs_service_update
```

## 📊 Monitoring and Logging

### CloudWatch Logs
- ECS task logs: `/ecs/order-automation`
- 7-day retention policy

### Health Checks
- ALB health check: `/health` endpoint
- ECS container health check: Built-in

### Metrics
- ECS service metrics (CPU, memory)
- ALB metrics (request count, response time)
- CloudFront metrics (cache hit ratio)

## 🔧 Troubleshooting

### Common Issues

1. **Docker Build Failures**
   ```bash
   # Check Docker daemon
   docker info
   
   # Verify ECR login
   aws ecr get-login-password --region us-west-2 | docker login --username AWS --password-stdin 123456789012.dkr.ecr.us-west-2.amazonaws.com
   ```

2. **React Build Failures**
   ```bash
   # Check Node.js version
   node --version  # Requires 16+
   
   # Reinstall dependencies
   cd ../frontend
   rm -rf node_modules package-lock.json
   npm install
   ```

3. **ECS Task Start Failures**
   ```bash
   # Check ECS logs
   aws logs describe-log-groups --log-group-name-prefix "/ecs/order-automation"
   
   # Verify task definition
   aws ecs describe-task-definition --task-definition order-automation-task
   ```

4. **CloudFront Cache Issues**
   ```bash
   # Manual cache invalidation
   aws cloudfront create-invalidation --distribution-id E1234567890123 --paths "/*"
   ```

### Log Inspection

```bash
# ECS service status
aws ecs describe-services --cluster order-automation-cluster --services order-automation-service

# CloudWatch logs
aws logs tail /ecs/order-automation --follow

# ALB target health
aws elbv2 describe-target-health --target-group-arn arn:aws:elasticloadbalancing:...
```

## 💰 Cost Optimization

### Resource Sizing
- **ECS Tasks**: Adjust CPU/memory to actual requirements
- **NAT Gateway**: Use single AZ for cost savings (reduces HA)
- **CloudFront**: Select only required regions

### Automatic Cleanup
- **ECR**: Image lifecycle policy removes old images
- **S3**: Upload files auto-delete after 30 days
- **CloudWatch**: 7-day log retention

## 🔒 Security Best Practices

### Network Security
- ECS tasks run in Private Subnets
- Security Groups allow only necessary ports
- Traffic only allowed through ALB

### Access Control
- IAM role-based least privilege
- S3 bucket public access blocked
- CloudFront OAC prevents direct S3 access

### Data Protection
- S3 server-side encryption (AES256)
- HTTPS enforcement (CloudFront, ALB)
- Versioning enabled

## 🗑️ Resource Cleanup

```bash
# Delete all resources
terraform destroy

# Delete specific resources
terraform destroy -target=aws_ecs_service.app
```

**Warning**: S3 buckets with data may fail to delete. Manually empty them first if needed.

## 📋 Deployment Checklist

Pre-deployment:
- [ ] AWS CLI configured
- [ ] Docker daemon running
- [ ] Node.js 16+ installed
- [ ] Terraform 1.0+ installed
- [ ] AWS permissions verified
- [ ] terraform.tfvars configured

Post-deployment:
- [ ] CloudFront URL accessible
- [ ] API endpoints functional
- [ ] ECS tasks running normally
- [ ] Logs outputting correctly
- [ ] Auto scaling configured

## 🎯 Key Features

### Complete Automation
- **Zero Scripts**: Pure Terraform, no shell scripts
- **One Command**: `terraform apply` does everything
- **Change Detection**: Automatic rebuilds on code changes
- **Rolling Updates**: Zero-downtime deployments

### Production Ready
- **High Availability**: Multi-AZ deployment
- **Auto Scaling**: CPU/memory-based scaling
- **Security**: Best practices implemented
- **Monitoring**: CloudWatch integration

### Developer Friendly
- **Fast Builds**: Multi-stage Docker builds
- **CDN Integration**: Global content delivery
- **Easy Updates**: Simple redeployment process
- **Environment Support**: Dev/staging/prod workspaces

## 🤝 Contributing

1. Create an issue or feature request
2. Create a branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push branch (`git push origin feature/amazing-feature`)
5. Create Pull Request

---

**Built with Terraform, AWS, and Infrastructure as Code Best Practices**