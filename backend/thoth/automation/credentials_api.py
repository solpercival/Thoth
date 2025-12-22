"""
Ezaango Credentials API Service
Provides admin credentials for Ezaango shift checking automation.

Endpoints:
- GET /health - Health check
- GET /api/credentials/<service_name> - Get credentials for service
- GET /api/services - List available services

Environment variables:
- ADMIN_USERNAME_HAHS_VIC3495
- ADMIN_PASSWORD_HAHS_VIC3495
"""

from flask import Flask, jsonify, request
import os
import logging

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Supported Ezaango services and their credentials from env vars
EZAANGO_SERVICES = {
    "hahs_vic3495": {
        "username": os.getenv("ADMIN_USERNAME_HAHS_VIC3495"),
        "password": os.getenv("ADMIN_PASSWORD_HAHS_VIC3495"),
    }
}


@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "healthy"}), 200


@app.route("/api/credentials/<service_name>", methods=["GET"])
def get_credentials(service_name: str):
    """
    Get admin credentials for an Ezaango service.
    
    Args:
        service_name: Ezaango service identifier (e.g., 'hahs_vic3495')
        
    Returns:
        JSON with username and password
    """
    logger.info(f"Credentials request for service: {service_name}")
    
    if service_name not in EZAANGO_SERVICES:
        logger.warning(f"Service not found: {service_name}")
        return jsonify({"error": f"Service '{service_name}' not found"}), 404
    
    creds = EZAANGO_SERVICES[service_name]
    
    if not creds.get("username") or not creds.get("password"):
        logger.error(f"Credentials not configured for {service_name}")
        return jsonify({"error": f"Credentials not configured for '{service_name}'"}), 500
    
    logger.info(f"Returning credentials for {service_name}")
    return jsonify(creds), 200


@app.route("/api/services", methods=["GET"])
def list_services():
    """List all available Ezaango services"""
    services = list(EZAANGO_SERVICES.keys())
    return jsonify({"services": services}), 200


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=os.getenv("DEBUG", "False") == "True")
