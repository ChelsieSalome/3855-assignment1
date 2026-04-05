import connexion
from flask_cors import CORS
import json
import logging
import logging.config
import yaml
from datetime import datetime, timezone
import requests
from apscheduler.schedulers.background import BackgroundScheduler
import os


with open('/config/healthcheck_config.yml', 'r') as f:
    CONFIG = yaml.safe_load(f)

with open('/config/healthcheck_log_config.yml', 'r') as f:
    log_config = yaml.safe_load(f)
    logging.config.dictConfig(log_config)

logger = logging.getLogger('basicLogger')

DATASTORE_LOCATION = CONFIG['datastore']['location']
HEALTH_CHECK_INTERVAL = CONFIG['health_check']['interval_seconds']
TIMEOUT = CONFIG['health_check']['timeout_seconds']
SERVICES = CONFIG['services']

logger.info("Health Check Service configuration loaded")


def check_service_health(service_name, service_config):
    """
    Check if a single service is healthy by calling its /health endpoint
    
    Args:
        service_name (str): Name of service (e.g., 'receiver')
        service_config (dict): Service config with 'url' key
    
    Returns:
        str: 'Up' if service returns 200, 'Down' otherwise
    """
    try:
        response = requests.get(
            service_config['url'],
            timeout=TIMEOUT
        )
        
        if response.status_code == 200:
            logger.info(f"✓ {service_name.upper()} service is UP")
            return "Up"
        else:
            logger.warning(
                f"✗ {service_name.upper()} service returned HTTP {response.status_code}"
            )
            return "Down"
    
    except requests.exceptions.Timeout:
        logger.warning(
            f"✗ {service_name.upper()} service TIMEOUT (>{TIMEOUT}s)"
        )
        return "Down"
    
    except requests.exceptions.ConnectionError:
        logger.warning(
            f"✗ {service_name.upper()} service CONNECTION ERROR"
        )
        return "Down"
    
    except Exception as e:
        logger.error(
            f"✗ {service_name.upper()} service ERROR: {str(e)}"
        )
        return "Down"


def update_health_status():
    """
    Poll all services and update the datastore with their current status.
    This function is called periodically by the APScheduler.
    """
    logger.info("=" * 50)
    logger.info("STARTING HEALTH CHECK CYCLE")
    logger.info("=" * 50)
    
    try:
        with open(DATASTORE_LOCATION, 'r') as f:
            health_status = json.load(f)
            logger.debug(f"Loaded existing datastore from {DATASTORE_LOCATION}")
    
    except FileNotFoundError:
        logger.warning(f"Datastore not found, creating new file at {DATASTORE_LOCATION}")
        health_status = {
            service: {
                "status": "Unknown",
                "last_check": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            }
            for service in SERVICES.keys()
        }
    
    except Exception as e:
        logger.error(f"Error loading datastore: {e}, using defaults")
        health_status = {
            service: {
                "status": "Unknown",
                "last_check": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            }
            for service in SERVICES.keys()
        }
    
    current_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    for service_name, service_config in SERVICES.items():
        status = check_service_health(service_name, service_config)
        
        health_status[service_name] = {
            "status": status,
            "last_check": current_time
        }
        
        logger.info(f"RECORDED: {service_name.upper()} = {status} at {current_time}")
    
    try:
        os.makedirs(os.path.dirname(DATASTORE_LOCATION), exist_ok=True)
        
        with open(DATASTORE_LOCATION, 'w') as f:
            json.dump(health_status, f, indent=2)
        
        logger.debug(f"Datastore updated successfully")
    
    except Exception as e:
        logger.error(f"Failed to write datastore: {e}")
    
    logger.info("=" * 50)
    logger.info("HEALTH CHECK CYCLE COMPLETE")
    logger.info("=" * 50)


def get_health_status():
    """
    API Endpoint: GET /healthcheck/health-status
    Returns current health status of all services
    """
    logger.info("API REQUEST: GET /health-status")
    
    try:
        with open(DATASTORE_LOCATION, 'r') as f:
            health_status = json.load(f)
        
        response = {}
        latest_timestamp = None
        
        for service_name, service_data in health_status.items():
            response[service_name] = service_data['status']
            
            if latest_timestamp is None or service_data['last_check'] > latest_timestamp:
                latest_timestamp = service_data['last_check']
        
        response['last_update'] = latest_timestamp if latest_timestamp else "Unknown"
        
        logger.info(f"API RESPONSE: {response}")
        
        return response, 200
    
    except FileNotFoundError:
        logger.error("Datastore file not found")
        return {"message": "Health status not available yet"}, 503
    
    except Exception as e:
        logger.error(f"Error retrieving health status: {e}")
        return {"message": "Error retrieving health status"}, 500




def init_scheduler():
    """Initialize and start the background scheduler"""
    logger.info(f"Initializing scheduler with {HEALTH_CHECK_INTERVAL}s interval")
    
    try:
        scheduler = BackgroundScheduler(daemon=True)
        scheduler.add_job(
            update_health_status,
            'interval',
            seconds=HEALTH_CHECK_INTERVAL,
            id='health_check_job',
            name='Periodic health check'
        )
        scheduler.start()
        logger.info("✓ Scheduler started successfully")
    
    except Exception as e:
        logger.error(f"Failed to start scheduler: {e}")
        raise




app = connexion.FlaskApp(__name__, specification_dir='')
CORS(app.app)

app.add_api(
    'openapi.yaml',
    base_path='/healthcheck',
    strict_validation=True,
    validate_responses=True
)



if __name__ == '__main__':
    logger.info("=" * 60)
    logger.info("STARTING HEALTH CHECK SERVICE ON PORT 8120")
    logger.info("=" * 60)
    
    init_scheduler()
    
    app.run(
        host='0.0.0.0',
        port=CONFIG['app']['port'],
        debug=False
    )