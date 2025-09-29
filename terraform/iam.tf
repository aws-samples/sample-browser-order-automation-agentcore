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
        Sid = "BedrockModelInvocation"
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
        Sid = "BedrockAgentCoreFullAccess"
        Effect = "Allow"
        Action = [
          "bedrock-agentcore:*"
        ]
        Resource = "*"
      },
      {
        Sid = "BedrockAgentCoreControlFullAccess"
        Effect = "Allow"
        Action = [
          "bedrock-agentcore-control:*"
        ]
        Resource = "*"
      },
      {
        Sid = "BedrockAgentCoreWorkloadAccess"
        Effect = "Allow"
        Action = [
          "bedrock-agentcore:GetWorkloadAccessToken",
          "bedrock-agentcore:GetWorkloadAccessTokenForJWT",
          "bedrock-agentcore:GetWorkloadAccessTokenForUserId"
        ]
        Resource = [
          "arn:aws:bedrock-agentcore:${var.aws_region}:${data.aws_caller_identity.current.account_id}:workload-identity-directory/default",
          "arn:aws:bedrock-agentcore:${var.aws_region}:${data.aws_caller_identity.current.account_id}:workload-identity-directory/default/workload-identity/*"
        ]
      },
      {
        Sid = "S3FullAccess"
        Effect = "Allow"
        Action = [
          "s3:*"
        ]
        Resource = [
          aws_s3_bucket.app_data.arn,
          "${aws_s3_bucket.app_data.arn}/*",
          aws_s3_bucket.static_assets.arn,
          "${aws_s3_bucket.static_assets.arn}/*",
          "arn:aws:s3:::bedrock-agentcore-*",
          "arn:aws:s3:::bedrock-agentcore-*/*",
          "arn:aws:s3:::sanghwa-oregon",
          "arn:aws:s3:::sanghwa-oregon/*"
        ]
      },
      {
        Sid = "IAMRoleManagement"
        Effect = "Allow"
        Action = [
          "iam:CreateRole",
          "iam:DeleteRole",
          "iam:GetRole",
          "iam:PutRolePolicy",
          "iam:DeleteRolePolicy",
          "iam:AttachRolePolicy",
          "iam:DetachRolePolicy",
          "iam:TagRole",
          "iam:ListRolePolicies",
          "iam:ListAttachedRolePolicies",
          "iam:ListRoles",
          "iam:PassRole",
          "sts:AssumeRole"
        ]
        Resource = "*"
      },
      {
        Sid = "CloudWatchLogsAccess"
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "logs:DescribeLogGroups",
          "logs:DescribeLogStreams",
          "logs:GetLogEvents"
        ]
        Resource = [
          "arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:log-group:/aws/bedrock-agentcore/*",
          "arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:log-group:/aws/codebuild/*",
          "arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:*"
        ]
      },
      {
        Sid = "ECRAccess"
        Effect = "Allow"
        Action = [
          "ecr:CreateRepository",
          "ecr:DescribeRepositories",
          "ecr:GetRepositoryPolicy",
          "ecr:InitiateLayerUpload",
          "ecr:CompleteLayerUpload",
          "ecr:PutImage",
          "ecr:UploadLayerPart",
          "ecr:BatchCheckLayerAvailability",
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage",
          "ecr:ListImages",
          "ecr:TagResource",
          "ecr:GetAuthorizationToken"
        ]
        Resource = "*"
      },
      {
        Sid = "CodeBuildAccess"
        Effect = "Allow"
        Action = [
          "codebuild:StartBuild",
          "codebuild:BatchGetBuilds",
          "codebuild:ListBuildsForProject",
          "codebuild:CreateProject",
          "codebuild:UpdateProject",
          "codebuild:BatchGetProjects",
          "codebuild:ListProjects"
        ]
        Resource = "*"
      },
      {
        Sid = "XRayAccess"
        Effect = "Allow"
        Action = [
          "xray:PutTraceSegments",
          "xray:PutTelemetryRecords",
          "xray:GetSamplingRules",
          "xray:GetSamplingTargets"
        ]
        Resource = "*"
      },
      {
        Sid = "CloudWatchMetrics"
        Effect = "Allow"
        Action = [
          "cloudwatch:PutMetricData"
        ]
        Resource = "*"
        Condition = {
          StringEquals = {
            "cloudwatch:namespace" = "bedrock-agentcore"
          }
        }
      },
      {
        Sid = "BedrockGuardrailsAndPolicies"
        Effect = "Allow"
        Action = [
          "bedrock:CreateAutomatedReasoningPolicy",
          "bedrock:GetAutomatedReasoningPolicy",
          "bedrock:ListAutomatedReasoningPolicies",
          "bedrock:ExportAutomatedReasoningPolicyVersion",
          "bedrock:StartAutomatedReasoningPolicyBuildWorkflow",
          "bedrock:GetAutomatedReasoningPolicyBuildWorkflow",
          "bedrock:InvokeAutomatedReasoningPolicy",
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

# Bedrock AgentCore Execution Role
resource "aws_iam_role" "bedrock_agentcore_execution" {
  name = "BedrockAgentCoreRole"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid = "AssumeRolePolicy"
        Effect = "Allow"
        Principal = {
          Service = "bedrock-agentcore.amazonaws.com"
        }
        Action = "sts:AssumeRole"
        Condition = {
          StringEquals = {
            "aws:SourceAccount" = data.aws_caller_identity.current.account_id
          }
          ArnLike = {
            "aws:SourceArn" = "arn:aws:bedrock-agentcore:${var.aws_region}:${data.aws_caller_identity.current.account_id}:*"
          }
        }
      },
      {
        Sid = "AllowECSTaskRole"
        Effect = "Allow"
        Principal = {
          AWS = aws_iam_role.ecs_task.arn
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = var.tags
}

# Bedrock AgentCore Execution Role Policy
resource "aws_iam_role_policy" "bedrock_agentcore_execution" {
  name = "BedrockAgentCoreBrowserPolicy"
  role = aws_iam_role.bedrock_agentcore_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid = "BedrockAgentCoreInBuiltToolsFullAccess"
        Effect = "Allow"
        Action = [
          "bedrock-agentcore:CreateBrowser",
          "bedrock-agentcore:ListBrowsers",
          "bedrock-agentcore:GetBrowser",
          "bedrock-agentcore:DeleteBrowser",
          "bedrock-agentcore:StartBrowserSession",
          "bedrock-agentcore:ListBrowserSessions",
          "bedrock-agentcore:GetBrowserSession",
          "bedrock-agentcore:StopBrowserSession",
          "bedrock-agentcore:UpdateBrowserStream",
          "bedrock-agentcore:ConnectBrowserAutomationStream",
          "bedrock-agentcore:ConnectBrowserLiveViewStream"
        ]
        Resource = [
          "arn:aws:bedrock-agentcore:${var.aws_region}:${data.aws_caller_identity.current.account_id}:browser/*",
          "arn:aws:bedrock-agentcore:${var.aws_region}:${data.aws_caller_identity.current.account_id}:browser-custom/*"
        ]
      },
      {
        Sid = "BedrockAgentCoreBuiltInToolsS3Policy"
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:ListMultipartUploadParts",
          "s3:AbortMultipartUpload"
        ]
        Resource = "arn:aws:s3:::sanghwa-oregon/*"
        Condition = {
          StringEquals = {
            "aws:ResourceAccount" = data.aws_caller_identity.current.account_id
          }
        }
      },
      {
        Sid = "ECRImageAccess"
        Effect = "Allow"
        Action = [
          "ecr:BatchGetImage",
          "ecr:GetDownloadUrlForLayer",
          "ecr:GetAuthorizationToken"
        ]
        Resource = "*"
      },
      {
        Sid = "CloudWatchLogsAccess"
        Effect = "Allow"
        Action = [
          "logs:DescribeLogStreams",
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "logs:DescribeLogGroups"
        ]
        Resource = [
          "arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:log-group:/aws/bedrock-agentcore/runtimes/*",
          "arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:log-group:*"
        ]
      },
      {
        Sid = "XRayAccess"
        Effect = "Allow"
        Action = [
          "xray:PutTraceSegments",
          "xray:PutTelemetryRecords",
          "xray:GetSamplingRules",
          "xray:GetSamplingTargets"
        ]
        Resource = "*"
      },
      {
        Sid = "CloudWatchMetrics"
        Effect = "Allow"
        Action = [
          "cloudwatch:PutMetricData"
        ]
        Resource = "*"
        Condition = {
          StringEquals = {
            "cloudwatch:namespace" = "bedrock-agentcore"
          }
        }
      },
      {
        Sid = "GetAgentAccessToken"
        Effect = "Allow"
        Action = [
          "bedrock-agentcore:GetWorkloadAccessToken",
          "bedrock-agentcore:GetWorkloadAccessTokenForJWT",
          "bedrock-agentcore:GetWorkloadAccessTokenForUserId"
        ]
        Resource = [
          "arn:aws:bedrock-agentcore:${var.aws_region}:${data.aws_caller_identity.current.account_id}:workload-identity-directory/default",
          "arn:aws:bedrock-agentcore:${var.aws_region}:${data.aws_caller_identity.current.account_id}:workload-identity-directory/default/workload-identity/*"
        ]
      },
      {
        Sid = "BedrockModelInvocation"
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream"
        ]
        Resource = [
          "arn:aws:bedrock:*::foundation-model/*",
          "arn:aws:bedrock:${var.aws_region}:${data.aws_caller_identity.current.account_id}:*"
        ]
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

# Output the BedrockAgentCoreRole ARN for use in application configuration
output "bedrock_agentcore_role_arn" {
  description = "ARN of the Bedrock AgentCore execution role"
  value       = aws_iam_role.bedrock_agentcore_execution.arn
}

# Note: AmazonECSServiceRolePolicy is deprecated and no longer needed for ECS auto scaling