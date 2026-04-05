import connexion
from connexion import NoContent
import uuid
import yaml
import logging
import logging.config
import json
import datetime
import time
from kafka import KafkaProducer
from kafka.errors import NoBrokersAvailable

with open('/config/receiver_config.yml', 'r') as f: #lab9
    app_config = yaml.safe_load(f.read())

with open("/config/receiver_log_config.yml", "r") as f: #lab9
    LOG_CONFIG = yaml.safe_load(f.read())
    logging.config.dictConfig(LOG_CONFIG)

logger = logging.getLogger('basicLogger')

logging.getLogger('kafka').setLevel(logging.WARNING)

logger.info("Configuration loaded - Kafka DEBUG logs suppressed")

KAFKA_SERVER = f"{app_config['events']['hostname']}:{app_config['events']['port']}"
KAFKA_TOPIC = app_config['events']['topic']

def get_kafka_producer():
    max_retries = 10
    retry_delay = 5  # seconds

    for attempt in range(max_retries):
        try:
            p = KafkaProducer(
                bootstrap_servers=KAFKA_SERVER,
                value_serializer=lambda v: json.dumps(v).encode('utf-8')
            )
            logger.info(f"Connected to Kafka at {KAFKA_SERVER}")
            return p
        except NoBrokersAvailable:
            logger.warning(f"Kafka not ready. Attempt {attempt + 1}/{max_retries}. Retrying in {retry_delay}s...")
            time.sleep(retry_delay)

    logger.error("Could not connect to Kafka after maximum retries.")
    raise Exception("Kafka connection failed after max retries.")

producer = get_kafka_producer()


def report_performance_metrics(body):
    """Receive performance metrics and send to Kafka"""
    try:
        server_id = body['server_id']
        reporting_timestamp = body['reporting_timestamp']
        metrics = body['metrics']

        for metric in metrics:
            trace_id = str(uuid.uuid4())

            logger.info(f"RECEIVED: Performance metric from server {server_id} (trace: {trace_id})")

            individual_event = {
                "trace_id": trace_id,
                "server_id": server_id,
                "cpu": metric['cpu'],
                "memory": metric['memory'],
                "disk_io": metric['disk_io'],
                "reporting_timestamp": reporting_timestamp
            }

            msg = {
                "type": "performance_metric",
                "datetime": datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
                "payload": individual_event
            }

            producer.send(KAFKA_TOPIC, value=msg)
            producer.flush()

            logger.info(f"SENT TO KAFKA: Performance metric (trace: {trace_id})")

        return NoContent, 201
    except Exception as e:
        logger.error(f"Error processing performance metrics: {e}")
        return {"error": str(e)}, 500


def report_error_metrics(body):
    """Receive error metrics and send to Kafka"""
    try:
        server_id = body['server_id']
        reporting_timestamp = body['reporting_timestamp']
        errors = body['errors']

        logger.info(f"RECEIVED: Error metrics from server {server_id}")

        if not errors:
            return NoContent, 201

        for error in errors:
            trace_id = str(uuid.uuid4())

            individual_event = {
                "trace_id": trace_id,
                "server_id": server_id,
                "error_code": error['error_code'],
                "severity_level": error['severity_level'],
                "avg_response_time": error['avg_response_time'],
                "error_message": error.get('error_message', ''),
                "reporting_timestamp": reporting_timestamp
            }

            msg = {
                "type": "error_metric",
                "datetime": datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
                "payload": individual_event
            }

            producer.send(KAFKA_TOPIC, value=msg)
            producer.flush()

            logger.info(f"SENT TO KAFKA: Error metric (trace: {trace_id}, code: {error['error_code']})")

        return NoContent, 201
    except Exception as e:
        logger.error(f"Error processing error metrics: {e}")
        return {"error": str(e)}, 500


app = connexion.FlaskApp(__name__, specification_dir='')
app.add_api("receiver_openapi.yaml",
            strict_validation=True,
            validate_responses=True)

flask_app = app.app

#Assignment 1
def health():
    """Health check endpoint"""
    return {"status": "healthy"}, 200

@flask_app.route('/')
def home():
    """Home page with links to API endpoints"""
    return '''
    <html>
    <head><title>Receiver Service</title></head>
    <body>
        <h1>Receiver Service</h1>
        <h2>Available Endpoints:</h2>
        <ul>
            <li>POST /monitoring/performance</li>
            <li>POST /monitoring/errors</li>
        </ul>
    </body>
    </html>
    '''


if __name__ == "__main__":
    logger.info("Starting Receiver Service on port 8080")
    app.run(host='0.0.0.0', port=8080)
