# Browser Order Automation with Amazon Bedrock AgentCore

A sample e-commerce order automation application built on Amazon Bedrock AgentCore Browser with Nova Act, Strands Agent, and Playwright MCP for secure browser automation and intelligent agent orchestration capabilities.

**Note**: This is a sample application for demonstration purposes. Review and modify security settings, resource configurations, and access policies according to your organization's requirements before deploying to production environments.

## Key Features

- **AI-Powered Automation**: Nova Act or Amazon Bedrock models (e.g. Sonnet 4, Opus 4.1) for intelligent order processing
- **Secure Browser Automation**: Amazon Bedrock AgentCore Browser Tool provides isolated, managed browser environment
- **Multi-Agent Architecture**: Strands Agent orchestrates Nova Act and Playwright MCP agents for complex workflows
- **Real-time Monitoring**: WebSocket connections for live order tracking and browser session viewing
- **Human-in-the-Loop**: Manual intervention with live browser view, session replay, and manual control takeover
- **Batch Processing**: CSV upload support for bulk order automation with priority queuing
- **Secure Credential Management**: AWS Secrets Manager for encrypted credential storage with KMS encryption
- **High Availability**: Multi-AZ deployment with auto-scaling ECS Fargate tasks
- **Enterprise Security**: VPC isolation, WAF protection, encrypted storage, and IAM-based access control

## Architecture Overview

![Architecture Diagram](browser-order-automation.drawio.png)

This solution demonstrates a modern, cloud-native approach to e-commerce order automation using AWS services including Amazon Bedrock, AgentCore Browser Tool, ECS Fargate, and CloudFront. The system processes orders through an AI pipeline that automates web interactions, validates data, and provides real-time monitoring with human-in-the-loop capabilities.

### System Components

**Frontend Layer**
- React 18 application with AWS Cloudscape Design System
- CloudFront distribution for global content delivery
- Real-time WebSocket connections for order status updates
- Live browser view with DCV streaming and session replay

**Backend Layer**
- Python FastAPI application with asynchronous job processing
- ARM64-optimized ECS Fargate containers
- Priority-based job queue with concurrent workers (1-10 configurable)
- WebSocket server for real-time updates

**AI & Automation Layer**
- Amazon Bedrock for Claude model access
- AgentCore Browser Tool for secure web automation
- Strands Agent for workflow orchestration
- Nova Act for AI-powered browser intelligence
- Playwright MCP Agent for browser actuation

**Data & Security Layer**
- Amazon RDS PostgreSQL for production, SQLite for development
- AWS Secrets Manager for credential storage with KMS encryption
- S3 for file uploads and session recordings
- CloudWatch for metrics, logging, and monitoring
## Application Logic Flow

### Order Processing Pipeline

```mermaid
graph TD
    A[User Upload] --> B[Order Validation]
    B --> C[Job Creation]
    C --> D[Priority Queue]
    D --> E[Agent Selection]
    E --> F[Browser Automation]
    F --> G[Real-time Monitoring]
    G --> H{Success?}
    H -->|Yes| I[Order Complete]
    H -->|Issues| J[Human Review]
    J --> K[Manual Resolution]
    K --> I
```

**Processing Flow:**
1. **Order Creation**: User uploads single order or CSV batch with priority assignment
2. **Queue Management**: Priority-based FIFO processing with configurable workers
3. **Agent Orchestration**: Strands Agent coordinates Nova Act (AI) and Playwright MCP (browser control)
4. **Browser Automation**: AgentCore Browser Tool provides isolated sessions with live monitoring
5. **Human Review**: Complex cases routed for manual intervention with live browser control

### System Interaction Flow

```mermaid
sequenceDiagram
    participant U as User
    participant F as Frontend
    participant A as FastAPI
    participant Q as Job Queue
    participant S as Strands Agent
    participant B as AgentCore Browser
    participant SM as Secrets Manager

    U->>F: Upload order/CSV
    F->>A: POST /api/orders
    A->>Q: Add to priority queue
    A->>F: Return job ID
    
    loop Background Processing
        Q->>S: Get next job
        S->>SM: Retrieve credentials
        S->>B: Start browser session
        B->>S: Live view URL
        S->>A: Progress updates
        A->>F: WebSocket updates
        F->>U: Real-time status
    end
```

### Agent Architecture

**Strands Agent** - Main orchestrator
- Workflow coordination and state management
- Credential retrieval from AWS Secrets Manager
- Browser session lifecycle management
- Progress tracking and error handling

**Nova Act** - AI-powered browser intelligence
- Natural language to browser actions
- Visual understanding of web pages
- Adaptive navigation strategies
- CAPTCHA detection and human escalation

**Playwright MCP** - Browser actuation
- Low-level browser control and element interaction
- Form filling and submission
- Network request monitoring
## Quick Start

### Prerequisites

**Local Development**
- Python 3.9+
- Node.js 16+
- AWS CLI configured with appropriate permissions

**AWS Deployment**
- AWS Account with Bedrock and AgentCore access
- Terraform 1.0+
- Domain registered in Route 53 (optional)

### Local Development

```bash
# Clone the repository
git clone <repository-url>
cd browser-order-automation-agentcore

# Backend setup
cd backend
pip install -r requirements.txt
python app.py  # Starts on port 8000

# Frontend setup (new terminal)
cd frontend
npm install
npm start  # Starts on port 3000
```

Access the application at `http://localhost:3000`

### Environment Configuration

**Backend** (create `backend/.env`):
```bash
AWS_REGION=us-west-2
FLASK_ENV=development
ALLOWED_ORIGINS=http://localhost:3000

# Optional - uses SQLite if not set
# DATABASE_URL=postgresql://user:pass@host:5432/dbname
```

**Frontend** (create `frontend/.env`):
```bash
REACT_APP_API_URL=http://localhost:8000
```

### AWS Deployment

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your configuration

terraform init
terraform plan
terraform apply
```

## Core Features

### Order Management
- **Single Orders**: Create individual orders with product URL, customer details, and automation method
- **Batch Processing**: CSV upload for bulk orders with priority assignment
- **Queue Management**: Priority-based processing (Low, Normal, High, Urgent)
- **Status Tracking**: Real-time updates via WebSocket connections

### Browser Automation
- **Live View**: Real-time browser session viewing with DCV streaming
- **Session Replay**: Recorded sessions for completed orders
- **Manual Control**: Human takeover capability during automation
- **Screenshot Capture**: Automatic screenshots at each automation step

### Secret Management
- **AWS Secrets Manager**: Encrypted credential storage with KMS
- **Web UI**: Secret Vault interface for managing retailer credentials
- **Automatic Retrieval**: Seamless credential access during automation
- **Audit Logging**: Full CloudTrail integration for compliance

### Monitoring & Observability
- **Real-time Dashboard**: Order status, queue metrics, and system health
- **WebSocket Updates**: Live progress tracking and notifications
- **CloudWatch Integration**: Metrics, logs, and alarms
- **Health Checks**: Application and infrastructure monitoring## AP
I Reference

### Order Management

```http
POST /api/orders
Content-Type: application/json

{
  "retailer": "sample_retailer",
  "automation_method": "nova_act",
  "product": {
    "url": "https://example.com/product",
    "name": "Product Name",
    "size": "M",
    "color": "Blue",
    "price": 99.99
  },
  "customer_name": "John Doe",
  "customer_email": "john@example.com",
  "shipping_address": {...},
  "priority": "normal"
}
```

```http
GET /api/orders/{order_id}
GET /api/orders?status=processing&limit=50
DELETE /api/orders/{order_id}  # Cancel order
```

### Batch Processing

```http
POST /api/orders/upload-csv
Content-Type: multipart/form-data

file: CSV file
automation_method: "nova_act" | "strands"
ai_model: "nova_act" | "claude-sonnet-4"
```

### Live Monitoring

```http
GET /api/orders/{order_id}/live-view
GET /api/orders/{order_id}/session-replay
POST /api/orders/{order_id}/take-control
POST /api/orders/{order_id}/release-control
```

### Secret Management

```http
GET /api/secrets
POST /api/secrets
GET /api/secrets/{site_name}
PUT /api/secrets/{site_name}
DELETE /api/secrets/{site_name}
```

### WebSocket Events

```javascript
// Connect to real-time updates
const ws = new WebSocket('ws://localhost:8000/ws');

// Order status updates
{
  "type": "order_updated",
  "order_id": "uuid",
  "status": "processing",
  "progress": 45
}

// Live browser screenshots
{
  "type": "screenshot",
  "order_id": "uuid",
  "image_url": "/api/screenshots/image.png"
}
```

## Security Considerations

### AWS Secrets Manager Integration
- **Encryption**: Automatic KMS encryption for all stored credentials
- **Access Control**: IAM-based permissions with least privilege
- **Audit Trail**: CloudTrail logging for all secret access
- **Rotation**: Built-in support for automatic credential rotation

### Network Security
- **VPC Isolation**: Private subnets for application and database tiers
- **WAF Protection**: Application firewall with common attack prevention
- **TLS Encryption**: HTTPS/TLS for all data in transit
- **Security Groups**: Least-privilege network access rules

### Browser Security
- **Isolated Sessions**: AgentCore Browser Tool provides containerized environments
- **Session Cleanup**: Automatic cleanup after order completion
- **Access Logging**: Detailed audit logs for all browser interactions

## Deployment

### Terraform Configuration

Key variables in `terraform.tfvars`:

```hcl
project_name = "order-automation"
environment  = "prod"
aws_region   = "us-west-2"

# Optional custom domain
domain_name = "orders.yourdomain.com"

# ECS Configuration
ecs_task_cpu      = 512
ecs_task_memory   = 1024
ecs_desired_count = 2
enable_auto_scaling = true
```

### Infrastructure Components
- **ECS Fargate**: Containerized application with auto-scaling
- **Application Load Balancer**: Traffic distribution with health checks
- **RDS PostgreSQL**: Managed database with encryption
- **CloudFront**: Global content delivery network
- **S3**: Static assets and file storage
- **Secrets Manager**: Encrypted credential storage

## Monitoring

### CloudWatch Metrics
- ECS service metrics (CPU, memory, task count)
- Application Load Balancer metrics (requests, latency)
- Custom application metrics (order processing, queue depth)

### Health Checks
- Application health endpoint: `GET /health`
- ECS container health checks
- ALB target group health monitoring

### Logging
- Structured JSON logging with multiple levels
- CloudWatch Logs integration
- Real-time log streaming and filtering

## Development

### Local Development
1. **Database**: Automatic SQLite when `DATABASE_URL` not set
2. **AWS Services**: Configure AWS CLI with development credentials
3. **Hot Reload**: Both frontend and backend support hot reload

### Testing
```bash
# Backend tests
cd backend && python -m pytest tests/

# Frontend tests
cd frontend && npm test

# Integration tests
npm run test:integration
```

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Support

For questions, issues, or contributions:
1. Check existing [Issues](../../issues)
2. Create a new issue with detailed description
3. Review [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines

## Additional Resources

- [Amazon Bedrock Documentation](https://docs.aws.amazon.com/bedrock/)
- [Amazon Bedrock AgentCore Browser Tool](https://docs.aws.amazon.com/bedrock/latest/userguide/agentcore-browser.html)
- [AWS Secrets Manager Best Practices](https://docs.aws.amazon.com/secretsmanager/latest/userguide/best-practices.html)
- [ECS Fargate Best Practices](https://docs.aws.amazon.com/AmazonECS/latest/bestpracticesguide/)
- [React Cloudscape Design System](https://cloudscape.design/)

---

**Note**: This is a sample application for demonstration purposes. Review and modify security settings, resource configurations, and access policies according to your organization's requirements before deploying to production environments.