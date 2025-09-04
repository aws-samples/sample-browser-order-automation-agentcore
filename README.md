# Order Automation System

A production-ready e-commerce order automation platform powered by AI agents and intelligent browser automation.

## Overview

This system provides enterprise-grade automation for e-commerce order processing using advanced AI agents and browser automation technologies. It supports multiple automation methods, human-in-the-loop workflows, and real-time monitoring.

## Key Features

### AI-Powered Automation
- **Strands Agents**: Advanced AI agents using the Strands SDK for intelligent decision-making
- **Playwright MCP**: Structured browser automation with Model Context Protocol integration
- **Multi-step Reasoning**: Complex order processing with autonomous problem-solving

### Multi-Retailer Support
- **Gucci**: Premium luxury fashion automation
- **Valentino**: High-end designer goods processing
- **Net-A-Porter**: Luxury fashion marketplace
- **Farfetch**: Global fashion platform
- **Configurable**: Easy addition of new retailers

### Human-in-the-Loop
- **CAPTCHA Handling**: Automatic escalation for human intervention
- **Review Queue**: Manual review for complex scenarios
- **Error Recovery**: Intelligent fallback and retry mechanisms
- **Real-time Notifications**: Instant alerts for human attention

### Production Monitoring
- **Real-time Dashboard**: Live order tracking and metrics
- **Queue Management**: Priority-based order processing
- **Performance Analytics**: Success rates, processing times, and trends
- **Browser Session Monitoring**: Live thumbnails and session management

### Enterprise Configuration
- **Database Flexibility**: SQLite for local, PostgreSQL/RDS for production
- **Scalable Architecture**: Microservices-ready design
- **Security**: Token-based authentication and encrypted data
- **Observability**: Comprehensive logging and metrics

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │   Backend API   │    │   Automation    │
│   (React +      │◄──►│   (FastAPI)     │◄──►│   Agents        │
│   Cloudscape)   │    │                 │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   WebSocket     │    │   Database      │    │   Browser       │
│   Real-time     │    │   (SQLite/RDS)  │    │   Sessions      │
│   Updates       │    │                 │    │   (Playwright)  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### Core Components

#### Automation Agents
- **Strands Agent**: Uses Strands SDK for intelligent browser control with LLM reasoning
- **Playwright MCP Agent**: Structured automation with accessibility-driven interactions
- **Session Manager**: Browser lifecycle and resource management

#### Order Queue System
- **Priority Processing**: High, normal, low priority queues
- **Concurrent Execution**: Configurable parallel order processing
- **Retry Logic**: Intelligent error recovery and retry mechanisms
- **Human Escalation**: Automatic handoff for complex scenarios

#### Data Layer
- **Order Management**: Complete order lifecycle tracking
- **Configuration**: Retailer settings and automation parameters
- **Session Tracking**: Browser session state and thumbnails
- **Metrics**: Performance and success rate analytics

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- Docker (optional)

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd order-automation-system
   ```

2. **Backend Setup**
   ```bash
   cd backend
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Frontend Setup**
   ```bash
   cd frontend
   npm install
   ```

4. **Environment Configuration**
   ```bash
   # Backend environment
   cp backend/.env.example backend/.env
   
   # Configure your API keys
   export ANTHROPIC_API_KEY="your-anthropic-key"
   export AWS_ACCESS_KEY_ID="your-aws-key"
   export AWS_SECRET_ACCESS_KEY="your-aws-secret"
   ```

5. **Database Setup**
   ```bash
   # For local development (SQLite)
   cd backend
   python -c "from database import DatabaseManager; DatabaseManager()"
   
   # For production (PostgreSQL)
   export DATABASE_URL="postgresql://user:pass@localhost/orderdb"
   ```

### Running the Application

#### Development Mode
```bash
# Start backend (from backend directory)
python app.py

# Start frontend (from frontend directory)
npm start
```

#### Production Mode
```bash
# Using the provided script
./start.sh

# Or manually
cd backend && uvicorn app:app --host 0.0.0.0 --port 8000 &
cd frontend && npm run build && npx serve -s build -l 3000
```

#### Docker Deployment
```bash
docker-compose up -d
```

## Configuration

### Retailer Configuration
Configure supported retailers in `backend/config_manager.py`:

```python
SUPPORTED_RETAILERS = {
    "gucci": {
        "name": "Gucci",
        "base_url": "https://www.gucci.com",
        "automation_methods": ["strands_agent", "playwright_mcp"],
        "preferred_method": "strands_agent",
        "selectors": {
            "size_selector": "[data-testid='size-selector']",
            "add_to_cart": "[data-testid='add-to-cart-button']"
        }
    }
}
```

### Automation Methods
- **Strands Agent**: AI-powered with natural language understanding
- **Playwright MCP**: Structured automation with accessibility focus

### Queue Settings
```python
QUEUE_SETTINGS = {
    "max_concurrent_orders": 5,
    "order_timeout_minutes": 30,
    "retry_delay_seconds": 60,
    "max_queue_size": 100
}
```

## API Documentation

### Order Management
- `POST /api/orders` - Create new order
- `GET /api/orders` - List orders with filtering
- `GET /api/orders/{id}` - Get specific order
- `PUT /api/orders/{id}` - Update order (human review)
- `DELETE /api/orders/{id}` - Cancel order

### Queue Management
- `GET /api/queue/metrics` - Get queue statistics
- `POST /api/queue/pause` - Pause order processing
- `POST /api/queue/resume` - Resume order processing

### Configuration
- `GET /api/config/retailers` - Get supported retailers
- `GET /api/config/automation-methods` - Get automation methods
- `PUT /api/config/system` - Update system configuration

### Human Review
- `GET /api/review/queue` - Get orders requiring review
- `POST /api/review/{id}/resolve` - Resolve human review

## Testing

### Backend Tests
```bash
cd backend
pytest tests/ -v
```

### Frontend Tests
```bash
cd frontend
npm test
```

### Integration Tests
```bash
# Run full system tests
python tests/integration/test_order_flow.py
```

## Monitoring & Observability

### Metrics Available
- **Order Success Rate**: Percentage of successfully completed orders
- **Processing Time**: Average time per order completion
- **Queue Depth**: Current pending orders
- **Error Rates**: Failure rates by retailer and method
- **Human Intervention Rate**: Percentage requiring manual review

### Real-time Monitoring
- WebSocket-based live updates
- Browser session thumbnails
- Progress tracking with detailed steps
- Error notifications and alerts

### Logging
- Structured logging with correlation IDs
- Configurable log levels
- Integration with external monitoring systems

## Security

### Data Protection
- Payment information tokenization
- Encrypted sensitive data storage
- Secure API key management
- Session-based authentication

### Network Security
- CORS configuration
- Rate limiting
- Input validation and sanitization
- Secure WebSocket connections

## Deployment

### Local Development
- SQLite database
- File-based configuration
- Local browser sessions

### Production Deployment
- PostgreSQL/RDS database
- Environment-based configuration
- Distributed browser sessions
- Load balancing support

### Docker Deployment
```yaml
version: '3.8'
services:
  backend:
    build: ./backend
    environment:
      - DATABASE_URL=postgresql://user:pass@db:5432/orderdb
    depends_on:
      - db
  
  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
  
  db:
    image: postgres:15
    environment:
      - POSTGRES_DB=orderdb
```

### AWS Deployment
- ECS/Fargate for containerized deployment
- RDS for managed database
- CloudWatch for monitoring
- ALB for load balancing

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Guidelines
- Follow PEP 8 for Python code
- Use ESLint/Prettier for JavaScript
- Write tests for new features
- Update documentation

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

### Documentation
- [API Documentation](http://localhost:8000/docs) - Interactive API docs
- [Architecture Guide](docs/architecture.md) - System design details
- [Configuration Reference](docs/configuration.md) - Complete config options

### Getting Help
- Create an issue for bugs or feature requests
- Check existing issues for solutions
- Review the troubleshooting guide

### Troubleshooting

#### Common Issues
1. **Database Connection Errors**
   - Check DATABASE_URL environment variable
   - Ensure database server is running
   - Verify credentials and permissions

2. **Browser Automation Failures**
   - Install Playwright browsers: `playwright install`
   - Check for CAPTCHA requirements
   - Verify retailer website accessibility

3. **WebSocket Connection Issues**
   - Check CORS configuration
   - Verify backend server is running
   - Check firewall settings

#### Performance Optimization
- Adjust `max_concurrent_orders` based on system resources
- Monitor memory usage with multiple browser sessions
- Use headless mode for better performance
- Configure appropriate timeouts

## Roadmap

### Upcoming Features
- [ ] Multi-language support
- [ ] Advanced analytics dashboard
- [ ] Mobile app for monitoring
- [ ] Webhook integrations
- [ ] Advanced retry strategies
- [ ] Machine learning optimization

### Long-term Goals
- [ ] Multi-tenant architecture
- [ ] Global deployment support
- [ ] Advanced AI agent capabilities
- [ ] Integration marketplace
- [ ] Enterprise SSO support

---

**Built with modern web technologies and AI-powered automation.**