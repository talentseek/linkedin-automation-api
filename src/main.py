import os
import sys
import logging
from flask import Flask, send_from_directory, jsonify
from flask_cors import CORS

# Add src directory to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.config import config
from src.extensions import db, jwt

# Global scheduler instance - will be initialized lazily
outreach_scheduler = None

def create_app(config_name=None):
    """Application factory pattern."""
    app = Flask(__name__)
    
    # Load configuration
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')
    
    app.config.from_object(config[config_name])
    
    # Validate production configuration if needed
    if config_name == 'production':
        config[config_name].validate_config()
    
    # Configure CORS
    CORS(app, origins=app.config['CORS_ORIGINS'], supports_credentials=True)
    
    # Initialize extensions
    db.init_app(app)
    jwt.init_app(app)
    
    # Register blueprints
    from src.routes.auth import auth_bp
    from src.routes.client import client_bp
    from src.routes.campaign import campaign_bp
    from src.routes.lead import lead_bp  # Now uses modular structure
    from src.routes.automation import automation_bp
    from src.routes.webhook import webhook_bp  # Now uses modular structure
    from src.routes.sequence import sequence_bp
    from src.routes.analytics import analytics_bp
    from src.routes.linkedin_account import linkedin_account_bp
    from src.routes.unipile_auth import unipile_auth_bp
    from src.routes.user import user_bp
    from src.routes.admin import admin_bp
    
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(client_bp, url_prefix='/api/clients')
    app.register_blueprint(campaign_bp, url_prefix='/api/campaigns')
    app.register_blueprint(lead_bp, url_prefix='/api/leads')
    app.register_blueprint(automation_bp, url_prefix='/api/automation')
    app.register_blueprint(webhook_bp, url_prefix='/api/webhooks')
    app.register_blueprint(sequence_bp, url_prefix='/api/sequence')
    app.register_blueprint(analytics_bp, url_prefix='/api/analytics')
    app.register_blueprint(linkedin_account_bp, url_prefix='/api/linkedin-accounts')
    app.register_blueprint(unipile_auth_bp, url_prefix='/api/unipile-auth')
    app.register_blueprint(user_bp, url_prefix='/api/users')
    app.register_blueprint(admin_bp, url_prefix='/api/admin')
    
    # Initialize scheduler with app context
    from src.services.scheduler import get_outreach_scheduler  # Now uses modular structure
    global outreach_scheduler
    outreach_scheduler = get_outreach_scheduler()
    outreach_scheduler.init_app(app)
    
    # Set the global instance in the scheduler module
    import src.services.scheduler
    src.services.scheduler._outreach_scheduler = outreach_scheduler
    
    # Start scheduler in production or when explicitly requested
    # Use resolved config_name rather than app.config['FLASK_ENV'] (FLASK_ENV is deprecated in Flask 3)
    if config_name == 'production' or app.config.get('START_SCHEDULER', False):
        try:
            outreach_scheduler.start()
            app.logger.info("Outreach scheduler started automatically")
        except Exception as e:
            app.logger.error(f"Failed to start scheduler: {str(e)}")
    
    # Create database tables (avoid fatal boot failures in production)
    try:
        with app.app_context():
            # In production, only run if explicitly enabled
            if config_name != 'production' or os.environ.get('STARTUP_DB_CREATE_ALL', 'false').lower() == 'true':
                db.create_all()
                app.logger.info("Database tables created/verified")
            else:
                app.logger.info("Skipping db.create_all() on startup in production")
    except Exception as e:
        app.logger.error(f"Failed to create/verify database tables on startup: {str(e)}")
    
    # Configure logging
    if not app.debug:
        if not os.path.exists('logs'):
            os.mkdir('logs')
        file_handler = logging.FileHandler('logs/linkedin_automation.log')
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        app.logger.setLevel(logging.INFO)
        app.logger.info('LinkedIn Automation API startup')
    
    # Serve static files - moved to end to avoid overriding API routes
    @app.route('/')
    def index():
        return send_from_directory('static', 'index.html')
    
    @app.route('/static/<path:filename>')
    def static_files(filename):
        return send_from_directory('static', filename)
    
    # Only serve other static files if they exist and are not API routes
    @app.route('/<path:filename>')
    def other_static_files(filename):
        # Don't serve files that start with 'api'
        if filename.startswith('api/'):
            return jsonify({'error': 'API endpoint not found'}), 404
        return send_from_directory('static', filename)
    
    return app

# Create the application instance
app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
