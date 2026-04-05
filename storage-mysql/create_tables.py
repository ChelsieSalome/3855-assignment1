from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base
import yaml
import logging
import logging.config
import time


# Load configuration
with open('/config/storage_config.yml', 'r') as f: #lab9
    app_config = yaml.safe_load(f.read())

db_conf = app_config['datastore']

with open("/config/storage_log_config.yml", "r") as f: #lab9
    LOG_CONFIG = yaml.safe_load(f.read())
    logging.config.dictConfig(LOG_CONFIG)

logger = logging.getLogger('basicLogger')

# MySQL connection string
DATABASE_URL = (
    f"mysql+pymysql://{db_conf['user']}:{db_conf['password']}"
    f"@{db_conf['hostname']}:{db_conf['port']}/{db_conf['db']}"
)

logger.info(f"Database URL configured for {db_conf['hostname']}:{db_conf['port']}/{db_conf['db']}")

# Create engine (does NOT connect yet)
engine = create_engine(DATABASE_URL, echo=False)


def make_session():
    """Create and return a new database session"""
    Session = sessionmaker(bind=engine)
    return Session()


def init_db(retries=10, delay=5):
    """
    Wait for MySQL to be ready, then create tables.
    Called explicitly at startup — NOT at import time.
    """
    for attempt in range(1, retries + 1):
        try:
            logger.info(f"MySQL connection attempt {attempt}/{retries}...")
            # This actually tests the connection
            Base.metadata.create_all(engine)
            logger.info("✅ MySQL connected and tables created successfully")
            return True
        except Exception as e:
            logger.warning(f"MySQL not ready (attempt {attempt}/{retries}): {e}")
            if attempt < retries:
                logger.info(f"Retrying in {delay} seconds...")
                time.sleep(delay)
            else:
                logger.error("❌ Could not connect to MySQL after all retries. Exiting.")
                raise
if __name__ == "__main__":
    init_db()
