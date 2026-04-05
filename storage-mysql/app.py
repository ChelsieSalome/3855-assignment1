import connexion
from connexion import NoContent
from datetime import datetime
import functools
import json
import yaml
import logging
import logging.config 
import threading
from models import PerformanceReading, ErrorReading
from create_tables import make_session
from sqlalchemy import select
from kafka import KafkaConsumer
from kafka.errors import KafkaError


with open('/config/storage_config.yml', 'r') as f:  #lab9
    app_config = yaml.safe_load(f.read())


with open('/config/storage_log_config.yml', 'r') as f:  #lab9
    log_config = yaml.safe_load(f.read())
    logging.config.dictConfig(log_config)  


logger = logging.getLogger('basicLogger')
 

# Suppress Kafka DEBUG logs
logging.getLogger('kafka').setLevel(logging.WARNING)
logging.getLogger('kafka.conn').setLevel(logging.WARNING)
logging.getLogger('kafka.client').setLevel(logging.WARNING)
logging.getLogger('kafka.consumer').setLevel(logging.WARNING)
logging.getLogger('kafka.protocol').setLevel(logging.WARNING)
logging.getLogger('kafka.coordinator').setLevel(logging.WARNING)



KAFKA_SERVER = f"{app_config['events']['hostname']}:{app_config['events']['port']}"
KAFKA_TOPIC = app_config['events']['topic']

logger.info("Storage service configuration loaded successfully")
logger.info(f"Kafka: {KAFKA_SERVER}, Topic: {KAFKA_TOPIC}")

def use_db_session(func):
    """Decorator to inject database session into functions"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        session = make_session()
        try:
            return func(session, *args, **kwargs)
        finally:
            session.close()
    return wrapper


@use_db_session
def report_performance_metrics(session, body):
    """Store performance metric to database"""
    reading = PerformanceReading(
        trace_id=body['trace_id'],
        server_id=body['server_id'],
        cpu=body['cpu'],
        memory=body['memory'],
        disk_io=body['disk_io'],
        reporting_timestamp=datetime.strptime(body['reporting_timestamp'], "%Y-%m-%dT%H:%M:%SZ")
    )
    
    session.add(reading)
    session.commit()

    logger.info(f" STORED: Performance reading (trace_id: {body['trace_id']}, server: {body['server_id']})")
    return NoContent, 201


@use_db_session
def report_error_metrics(session, body):
    """Store error metric to database"""
    reading = ErrorReading(
        trace_id=body['trace_id'],
        server_id=body['server_id'],
        error_code=body['error_code'],
        severity_level=body['severity_level'],
        avg_response_time=body['avg_response_time'],
        error_message=body['error_message'],
        reporting_timestamp=datetime.strptime(body['reporting_timestamp'], "%Y-%m-%dT%H:%M:%SZ")
    )
    
    session.add(reading)
    session.commit()

    logger.info(f" STORED: Error reading (trace_id: {body['trace_id']}, server: {body['server_id']}, code: {body['error_code']})")
    return NoContent, 201


@use_db_session
def get_performance_readings(session, start_timestamp, end_timestamp):
    """Retrieve performance readings within time range"""
    logger.debug(f"GET /monitoring/performance request: {start_timestamp} to {end_timestamp}")
    
    start_timestamp = start_timestamp.strip()
    end_timestamp = end_timestamp.strip()
    
    start_datetime = datetime.strptime(start_timestamp, "%Y-%m-%dT%H:%M:%SZ")
    end_datetime = datetime.strptime(end_timestamp, "%Y-%m-%dT%H:%M:%SZ")
    
    
    statement = select(PerformanceReading).where(
        PerformanceReading.date_created >= start_datetime
    ).where(
        PerformanceReading.date_created < end_datetime
    )
    
    results = [reading.to_dict() for reading in session.execute(statement).scalars().all()]
    
    logger.info(f"GET request: Found {len(results)} performance readings between {start_timestamp} and {end_timestamp}")
    
    return results, 200


@use_db_session
def get_error_readings(session, start_timestamp, end_timestamp):
    """Retrieve error readings within time range"""
    logger.debug(f"GET /monitoring/errors request: {start_timestamp} to {end_timestamp}")
    
    start_timestamp = start_timestamp.strip()
    end_timestamp = end_timestamp.strip()
    
    start_datetime = datetime.strptime(start_timestamp, "%Y-%m-%dT%H:%M:%SZ")
    end_datetime = datetime.strptime(end_timestamp, "%Y-%m-%dT%H:%M:%SZ")
    
    statement = select(ErrorReading).where(
        ErrorReading.date_created >= start_datetime
    ).where(
        ErrorReading.date_created < end_datetime
    )
    
    results = [reading.to_dict() for reading in session.execute(statement).scalars().all()]
    
    logger.info(f"GET request: Found {len(results)} error readings between {start_timestamp} and {end_timestamp}")
    
    return results, 200


# KAFKA CONSUMER THREAD
def process_messages():
    """Process event messages from Kafka"""
    logger.info(f" Connecting to Kafka at {KAFKA_SERVER}")
    
    try:
        consumer = KafkaConsumer(
            KAFKA_TOPIC,
            bootstrap_servers=KAFKA_SERVER,
            group_id='storage_group',
            auto_offset_reset='earliest',
            enable_auto_commit=False,
            value_deserializer=lambda m: json.loads(m.decode('utf-8'))
        )
        
        logger.info(f" Subscribed to topic: {KAFKA_TOPIC}")
        logger.info(" Waiting for messages...")
        
        # This is blocking - it will wait for new messages
        for msg in consumer:
            try:
                msg_data = msg.value
                payload = msg_data["payload"]
                msg_type = msg_data["type"]
                trace_id = payload.get('trace_id', 'unknown')
                server_id = payload.get('server_id', 'unknown')
                
                logger.info(f" RECEIVED FROM KAFKA: {msg_type} (trace: {trace_id}, server: {server_id})")
                
                if msg_type == "performance_metric":
                    # Store the performance metric to the DB
                    report_performance_metrics(payload)
                    
                elif msg_type == "error_metric":
                    # Store the error metric to the DB
                    report_error_metrics(payload)
                    
                else:
                    logger.warning(f"Unknown message type: {msg_type}")
                
                # Commit the message as being read
                consumer.commit()
                
            except Exception as e:
                logger.error(f" Error processing message: {e}")
                # Don't commit on error - message will be reprocessed
                
    except Exception as e:
        logger.error(f" Fatal error in Kafka consumer: {e}")


def setup_kafka_thread():
    """Setup and start Kafka consumer thread"""
    t1 = threading.Thread(target=process_messages)
    t1.daemon = True
    t1.start()
    logger.info(" Kafka consumer thread started")


# CONNEXION APP SETUP
app = connexion.FlaskApp(__name__, specification_dir='')
app.add_api("storage_openapi.yaml",
            strict_validation=True,
            validate_responses=True)

flask_app = app.app


@flask_app.route('/')
def home():
    """Home page with links to API endpoints"""
    return '''
    <html>
        <head>
            <title>Storage Service</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 40px; }
                h1 { color: #2c3e50; }
                code { background: #f4f4f4; padding: 2px 6px; border-radius: 3px; }
            </style>
        </head>
        <body>
            <h1> Storage Service</h1>
            <h2>Available Endpoints:</h2>
            <ol>
                <li>
                    <strong>GET:</strong> 
                    <code>/monitoring/performance?start_timestamp=2026-02-18T00:00:00Z&end_timestamp=2026-02-18T23:59:59Z</code>
                </li>
                <li>
                    <strong>GET:</strong> 
                    <code>/monitoring/errors?start_timestamp=2026-02-18T00:00:00Z&end_timestamp=2026-02-18T23:59:59Z</code>
                </li>
            </ol>
            <p><em> Messages are consumed from Kafka topic: <strong>events</strong></em></p>
            <hr>
            <p><a href="/ui">View API Documentation (Swagger UI)</a></p>
        </body>
    </html>
    '''

# Assignment 1
def health():
    """Health check endpoint"""
    return {"status": "healthy"}, 200

if __name__ == "__main__":
    logger.info(" Starting Storage Service on port 8091")
    
    setup_kafka_thread()
    
    app.run(host="0.0.0.0", port=8091)
