variable "project_name" {
  description = "Name of the project"
  type        = string
  default     = "timecard-processor"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "prod"
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-west-2"
}

variable "domain_name" {
  description = "Domain name for the application (optional)"
  type        = string
  default     = ""
}

variable "create_certificate" {
  description = "Whether to create ACM certificate automatically"
  type        = bool
  default     = true
}

variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zones" {
  description = "Availability zones"
  type        = list(string)
  default     = ["us-west-2a", "us-west-2b"]
}

variable "ecs_task_cpu" {
  description = "CPU units for ECS task"
  type        = number
  default     = 2048  # Increased from 512 to 2048 (2 vCPU)
}

variable "ecs_task_memory" {
  description = "Memory for ECS task"
  type        = number
  default     = 4096  # Increased from 1024 to 4096 (4 GB)
}

# Security feature toggles
variable "enable_vpc_flow_logs" {
  description = "Enable VPC Flow Logs"
  type        = bool
  default     = false
}

variable "enable_guardduty" {
  description = "Enable GuardDuty"
  type        = bool
  default     = false
}

variable "enable_config" {
  description = "Enable AWS Config"
  type        = bool
  default     = false
}

variable "enable_cloudtrail" {
  description = "Enable CloudTrail"
  type        = bool
  default     = false
}

variable "ecs_desired_count" {
  description = "Desired number of ECS tasks"
  type        = number
  default     = 3  # Increased from 2 to 3
}

variable "ecs_min_capacity" {
  description = "Minimum number of ECS tasks"
  type        = number
  default     = 2  # Increased from 1 to 2
}

variable "ecs_max_capacity" {
  description = "Maximum number of ECS tasks"
  type        = number
  default     = 15  # Increased from 10 to 15
}

variable "enable_auto_scaling" {
  description = "Enable ECS auto scaling"
  type        = bool
  default     = true
}

variable "cloudfront_price_class" {
  description = "CloudFront price class"
  type        = string
  default     = "PriceClass_100"
}

variable "certificate_arn" {
  description = "ARN of existing ACM certificate (optional)"
  type        = string
  default     = ""
}

variable "tags" {
  description = "Tags to apply to resources"
  type        = map(string)
  default = {
    Project     = "timecard-processor"
    Environment = "prod"
    ManagedBy   = "terraform"
  }
}

# Database variables
variable "db_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t4g.micro"
}

variable "db_allocated_storage" {
  description = "Initial allocated storage for RDS"
  type        = number
  default     = 20
}

variable "db_max_allocated_storage" {
  description = "Maximum allocated storage for RDS autoscaling"
  type        = number
  default     = 100
}

variable "db_name" {
  description = "Database name"
  type        = string
  default     = "timecard_processor"
}

variable "db_username" {
  description = "Database username"
  type        = string
  default     = "timecard_admin"
}

variable "db_backup_retention_period" {
  description = "Database backup retention period in days"
  type        = number
  default     = 7
}

variable "db_multi_az" {
  description = "Enable Multi-AZ deployment for RDS"
  type        = bool
  default     = false
}