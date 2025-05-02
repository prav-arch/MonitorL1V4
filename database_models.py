"""
ClickHouse database models for L1 Monitoring application.
This module provides models for storing log data in ClickHouse for analytics.
"""
from sqlalchemy import Column, String, create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os
import json
import logging

# Setup logging
logger = logging.getLogger(__name__)

try:
    # Import ClickHouse-specific modules
    import clickhouse_connect
    import requests
    from clickhouse_sqlalchemy import make_session, get_declarative_base, types, engines
    
    # Create the ClickHouse SQLAlchemy base
    Base = get_declarative_base()
    
    # Define ClickHouse-specific models
    class DBLogEntry(Base):
        """Database model for log entries"""
        __tablename__ = 'log_entries'
        
        # ClickHouse engine definition
        __table_args__ = (
            engines.MergeTree(
                order_by='timestamp'
            ),
        )
        
        id = Column(types.Int32, primary_key=True)
        timestamp = Column(String(30), nullable=False)
        level = Column(String(10), nullable=False)
        message = Column(String, nullable=False)
        service = Column(String(50), nullable=True)
        additional_fields = Column(types.String, nullable=True)  # Using String instead of JSON for ClickHouse
        created_at = Column(types.DateTime, default=datetime.utcnow)
        
        def to_dict(self):
            """Convert to dictionary representation"""
            # Parse additional_fields from string to dict if it's a string
            additional_data = {}
            if self.additional_fields:
                if isinstance(self.additional_fields, str):
                    try:
                        additional_data = json.loads(self.additional_fields)
                    except json.JSONDecodeError:
                        additional_data = {"raw_data": self.additional_fields}
                else:
                    additional_data = self.additional_fields
                    
            return {
                "id": self.id,
                "timestamp": self.timestamp,
                "level": self.level,
                "message": self.message,
                "service": self.service or "unknown",
                **additional_data
            }
        
        @classmethod
        def from_log_entry(cls, log_entry):
            """Create from LogEntry dataclass"""
            # Convert additional_fields to JSON string for ClickHouse
            additional_fields_str = None
            if log_entry.additional_fields:
                if isinstance(log_entry.additional_fields, str):
                    additional_fields_str = log_entry.additional_fields
                else:
                    try:
                        additional_fields_str = json.dumps(log_entry.additional_fields)
                    except (TypeError, ValueError):
                        additional_fields_str = json.dumps({"data": str(log_entry.additional_fields)})
            
            return cls(
                timestamp=log_entry.timestamp,
                level=log_entry.level,
                message=log_entry.message,
                service=log_entry.service,
                additional_fields=additional_fields_str
            )
            
        @classmethod
        def to_log_entry(cls, db_log):
            """Convert database log entry to LogEntry dataclass"""
            # Import LogEntry class here to avoid circular imports
            from models import LogEntry
            
            # Parse additional_fields from string to dict if needed
            additional_fields = db_log.additional_fields
            if additional_fields and isinstance(additional_fields, str):
                try:
                    additional_fields = json.loads(additional_fields)
                except json.JSONDecodeError:
                    additional_fields = {"raw_data": additional_fields}
            
            return LogEntry(
                timestamp=db_log.timestamp,
                level=db_log.level,
                message=db_log.message,
                service=db_log.service,
                additional_fields=additional_fields,
                id=db_log.id
            )

    class DBAnalysisQuery(Base):
        """Database model for analysis queries"""
        __tablename__ = 'analysis_queries'
        
        # ClickHouse engine definition
        __table_args__ = (
            engines.MergeTree(
                order_by='id'
            ),
        )
        
        id = Column(types.Int32, primary_key=True)
        query_text = Column(String, nullable=False)
        suggestion = Column(String, nullable=False)
        confidence_score = Column(types.Int32, default=0)
        created_at = Column(types.DateTime, default=datetime.utcnow)

    # Association table for many-to-many relationship
    class AnalysisLogAssociation(Base):
        """Association table for analysis queries and relevant logs"""
        __tablename__ = 'analysis_log_associations'
        
        # ClickHouse engine definition
        __table_args__ = (
            engines.MergeTree(
                order_by=('analysis_id', 'log_id')
            ),
        )
        
        analysis_id = Column(types.Int32, primary_key=True)
        log_id = Column(types.Int32, primary_key=True)
        
    class DBTrainingData(Base):
        """Database model for LLM training data"""
        __tablename__ = 'training_data'
        
        # ClickHouse engine definition
        __table_args__ = (
            engines.MergeTree(
                order_by='id'
            ),
        )
        
        id = Column(types.Int32, primary_key=True)
        document_path = Column(String, nullable=False)
        document_type = Column(String(20), nullable=False)  # 'log', 'pdf', 'doc', etc.
        content_type = Column(String(50), nullable=False)  # 'telecom', 'general', '5g', 'openran', etc.
        extracted_text = Column(String, nullable=True)  # Extracted text from document if processed
        embedding_file = Column(String, nullable=True)  # Path to file containing embeddings
        is_processed = Column(types.UInt8, default=0)  # 0=not processed, 1=processed
        created_at = Column(types.DateTime, default=datetime.utcnow)
        
    class DBFineTuningJob(Base):
        """Database model for LLM fine-tuning jobs"""
        __tablename__ = 'fine_tuning_jobs'
        
        # ClickHouse engine definition
        __table_args__ = (
            engines.MergeTree(
                order_by='id'
            ),
        )
        
        id = Column(types.Int32, primary_key=True)
        job_name = Column(String(100), nullable=False)
        model_name = Column(String(100), nullable=False)  # Base model name
        fine_tuned_model_name = Column(String(100), nullable=True)  # Resulting model name
        status = Column(String(20), nullable=False)  # 'pending', 'running', 'completed', 'failed'
        training_files = Column(String, nullable=False)  # JSON array of training file IDs
        parameters = Column(String, nullable=True)  # JSON with fine-tuning parameters
        created_at = Column(types.DateTime, default=datetime.utcnow)
        updated_at = Column(types.DateTime, default=datetime.utcnow)
        error_message = Column(String, nullable=True)  # Error message if job failed

    # Setup database connection function
    def get_db_session():
        """Get a ClickHouse database session"""
        try:
            # Get database URL with fallback to local ClickHouse
            db_url = os.environ.get('DATABASE_URL', 'clickhouse://default:@localhost:8123/default')
            
            # Always use local ClickHouse
            if 'aws' in db_url or 'neon' in db_url:
                logger.info("Ignoring cloud database URL, using local ClickHouse instead")
                db_url = 'clickhouse://default:@localhost:8123/default'
                
            logger.info(f"Using database URL: {db_url}")
            
            # Test connection to ClickHouse
            if db_url.startswith('clickhouse://'):
                parts = db_url.replace('clickhouse://', '').split('@')
                if len(parts) == 2:
                    credentials, host_port_db = parts
                    user_pass = credentials.split(':')
                    user = user_pass[0]
                    password = user_pass[1] if len(user_pass) > 1 else ''
                    
                    host_db = host_port_db.split('/')
                    host_port = host_db[0].split(':')
                    host = host_port[0]
                    port = int(host_port[1]) if len(host_port) > 1 else 8123
                    db = host_db[1] if len(host_db) > 1 else 'default'
                    
                    # Try connecting to ClickHouse via HTTP API
                    test_url = f"http://{host}:{port}/?database={db}&user={user}&password={password}"
                    response = requests.get(test_url, timeout=2)
                    if response.status_code != 200:
                        logger.warning(f"ClickHouse connection test failed: {response.status_code}")
                        raise Exception(f"ClickHouse connection failed with status {response.status_code}")
            
            # Create engine with ClickHouse-specific configurations
            engine = create_engine(db_url)
            
            # Create tables
            Base.metadata.create_all(engine)
            
            # Create session
            session = make_session(engine)
            return session
        
        except Exception as e:
            # Provide more informative message about database fallback
            logger.warning(f"ClickHouse connection error: {str(e)}")
            logger.info("This is normal when running in development or without ClickHouse installed")
            
            # Try PostgreSQL as fallback first
            try:
                # Import PostgreSQL models for fallback
                from postgresql_models import get_db_session as get_pg_session
                logger.info("Falling back to PostgreSQL database - this is the expected behavior")
                
                # Check if PostgreSQL is available (DATABASE_URL should be set)
                if os.environ.get('DATABASE_URL'):
                    try:
                        session = get_pg_session()
                        logger.info("PostgreSQL connection successful!")
                        return session
                    except Exception as pg_conn_error:
                        logger.error(f"PostgreSQL connection failed: {str(pg_conn_error)}")
                else:
                    logger.warning("DATABASE_URL not set, skipping PostgreSQL fallback")
            except Exception as pg_error:
                logger.error(f"PostgreSQL fallback failed: {str(pg_error)}")
                
            # Import SQLite models as final fallback
            from sqlite_models import get_db_session as get_sqlite_session
            logger.info("Falling back to SQLite in-memory database")
            return get_sqlite_session()

    # Initialize database
    def init_db():
        """Initialize the database (ClickHouse)"""
        try:
            logger.info("Initializing ClickHouse database...")
            
            # Use local ClickHouse
            db_url = 'clickhouse://default:@localhost:8123/default'
            logger.info(f"Using local ClickHouse: {db_url}")
            
            # Parse the URL to extract components
            parts = db_url.replace('clickhouse://', '').split('@')
            if len(parts) == 2:
                credentials, host_port_db = parts
                user_pass = credentials.split(':')
                user = user_pass[0]
                password = user_pass[1] if len(user_pass) > 1 else ''
                
                host_db = host_port_db.split('/')
                host_port = host_db[0].split(':')
                host = host_port[0]
                port = int(host_port[1]) if len(host_port) > 1 else 8123
                db = host_db[1] if len(host_db) > 1 else 'default'
                
                # Test connection to ClickHouse HTTP server
                test_url = f"http://{host}:{port}/?database={db}&user={user}&password={password}"
                logger.info(f"Testing connection to: http://{host}:{port}/...")
                
                response = requests.get(test_url, timeout=3)
                if response.status_code == 200:
                    logger.info("ClickHouse connection successful!")
                    
                    # Use clickhouse_connect client for direct operations
                    client = clickhouse_connect.get_client(
                        host=host,
                        port=port,
                        username=user,
                        password=password
                    )
                    
                    # Create the database if it doesn't exist
                    logger.info(f"Creating database '{db}' if it doesn't exist...")
                    client.command(f'CREATE DATABASE IF NOT EXISTS {db}')
                    client.database = db
                    
                    # Set up the SQLAlchemy connection and create tables
                    logger.info("Creating database tables via SQLAlchemy...")
                    engine = create_engine(db_url)
                    Base.metadata.create_all(engine)
                    logger.info("ClickHouse database tables created successfully.")
                    return True
                else:
                    logger.error(f"ClickHouse connection test failed with status code: {response.status_code}")
            
            # Try PostgreSQL as fallback first
            try:
                # Import PostgreSQL models for fallback
                from postgresql_models import init_db as init_pg_db
                logger.info("Trying PostgreSQL database as fallback...")
                
                # Check if PostgreSQL is available (DATABASE_URL should be set)
                if os.environ.get('DATABASE_URL'):
                    try:
                        success = init_pg_db()
                        if success:
                            logger.info("PostgreSQL database initialized successfully")
                            return True
                    except Exception as pg_init_error:
                        logger.error(f"PostgreSQL initialization failed: {str(pg_init_error)}")
                else:
                    logger.warning("DATABASE_URL not set, skipping PostgreSQL fallback")
            except Exception as pg_error:
                logger.error(f"PostgreSQL fallback module not available: {str(pg_error)}")
            
            # If PostgreSQL fails or isn't available, fallback to SQLite
            from sqlite_models import init_db as init_sqlite_db
            logger.info("Falling back to SQLite in-memory database for development")
            return init_sqlite_db()
            
        except Exception as e:
            logger.error(f"Error initializing database: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            
            # Try PostgreSQL as fallback first
            try:
                # Import PostgreSQL models for fallback
                from postgresql_models import init_db as init_pg_db
                logger.info("Trying PostgreSQL database as fallback after error...")
                
                # Check if PostgreSQL is available (DATABASE_URL should be set)
                if os.environ.get('DATABASE_URL'):
                    try:
                        success = init_pg_db()
                        if success:
                            logger.info("PostgreSQL database initialized successfully after error")
                            return True
                    except Exception as pg_init_error:
                        logger.error(f"PostgreSQL initialization failed: {str(pg_init_error)}")
                else:
                    logger.warning("DATABASE_URL not set, skipping PostgreSQL fallback")
            except Exception as pg_error:
                logger.error(f"PostgreSQL fallback module not available: {str(pg_error)}")
            
            # Final fallback to SQLite
            from sqlite_models import init_db as init_sqlite_db
            logger.info("Falling back to SQLite due to error")
            return init_sqlite_db()

except ImportError:
    logger.warning("ClickHouse libraries not available, trying PostgreSQL as fallback")
    
    # Try to import PostgreSQL models first
    try:
        # Check if PostgreSQL is available (DATABASE_URL should be set)
        if os.environ.get('DATABASE_URL'):
            try:
                from postgresql_models import (
                    DBLogEntry, DBAnalysisQuery, AnalysisLogAssociation,
                    DBTrainingData, DBFineTuningJob, get_db_session, init_db, Base
                )
                logger.info("Using PostgreSQL as fallback database")
            except ImportError:
                logger.warning("PostgreSQL models not available, falling back to SQLite")
                # Import SQLite models for final fallback
                from sqlite_models import (
                    DBLogEntry, DBAnalysisQuery, AnalysisLogAssociation,
                    DBTrainingData, DBFineTuningJob, get_db_session, init_db, Base
                )
        else:
            logger.warning("DATABASE_URL not set, falling back to SQLite")
            # Import SQLite models for final fallback
            from sqlite_models import (
                DBLogEntry, DBAnalysisQuery, AnalysisLogAssociation,
                DBTrainingData, DBFineTuningJob, get_db_session, init_db, Base
            )
    except Exception as e:
        logger.error(f"Error setting up fallback database: {str(e)}")
        # Import SQLite models for final fallback
        from sqlite_models import (
            DBLogEntry, DBAnalysisQuery, AnalysisLogAssociation,
            DBTrainingData, DBFineTuningJob, get_db_session, init_db, Base
        )