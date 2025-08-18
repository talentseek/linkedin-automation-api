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
    
    # Configure logging first so we can see route registration errors
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
    
    # Register blueprints with error handling
    try:
        from src.routes.auth import auth_bp
        app.register_blueprint(auth_bp, url_prefix='/api/v1/auth')
        app.logger.info("Registered auth blueprint")
    except ImportError as e:
        app.logger.error(f"Import error for auth blueprint: {str(e)}")
        import traceback
        app.logger.error(f"Auth blueprint import error traceback: {traceback.format_exc()}")
    except Exception as e:
        app.logger.error(f"Failed to register auth blueprint: {str(e)}")
        import traceback
        app.logger.error(f"Auth blueprint error traceback: {traceback.format_exc()}")
    
    try:
        from src.routes.client import client_bp
        app.register_blueprint(client_bp, url_prefix='/api/v1')
        app.logger.info("Registered client blueprint")
    except Exception as e:
        app.logger.error(f"Failed to register client blueprint: {str(e)}")
        import traceback
        app.logger.error(f"Client blueprint error traceback: {traceback.format_exc()}")
    
    try:
        from src.routes.campaign import campaign_bp
        app.register_blueprint(campaign_bp, url_prefix='/api/v1')
        app.logger.info("Registered campaign blueprint")
    except Exception as e:
        app.logger.error(f"Failed to register campaign blueprint: {str(e)}")
    
    try:
        from src.routes.lead import lead_bp
        app.register_blueprint(lead_bp, url_prefix='/api/v1')
        app.logger.info("Registered lead blueprint")
    except Exception as e:
        app.logger.error(f"Failed to register lead blueprint: {str(e)}")
    
    try:
        from src.routes.automation import automation_bp
        app.register_blueprint(automation_bp, url_prefix='/api/v1/automation')
        app.logger.info("Registered automation blueprint")
    except Exception as e:
        app.logger.error(f"Failed to register automation blueprint: {str(e)}")
    
    try:
        from src.routes.webhook import webhook_bp
        app.register_blueprint(webhook_bp, url_prefix='/api/v1/webhooks')
        app.logger.info("Registered webhook blueprint")
    except Exception as e:
        app.logger.error(f"Failed to register webhook blueprint: {str(e)}")
    
    try:
        from src.routes.sequence import sequence_bp
        app.register_blueprint(sequence_bp, url_prefix='/api/v1')
        app.logger.info("Registered sequence blueprint")
    except Exception as e:
        app.logger.error(f"Failed to register sequence blueprint: {str(e)}")
        import traceback
        app.logger.error(f"Sequence blueprint error traceback: {traceback.format_exc()}")
    
    try:
        from src.routes.analytics import analytics_bp
        app.register_blueprint(analytics_bp, url_prefix='/api/v1/analytics')
        app.logger.info("Registered analytics blueprint")
    except Exception as e:
        app.logger.error(f"Failed to register analytics blueprint: {str(e)}")
    
    try:
        from src.routes.linkedin_account import linkedin_account_bp
        app.register_blueprint(linkedin_account_bp, url_prefix='/api/v1')
        app.logger.info("Registered linkedin_account blueprint")
    except Exception as e:
        app.logger.error(f"Failed to register linkedin_account blueprint: {str(e)}")
    
    try:
        from src.routes.unipile_auth import unipile_auth_bp
        app.register_blueprint(unipile_auth_bp, url_prefix='/api/v1/unipile-auth')
        app.logger.info("Registered unipile_auth blueprint")
    except Exception as e:
        app.logger.error(f"Failed to register unipile_auth blueprint: {str(e)}")
    
    try:
        from src.routes.user import user_bp
        app.register_blueprint(user_bp, url_prefix='/api/v1')
        app.logger.info("Registered user blueprint")
    except Exception as e:
        app.logger.error(f"Failed to register user blueprint: {str(e)}")
    
    try:
        from src.routes.admin import admin_bp
        app.register_blueprint(admin_bp, url_prefix='/api/v1/admin')
        app.logger.info("Registered admin blueprint")
    except Exception as e:
        app.logger.error(f"Failed to register admin blueprint: {str(e)}")
    
    # Docs (OpenAPI/Swagger UI)
    try:
        from src.routes.docs import docs_bp
        app.register_blueprint(docs_bp, url_prefix='/api/v1')
        app.logger.info("Registered docs blueprint")
    except Exception as e:
        app.logger.error(f"Failed to register docs blueprint: {str(e)}")
    
    # Initialize scheduler with app context
    from src.services.scheduler import get_outreach_scheduler  # Now uses modular structure
    # Sequence engine is now modular and imported by scheduler
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
    

    
    # Register global error handlers
    try:
        from src.utils.error_handlers import register_error_handlers
        register_error_handlers(app)
        app.logger.info("Registered global error handlers")
    except Exception as e:
        app.logger.error(f"Failed to register error handlers: {str(e)}")
    
    # Simple health check endpoint
    @app.route('/')
    def index():
        return jsonify({'status': 'ok', 'message': 'LinkedIn Automation API is running'})
    
    return app

# Create the application instance
app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
