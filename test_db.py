#!/usr/bin/env python3

import os
import sys
sys.path.insert(0, os.path.dirname(__file__))

from src.config import config
from src.models import db
from flask import Flask

def test_db_connection():
    app = Flask(__name__)
    app.config.from_object(config['development'])
    
    print(f"Database URI: {app.config['SQLALCHEMY_DATABASE_URI']}")
    
    db.init_app(app)
    
    with app.app_context():
        try:
            # Test connection
            db.engine.connect()
            print("✅ Database connection successful!")
            
            # Test creating tables
            db.create_all()
            print("✅ Database tables created successfully!")
            
        except Exception as e:
            print(f"❌ Database error: {e}")
            return False
    
    return True

if __name__ == "__main__":
    test_db_connection() 