# ECS Task Execution Role
resource "aws_iam_role" "ecs_task_execution" {
  name = "${var.project_name}-ecs-task-execution-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
      }
    ]
  })

  tags = var.tags
}

resource "aws_iam_role_policy_attachment" "ecs_task_execution" {
  role       = aws_iam_role.ecs_task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# ECS Task Role
resource "aws_iam_role" "ecs_task" {
  name = "${var.project_name}-ecs-task-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
      }
    ]
  })

  tags = var.tags
}

# ECS Task Policy for Amazon Bedrock and S3
resource "aws_iam_role_policy" "ecs_task" {
  name = "${var.project_name}-ecs-task-policy"
  role = aws_iam_role.ecs_task.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream",
          "bedrock:ListFoundationModels",
          "bedrock:GetFoundationModel",
          "bedrock:Converse",
          "bedrock:ConverseStream"
        ]
        Resource = [
          # All foundation models in all regions
          "arn:aws:bedrock:*::foundation-model/*",
          # All inference profiles in all regions
          "arn:aws:bedrock:*:${data.aws_caller_identity.current.account_id}:inference-profile/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.app_data.arn,
          "${aws_s3_bucket.app_data.arn}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "bedrock:CreateAutomatedReasoningPolicy",
          "bedrock:GetAutomatedReasoningPolicy",
          "bedrock:ListAutomatedReasoningPolicies",
          "bedrock:ExportAutomatedReasoningPolicyVersion",
          "bedrock:StartAutomatedReasoningPolicyBuildWorkflow",
          "bedrock:GetAutomatedReasoningPolicyBuildWorkflow",
          "bedrock:InvokeAutomatedReasoningPolicy"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "bedrock:CreateGuardrail",
          "bedrock:GetGuardrail",
          "bedrock:ListGuardrails",
          "bedrock:ApplyGuardrail"
        ]
        Resource = "*"
      }
    ]
  })
}

# Auto Scaling Role
resource "aws_iam_role" "ecs_auto_scaling" {
  count = var.enable_auto_scaling ? 1 : 0
  name  = "${var.project_name}-ecs-auto-scaling-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "application-autoscaling.amazonaws.com"
        }
      }
    ]
  })

  tags = var.tags
}

# Note: AmazonECSServiceRolePolicy is deprecated and no longer needed for ECS auto scaling