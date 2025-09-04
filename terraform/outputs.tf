output "vpc_id" {
  description = "ID of the VPC"
  value       = aws_vpc.main.id
}

output "public_subnet_ids" {
  description = "IDs of the public subnets"
  value       = aws_subnet.public[*].id
}

output "private_subnet_ids" {
  description = "IDs of the private subnets"
  value       = aws_subnet.private[*].id
}

output "ecr_repository_url" {
  description = "URL of the ECR repository"
  value       = aws_ecr_repository.timecard_processor.repository_url
}

output "alb_dns_name" {
  description = "DNS name of the load balancer"
  value       = aws_lb.main.dns_name
}

output "alb_zone_id" {
  description = "Zone ID of the load balancer"
  value       = aws_lb.main.zone_id
}

output "alb_arn" {
  description = "ARN of the load balancer"
  value       = aws_lb.main.arn
}

output "cloudfront_distribution_id" {
  description = "ID of the CloudFront distribution"
  value       = aws_cloudfront_distribution.main.id
}

output "cloudfront_domain_name" {
  description = "Domain name of the CloudFront distribution"
  value       = aws_cloudfront_distribution.main.domain_name
}

output "s3_static_assets_bucket" {
  description = "Name of the S3 bucket for static assets"
  value       = aws_s3_bucket.static_assets.bucket
}

output "s3_app_data_bucket" {
  description = "Name of the S3 bucket for application data"
  value       = aws_s3_bucket.app_data.bucket
}

output "database_endpoint" {
  description = "RDS database endpoint"
  value       = aws_db_instance.main.endpoint
}

output "database_name" {
  description = "RDS database name"
  value       = aws_db_instance.main.db_name
}

output "ecs_cluster_name" {
  description = "Name of the ECS cluster"
  value       = aws_ecs_cluster.main.name
}

output "ecs_service_name" {
  description = "Name of the ECS service"
  value       = aws_ecs_service.app.name
}

output "application_url" {
  description = "URL to access the application"
  value       = var.domain_name != "" ? "https://${var.domain_name}" : "https://${aws_cloudfront_distribution.main.domain_name}"
}

output "certificate_arn" {
  description = "ARN of the ACM certificate"
  value       = var.domain_name != "" ? aws_acm_certificate.main[0].arn : null
}

output "route53_zone_id" {
  description = "Route53 hosted zone ID"
  value       = var.domain_name != "" ? data.aws_route53_zone.main[0].zone_id : null
}

output "route53_name_servers" {
  description = "Route53 name servers"
  value       = var.domain_name != "" ? data.aws_route53_zone.main[0].name_servers : null
}

output "api_url" {
  description = "URL to access the API directly"
  value       = "http://${aws_lb.main.dns_name}"
}