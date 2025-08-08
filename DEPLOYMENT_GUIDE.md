# LinkedIn Automation API - Production Deployment Guide

This guide covers deploying the LinkedIn Automation API to Fly.io for production use.

## Prerequisites

1. **Fly.io Account**: Sign up at [fly.io](https://fly.io)
2. **Fly CLI**: Install the Fly CLI tool
3. **PostgreSQL Database**: ✅ **Already configured** - Using existing database at `213.188.197.151:5432`
4. **Redis**: Set up Redis for job persistence (optional but recommended)

## Environment Variables

The application is already configured with your existing PostgreSQL database. For production deployment, you'll need to set the following environment variables in Fly.io:

```bash
# Required for Production
FLASK_ENV=production
SECRET_KEY=your-super-secret-key-here
JWT_SECRET_KEY=your-jwt-secret-key-here
DATABASE_URL=postgresql://postgres:e120fleB@213.188.197.151:5432/postgres
UNIPILE_API_KEY=your-unipile-api-key
UNIPILE_WEBHOOK_SECRET=your-unipile-webhook-secret

# Optional Configuration
CORS_ORIGINS=https://yourdomain.com,https://app.yourdomain.com
MAX_CONNECTIONS_PER_DAY=25
MAX_MESSAGES_PER_DAY=100
MIN_DELAY_BETWEEN_ACTIONS=300
MAX_DELAY_BETWEEN_ACTIONS=1800
WORKING_HOURS_START=9
WORKING_HOURS_END=17
LOG_LEVEL=INFO
```

## Database Setup

✅ **PostgreSQL Database Already Configured**

Your application is already using a PostgreSQL database at:
- **Host**: `213.188.197.151`
- **Port**: `5432`
- **Database**: `postgres`
- **User**: `postgres`

The database connection has been tested and is working correctly.

## Deployment Steps

### 1. Install Fly CLI

```bash
# macOS
brew install flyctl

# Linux
curl -L https://fly.io/install.sh | sh

# Windows
# Download from https://fly.io/docs/hands-on/install-flyctl/
```

### 2. Login to Fly.io

```bash
fly auth login
```

### 3. Create the App

```bash
fly apps create linkedin-automation-api
```

### 4. Set Environment Variables

```bash
fly secrets set SECRET_KEY="your-super-secret-key-here"
fly secrets set JWT_SECRET_KEY="your-jwt-secret-key-here"
fly secrets set DATABASE_URL="postgresql://postgres:e120fleB@213.188.197.151:5432/postgres"
fly secrets set UNIPILE_API_KEY="your-unipile-api-key"
fly secrets set UNIPILE_WEBHOOK_SECRET="your-unipile-webhook-secret"
fly secrets set CORS_ORIGINS="https://yourdomain.com,https://app.yourdomain.com"
```

### 5. Deploy the Application

```bash
fly deploy
```

### 6. Scale the Application

```bash
# Scale to 1 machine (minimum for automation)
fly scale count 1

# Scale to multiple machines for high availability
fly scale count 3
```

## Monitoring and Logs

### View Logs

```bash
# View real-time logs
fly logs

# View logs for specific machine
fly logs --machine-id <machine-id>
```

### Monitor Application

```bash
# Check app status
fly status

# Check machine status
fly machines list
```

## Health Checks

The application includes health checks that monitor:

- API endpoint availability (`/api/auth/login`)
- Database connectivity
- Scheduler status

## Security Considerations

1. **Environment Variables**: Never commit secrets to version control
2. **CORS**: Configure `CORS_ORIGINS` to only allow your frontend domains
3. **Rate Limiting**: The API includes built-in rate limiting for LinkedIn actions
4. **HTTPS**: Fly.io automatically provides HTTPS certificates
5. **Database Security**: Your PostgreSQL database is already secured with authentication

## Troubleshooting

### Common Issues

1. **Database Connection Errors**
   - ✅ Database connection is already tested and working
   - Verify `DATABASE_URL` is correctly set in Fly.io secrets

2. **Scheduler Not Starting**
   - Check logs for scheduler errors
   - Verify environment variables are set

3. **LinkedIn API Errors**
   - Verify `UNIPILE_API_KEY` is valid
   - Check Unipile account status

### Debug Commands

```bash
# SSH into a machine
fly ssh console

# Check environment variables
fly ssh console -C "env | grep -E '(SECRET|DATABASE|UNIPILE)'"

# Check application logs
fly logs --app linkedin-automation-api
```

## Backup and Recovery

### Database Backups

Since you're using an external PostgreSQL database, coordinate backups with your database provider.

```bash
# Test database connection from Fly.io
fly ssh console -C "python -c \"import psycopg2; conn = psycopg2.connect('postgresql://postgres:e120fleB@213.188.197.151:5432/postgres'); print('Database connection successful'); conn.close()\""
```

## Scaling

### Vertical Scaling

```bash
# Increase memory
fly scale memory 2048

# Increase CPU
fly scale cpu 2
```

### Horizontal Scaling

```bash
# Scale to multiple machines
fly scale count 3

# Scale to specific regions
fly scale count 2 --region lhr
fly scale count 1 --region jfk
```

## Cost Optimization

1. **Auto-scaling**: Use `auto_stop_machines = true` in fly.toml
2. **Resource limits**: Set appropriate CPU and memory limits
3. **Database**: You're already using an external PostgreSQL database

## Support

For issues with:
- **Fly.io**: Check [Fly.io documentation](https://fly.io/docs)
- **Application**: Check logs and this deployment guide
- **LinkedIn API**: Contact Unipile support
- **Database**: Contact your PostgreSQL provider

## Next Steps

After deployment:

1. Test all API endpoints
2. Verify automation is working
3. Set up monitoring and alerting
4. Configure webhook endpoints in Unipile
5. Test the complete automation flow

