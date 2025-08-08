# Fly.io Deployment Guide for LinkedIn Automation API

## Overview
This guide provides step-by-step instructions for deploying the LinkedIn Automation API to Fly.io.

## Prerequisites
- Fly.io CLI installed and authenticated
- PostgreSQL database (already configured: `postgresql://postgres:e120fleB@213.188.197.151:5432/postgres`)
- Unipile API credentials

## Step 1: Update Environment Variables

### 1.1 Update fly.toml with Real Values
Edit the `fly.toml` file and replace the placeholder values with your actual production values:

```toml
[env]
  FLASK_ENV = "production"
  PORT = "5001"
  # Database Configuration
  DATABASE_URL = "postgresql://postgres:e120fleB@213.188.197.151:5432/postgres"
  # Security Configuration (CHANGE THESE!)
  SECRET_KEY = "your-actual-super-secret-production-key"
  JWT_SECRET_KEY = "your-actual-jwt-secret-production-key"
  # Unipile API Configuration
  UNIPILE_API_KEY = "your-actual-unipile-api-key"
  UNIPILE_WEBHOOK_SECRET = "your-actual-unipile-webhook-secret"
  # CORS Configuration
  CORS_ORIGINS = "https://linkedin-automation-api.fly.dev,https://yourdomain.com"
  # Rate Limiting Configuration
  MAX_CONNECTIONS_PER_DAY = "25"
  MAX_MESSAGES_PER_DAY = "100"
  MIN_DELAY_BETWEEN_ACTIONS = "300"
  MAX_DELAY_BETWEEN_ACTIONS = "1800"
  WORKING_HOURS_START = "9"
  WORKING_HOURS_END = "17"
  # Logging Configuration
  LOG_LEVEL = "INFO"
```

### 1.2 Set Environment Variables via CLI (Alternative)
You can also set environment variables using the Fly.io CLI:

```bash
fly secrets set SECRET_KEY="your-actual-super-secret-production-key"
fly secrets set JWT_SECRET_KEY="your-actual-jwt-secret-production-key"
fly secrets set UNIPILE_API_KEY="your-actual-unipile-api-key"
fly secrets set UNIPILE_WEBHOOK_SECRET="your-actual-unipile-webhook-secret"
fly secrets set CORS_ORIGINS="https://linkedin-automation-api.fly.dev,https://yourdomain.com"
```

## Step 2: Deploy to Fly.io

### 2.1 Build and Deploy
```bash
# Deploy the application
fly deploy

# Check deployment status
fly status
```

### 2.2 Monitor Deployment
```bash
# View logs
fly logs

# Check app health
fly health check
```

## Step 3: Verify Deployment

### 3.1 Test API Endpoints
```bash
# Test the root endpoint
curl https://linkedin-automation-api.fly.dev/

# Test authentication
curl -X POST https://linkedin-automation-api.fly.dev/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"api_key":"linkedin-automation-api-key"}'
```

### 3.2 Check Application Status
```bash
# View running instances
fly status

# Check resource usage
fly status --all
```

## Step 4: Configure Webhooks (Optional)

If you're using Unipile webhooks, update your webhook URLs to point to your Fly.io deployment:

```
https://linkedin-automation-api.fly.dev/api/webhooks/unipile/users
https://linkedin-automation-api.fly.dev/api/webhooks/unipile/messaging
```

## Step 5: Monitoring and Maintenance

### 5.1 View Logs
```bash
# Real-time logs
fly logs --follow

# Historical logs
fly logs --since=1h
```

### 5.2 Scale Application
```bash
# Scale to multiple instances
fly scale count 2

# Scale memory/CPU
fly scale memory 2048
fly scale cpu 2
```

### 5.3 Restart Application
```bash
# Restart all instances
fly apps restart

# Restart specific instance
fly machine restart <machine-id>
```

## Troubleshooting

### Common Issues

1. **Application Won't Start**
   - Check logs: `fly logs`
   - Verify environment variables are set correctly
   - Ensure database is accessible

2. **Health Check Failures**
   - Verify the health check endpoint is working
   - Check if the application is binding to the correct port

3. **Database Connection Issues**
   - Verify DATABASE_URL is correct
   - Check if the database is accessible from Fly.io

4. **Memory Issues**
   - Monitor memory usage: `fly status --all`
   - Scale up memory if needed: `fly scale memory 2048`

### Debug Commands
```bash
# SSH into the running instance
fly ssh console

# View detailed app information
fly info

# Check machine status
fly machine list
```

## Security Considerations

1. **Environment Variables**: Never commit real secrets to version control
2. **API Keys**: Use Fly.io secrets for sensitive data
3. **CORS**: Configure CORS_ORIGINS to only allow your domains
4. **Database**: Ensure your PostgreSQL database has proper security

## Performance Optimization

1. **Scaling**: Start with 1 instance and scale based on usage
2. **Memory**: Monitor memory usage and adjust as needed
3. **Database**: Consider connection pooling for high traffic
4. **Caching**: Implement Redis for job persistence if needed

## Backup and Recovery

1. **Database Backups**: Ensure your PostgreSQL database has regular backups
2. **Application Backups**: Use version control for code backups
3. **Environment Backups**: Document all environment variables

## Support

If you encounter issues:
1. Check the Fly.io documentation: https://fly.io/docs/
2. View application logs: `fly logs`
3. Check Fly.io status: https://status.fly.io/ 