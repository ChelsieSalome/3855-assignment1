import connexion
from connexion import FlaskApp
from flask_cors import CORS
import json
import logging
import logging.config
import yaml
from kafka import KafkaConsumer
import threading

# Load configuration
with open('/config/analyzer_config.yml', 'r') as f:
    CONFIG = yaml.safe_load(f)

# Load logging configuration
with open('/config/analyzer_log_config.yml', 'r') as f:
    log_config = yaml.safe_load(f.read())
    logging.config.dictConfig(log_config)

logger = logging.getLogger('basicLogger')

# Create ONE persistent Kafka consumer at startup - FIX FOR LAB 10
def create_consumer():
    """Create a persistent Kafka consumer"""
    try:
        consumer = KafkaConsumer(
            CONFIG['kafka']['topic'],
            bootstrap_servers=f"{CONFIG['kafka']['hostname']}:{CONFIG['kafka']['port']}",
            group_id='analyzer_group',
            auto_offset_reset='earliest',
            enable_auto_commit=False,
            consumer_timeout_ms=1000,
            value_deserializer=lambda m: json.loads(m.decode('utf-8'))
        )
        # Don't poll or seek during initialization - let first request handle it
        logger.info("Kafka consumer created successfully")
        return consumer
    except Exception as e:
        logger.error(f"Failed to create Kafka consumer: {str(e)}")
        return None

# Create the persistent consumer at module load time
kafka_consumer = create_consumer()

# Create a lock to prevent concurrent access to the consumer
consumer_lock = threading.Lock()

# Flag to track if consumer has been initialized
consumer_initialized = False


def get_performance_event(index):
    """Gets a performance event at a specific index"""
    logger.info(f"Request for performance event at index {index}")
    
    global kafka_consumer, consumer_initialized
    
    if kafka_consumer is None:
        logger.error("Kafka consumer not available")
        return {"message": "Service unavailable"}, 503
    
    try:
        # Use lock to prevent concurrent access
        with consumer_lock:
            # Initialize on first request only
            if not consumer_initialized:
                logger.info("Initializing consumer on first request")
                kafka_consumer.poll(timeout_ms=1000)
                kafka_consumer.seek_to_beginning()
                consumer_initialized = True
            
            # Seek to beginning and iterate
            kafka_consumer.seek_to_beginning()
            performance_count = 0
            
            # Iterate through messages
            for msg in kafka_consumer:
                data = msg.value
                
                # Check if this is a performance event
                if data.get('type') == 'performance_metric':
                    if performance_count == index:
                        logger.info(f"Found performance event at index {index}")
                        return data['payload'], 200
                    performance_count += 1
        
        # If we get here, index not found
        logger.error(f"No performance event found at index {index}")
        return {"message": f"No performance event at index {index}"}, 404
        
    except Exception as e:
        logger.error(f"Error retrieving performance event: {str(e)}")
        return {"message": f"Error retrieving event: {str(e)}"}, 400


def get_error_event(index):
    """Gets an error event at a specific index"""
    logger.info(f"Request for error event at index {index}")
    
    global kafka_consumer, consumer_initialized
    
    if kafka_consumer is None:
        logger.error("Kafka consumer not available")
        return {"message": "Service unavailable"}, 503
    
    try:
        # Use lock to prevent concurrent access
        with consumer_lock:
            # Initialize on first request only
            if not consumer_initialized:
                logger.info("Initializing consumer on first request")
                kafka_consumer.poll(timeout_ms=1000)
                kafka_consumer.seek_to_beginning()
                consumer_initialized = True
            
            # Seek to beginning and iterate
            kafka_consumer.seek_to_beginning()
            error_count = 0
            
            # Iterate through messages
            for msg in kafka_consumer:
                data = msg.value
                
                # Check if this is an error event
                if data.get('type') == 'error_metric':
                    if error_count == index:
                        logger.info(f"Found error event at index {index}")
                        return data['payload'], 200
                    error_count += 1
        
        # If we get here, index not found
        logger.error(f"No error event found at index {index}")
        return {"message": f"No error event at index {index}"}, 404
        
    except Exception as e:
        logger.error(f"Error retrieving error event: {str(e)}")
        return {"message": f"Error retrieving event: {str(e)}"}, 400


def get_stats():
    """Gets statistics about events in the Kafka queue"""
    logger.info("Request for event statistics")
    
    global kafka_consumer, consumer_initialized
    
    if kafka_consumer is None:
        logger.error("Kafka consumer not available")
        return {"message": "Service unavailable"}, 503
    
    try:
        # Use lock to prevent concurrent access
        with consumer_lock:
            # Initialize on first request only
            if not consumer_initialized:
                logger.info("Initializing consumer on first request")
                kafka_consumer.poll(timeout_ms=1000)
                kafka_consumer.seek_to_beginning()
                consumer_initialized = True
            
            # Seek to beginning
            kafka_consumer.seek_to_beginning()
            
            # Initialize counts
            performance_count = 0
            error_count = 0
            
            # Iterate through all messages
            for msg in kafka_consumer:
                data = msg.value
                
                # Count by type
                if data.get('type') == 'performance_metric':
                    performance_count += 1
                elif data.get('type') == 'error_metric':
                    error_count += 1
        
        stats = {
            "num_performance_events": performance_count,
            "num_error_events": error_count
        }
        
        logger.info(f"Statistics: {stats}")
        return stats, 200
        
    except Exception as e:
        logger.error(f"Error retrieving statistics: {str(e)}")
        return {"message": f"Error retrieving statistics: {str(e)}"}, 400


def health():
    """Health check endpoint"""
    return {"status": "healthy"}, 200



app = FlaskApp(__name__, specification_dir='')

# Enable CORS
CORS(app.app)

# Add API with base path
app.add_api(
    'openapi.yaml',
    base_path='/analyzer',
    strict_validation=True,
    validate_responses=True
)

if __name__ == '__main__':
    app.run(
        host='0.0.0.0',
        port=CONFIG['app']['port']
    )