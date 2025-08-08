# LinkedIn Automation API

A comprehensive backend system for automated LinkedIn outreach campaigns, built with Flask and integrated with the Unipile API. This system enables businesses to manage clients, connect LinkedIn accounts, create personalized outreach sequences, and automate messaging while respecting LinkedIn's rate limits and best practices.

## 🚀 Features

### Core Functionality
- **Multi-tenant Client Management**: Manage multiple clients with isolated data
- **LinkedIn Account Integration**: Connect and manage LinkedIn accounts via Unipile API
- **Campaign Management**: Create and manage outreach campaigns with custom sequences
- **Lead Management**: Import, track, and manage leads throughout the outreach process
- **Automated Sequences**: Define multi-step outreach sequences with personalized messaging
- **Smart Scheduling**: Human-like timing with working hours and randomized delays
- **Webhook Integration**: Real-time event handling for connections and replies
- **Rate Limiting**: Built-in compliance with LinkedIn's usage policies

### Advanced Features
- **Template Personalization**: Dynamic message personalization with lead data
- **Background Job Scheduler**: Automated execution of outreach steps
- **Event Tracking**: Comprehensive logging of all outreach activities
- **Status Management**: Automatic lead status updates based on interactions
- **Multi-account Support**: Distribute outreach across multiple LinkedIn accounts
- **Timezone Support**: Respect working hours across different timezones
- **Comprehensive Duplication Management**: Prevent duplicate leads with database constraints and cross-campaign detection

## 🏗️ Architecture

### Technology Stack
- **Backend**: Python 3.11, Flask
- **Database**: SQLite (development), PostgreSQL (production)
- **Authentication**: JWT tokens
- **Scheduling**: APScheduler
- **External API**: Unipile for LinkedIn integration
- **Deployment**: Docker, Gunicorn, Nginx

### System Components
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │   API Gateway   │    │   LinkedIn      │
│   Application   │◄──►│   (Flask)       │◄──►│   (Unipile)     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │
                              ▼
                       ┌─────────────────┐
                       │   Database      │
                       │   (PostgreSQL)  │
                       └─────────────────┘
                              │
                              ▼
                       ┌─────────────────┐
                       │   Scheduler     │
                       │   (APScheduler) │
                       └─────────────────┘
```

## 📋 Prerequisites

- Python 3.11 or higher
- PostgreSQL (for production) or SQLite (for development)
- Unipile API account and credentials
- Domain with SSL certificate (for production webhooks)

## 🚀 Quick Start

### 1. Installation

```bash
# Clone the repository
git clone <repository-url>
cd linkedin-automation-api

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your configuration
nano .env
```

Required environment variables:
```bash
# Database
DATABASE_URL=sqlite:///linkedin_automation.db

# JWT
JWT_SECRET_KEY=your-super-secret-jwt-key

# Unipile API
UNIPILE_API_KEY=your_unipile_api_key
UNIPILE_DSN=your_unipile_dsn
UNIPILE_WEBHOOK_SECRET=your_webhook_secret

# Rate Limiting
MAX_CONNECTIONS_PER_DAY=25
MAX_MESSAGES_PER_DAY=100
```

### 3. Run the Application

```bash
# Start the development server
python src/main.py
```

The API will be available at `http://localhost:5000`

### 4. API Documentation

- **Comprehensive API Docs**: [COMPREHENSIVE_API_DOCUMENTATION.md](COMPREHENSIVE_API_DOCUMENTATION.md)
- **Deployment Guide**: [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)
- **Basic API Docs**: [API_DOCUMENTATION.md](API_DOCUMENTATION.md)

## 📊 API Overview

### Authentication
```bash
# Register a new user
POST /api/auth/register

# Login and get JWT token
POST /api/auth/login
```

### Client Management
```bash
# Create a client
POST /api/clients

# Get all clients
GET /api/clients
```

### Campaign Management
```bash
# Create a campaign
POST /api/clients/{client_id}/campaigns

# Start automation
POST /api/campaigns/{campaign_id}/start

# Check status
GET /api/campaigns/{campaign_id}/status
```

### Lead Management
```bash
# Import leads from LinkedIn
POST /api/campaigns/{campaign_id}/leads/import

# Convert public ID to provider ID
POST /api/leads/{lead_id}/convert-profile
```

## 🔧 Configuration

### Rate Limiting
The system implements LinkedIn-compliant rate limiting:

- **Connection Invitations**: 25 per day per account
- **Messages**: 100 per day per account
- **Working Hours**: 9 AM - 5 PM (configurable)
- **Delays**: 5-30 minutes between actions (randomized)

### Sequence Example
```json
[
  {
    "step_order": 1,
    "action_type": "invite",
    "template": "Hi {first_name}, I'd love to connect with you!",
    "delay_days": 0
  },
  {
    "step_order": 2,
    "action_type": "message",
    "template": "Thanks for connecting, {first_name}! I noticed your experience at {company_name}.",
    "delay_days": 2
  }
]
```

### Personalization Tokens
- `{first_name}`: Lead's first name
- `{last_name}`: Lead's last name
- `{full_name}`: Lead's full name
- `{company_name}`: Lead's company name

## 🔄 Workflow

### 1. Setup Phase
1. Register user account
2. Create client
3. Connect LinkedIn account via Unipile
4. Create campaign
5. Define outreach sequence

### 2. Lead Import Phase
1. Import leads from LinkedIn Sales Navigator
2. Convert public identifiers to provider IDs
3. Review and organize leads

### 3. Automation Phase
1. Start campaign automation
2. System schedules and executes outreach steps
3. Monitor progress and responses
4. Handle connection acceptances and replies automatically

### 4. Management Phase
1. Review campaign statistics
2. Manage responded leads
3. Adjust sequences and settings
4. Scale across multiple accounts

## 📈 Monitoring

### Campaign Metrics
- Total leads imported
- Invitations sent/accepted
- Messages sent/replied
- Response rates
- Current automation status

### System Metrics
- Daily rate limit usage
- Scheduled job status
- Webhook event processing
- Error rates and logs

## 🔒 Security

### Authentication & Authorization
- JWT-based authentication
- Client data isolation
- Secure webhook signature verification

### Rate Limiting & Compliance
- LinkedIn policy compliance
- Automatic rate limit enforcement
- Human-like behavior patterns
- Working hours respect

### Data Protection
- Encrypted sensitive data
- Secure API communications
- Webhook signature validation
- Input validation and sanitization

## 🚀 Deployment

### Development
```bash
python src/main.py
```

### Production with Docker
```bash
docker-compose up -d
```

### Production with Gunicorn
```bash
gunicorn -c gunicorn.conf.py src.main:app
```

See [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) for detailed deployment instructions.

## 📁 Project Structure

```
linkedin-automation-api/
├── src/
│   ├── main.py                 # Application entry point
│   ├── config.py              # Configuration settings
│   ├── models/                # Database models
│   │   ├── __init__.py
│   │   ├── client.py
│   │   ├── linkedin_account.py
│   │   ├── campaign.py
│   │   ├── lead.py
│   │   ├── event.py
│   │   └── webhook.py
│   ├── routes/                # API endpoints
│   │   ├── auth.py
│   │   ├── client.py
│   │   ├── linkedin_account.py
│   │   ├── unipile_auth.py
│   │   ├── campaign.py
│   │   ├── lead.py
│   │   ├── sequence.py
│   │   ├── automation.py
│   │   └── webhook.py
│   └── services/              # Business logic
│       ├── unipile_client.py
│       ├── sequence_engine.py
│       └── scheduler.py
├── requirements.txt           # Python dependencies
├── .env.example              # Environment template
├── README.md                 # This file
├── API_DOCUMENTATION.md      # Basic API docs
├── COMPREHENSIVE_API_DOCUMENTATION.md  # Detailed API docs
├── DUPLICATION_MANAGEMENT_GUIDE.md     # Duplication management guide
├── DUPLICATION_QUICK_REFERENCE.md      # Quick reference card
└── DEPLOYMENT_GUIDE.md       # Deployment instructions
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

### Documentation
- [Comprehensive API Documentation](COMPREHENSIVE_API_DOCUMENTATION.md)
- [Duplication Management Guide](DUPLICATION_MANAGEMENT_GUIDE.md)
- [Deployment Guide](DEPLOYMENT_GUIDE.md)
- [Basic API Documentation](API_DOCUMENTATION.md)

### Common Issues
1. **Database Connection**: Check DATABASE_URL format
2. **Unipile Integration**: Verify API credentials
3. **Webhook Delivery**: Ensure HTTPS endpoints
4. **Rate Limiting**: Monitor daily usage limits
5. **Duplicate Leads**: Use duplication management endpoints to prevent and handle duplicates

### Getting Help
- Check the documentation first
- Review error logs for specific issues
- Ensure all environment variables are set correctly
- Verify Unipile API credentials and permissions

## 🔮 Roadmap

### Upcoming Features
- [ ] Advanced analytics dashboard
- [ ] A/B testing for message templates
- [ ] Integration with CRM systems
- [ ] Advanced lead scoring
- [ ] Multi-language support
- [ ] Advanced reporting and exports

### Performance Improvements
- [ ] Redis caching layer
- [ ] Database query optimization
- [ ] Async processing for webhooks
- [ ] Load balancing support

## 📊 System Requirements

### Minimum Requirements
- **CPU**: 1 vCPU
- **RAM**: 512 MB
- **Storage**: 1 GB
- **Network**: Stable internet connection

### Recommended for Production
- **CPU**: 2+ vCPUs
- **RAM**: 2+ GB
- **Storage**: 10+ GB SSD
- **Database**: PostgreSQL with connection pooling
- **Load Balancer**: Nginx or similar
- **Monitoring**: Application and infrastructure monitoring

---

**Built with ❤️ for automated LinkedIn outreach that respects platform policies and user experience.**

