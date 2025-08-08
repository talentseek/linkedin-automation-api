import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Base configuration class."""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or 'jwt-secret-key-change-in-production'
    JWT_ACCESS_TOKEN_EXPIRES = 86400  # 24 hours
    
    # Unipile API configuration
    UNIPILE_API_KEY = os.environ.get('UNIPILE_API_KEY')
    UNIPILE_WEBHOOK_SECRET = os.environ.get('UNIPILE_WEBHOOK_SECRET')
    
    # Rate limiting configuration
    MAX_CONNECTIONS_PER_DAY = int(os.environ.get('MAX_CONNECTIONS_PER_DAY', '25'))
    MAX_MESSAGES_PER_DAY = int(os.environ.get('MAX_MESSAGES_PER_DAY', '100'))
    MIN_DELAY_BETWEEN_ACTIONS = int(os.environ.get('MIN_DELAY_BETWEEN_ACTIONS', '300'))  # 5 minutes
    MAX_DELAY_BETWEEN_ACTIONS = int(os.environ.get('MAX_DELAY_BETWEEN_ACTIONS', '1800'))  # 30 minutes
    WORKING_HOURS_START = int(os.environ.get('WORKING_HOURS_START', '9'))
    WORKING_HOURS_END = int(os.environ.get('WORKING_HOURS_END', '17'))
    
    # CORS configuration
    CORS_ORIGINS = os.environ.get('CORS_ORIGINS', '*').split(',')
    
    # Logging configuration
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    # Debug endpoints toggle
    DEBUG_ENDPOINTS_ENABLED = os.environ.get('DEBUG_ENDPOINTS_ENABLED', 'false').lower() == 'true'


class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///instance/linkedin_automation.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = True
    
    # Development-specific settings
    TESTING = False


class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    TESTING = False
    
    # Production database (PostgreSQL)
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Production security settings
    SECRET_KEY = os.environ.get('SECRET_KEY')
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY')
    
    # Production API keys
    UNIPILE_API_KEY = os.environ.get('UNIPILE_API_KEY')
    UNIPILE_WEBHOOK_SECRET = os.environ.get('UNIPILE_WEBHOOK_SECRET')
    
    # Production CORS (more restrictive)
    CORS_ORIGINS = os.environ.get('CORS_ORIGINS', '').split(',')
    
    @classmethod
    def validate_config(cls):
        """Validate production configuration."""
        if not cls.SQLALCHEMY_DATABASE_URI:
            raise ValueError("DATABASE_URL environment variable is required for production")
        
        if not cls.SECRET_KEY:
            raise ValueError("SECRET_KEY environment variable is required for production")
        
        if not cls.JWT_SECRET_KEY:
            raise ValueError("JWT_SECRET_KEY environment variable is required for production")
        
        if not cls.UNIPILE_API_KEY:
            raise ValueError("UNIPILE_API_KEY environment variable is required for production")
        
        if not cls.UNIPILE_WEBHOOK_SECRET:
            raise ValueError("UNIPILE_WEBHOOK_SECRET environment variable is required for production")
        
        if not cls.CORS_ORIGINS or cls.CORS_ORIGINS == ['']:
            raise ValueError("CORS_ORIGINS environment variable is required for production")


class TestingConfig(Config):
    """Testing configuration."""
    TESTING = True
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = False


# Configuration mapping
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}

