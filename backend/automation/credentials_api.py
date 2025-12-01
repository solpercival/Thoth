"""
Example Credentials API Service
Provides credentials to the login automation script
Can be deployed as a separate Docker container
"""

from flask import Flask, jsonify, request
from typing import Dict, Optional
import os
import logging

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# In-memory credential store (replace with database in production)
CREDENTIALS_DB: Dict[str, Dict] = {
    "example_service": {
        "username": os.getenv("EXAMPLE_USERNAME", "test_user"),
        "password": os.getenv("EXAMPLE_PASSWORD", "test_password"),
        "email": "test@example.com",
        "extra_fields": {}
    },
    "github": {
        "username": os.getenv("GITHUB_USERNAME", "your_github_username"),
        "password": os.getenv("GITHUB_PASSWORD", "your_github_token"),
        "email": "your_email@example.com",
        "extra_fields": {}
    },
    "linkedin": {
        "username": os.getenv("LINKEDIN_USERNAME", "your_email@example.com"),
        "password": os.getenv("LINKEDIN_PASSWORD", "your_password"),
        "email": "your_email@example.com",
        "extra_fields": {}
    }
}


@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "healthy"}), 200


@app.route("/api/credentials/<service_name>", methods=["GET"])
def get_credentials(service_name: str):
    """
    Get credentials for a specific service
    
    Args:
        service_name: Name of the service
        
    Returns:
        JSON with username, password, email, and extra_fields
    """
    logger.info(f"Credentials request for service: {service_name}")
    
    if service_name not in CREDENTIALS_DB:
        logger.warning(f"Service not found: {service_name}")
        return jsonify({"error": f"Service '{service_name}' not found"}), 404
    
    credentials = CREDENTIALS_DB[service_name]
    
    # Don't log passwords
    logger.info(f"Returning credentials for {service_name}")
    
    return jsonify(credentials), 200


@app.route("/api/credentials/<service_name>/<user_id>", methods=["GET"])
def get_user_credentials(service_name: str, user_id: str):
    """
    Get credentials for a specific service and user
    
    Args:
        service_name: Name of the service
        user_id: User ID
        
    Returns:
        JSON with user-specific credentials
    """
    logger.info(f"Credentials request for service: {service_name}, user: {user_id}")
    
    # This is a placeholder - implement your own user lookup logic
    if service_name not in CREDENTIALS_DB:
        return jsonify({"error": f"Service '{service_name}' not found"}), 404
    
    # Return the default credentials (in production, lookup from database by user_id)
    return jsonify(CREDENTIALS_DB[service_name]), 200


@app.route("/api/credentials", methods=["POST"])
def add_credentials():
    """
    Add or update credentials for a service
    
    Request body:
    {
        "service_name": "service_name",
        "username": "username",
        "password": "password",
        "email": "email@example.com",
        "extra_fields": {}
    }
    """
    try:
        data = request.json
        service_name = data.get("service_name")
        
        if not service_name:
            return jsonify({"error": "service_name is required"}), 400
        
        CREDENTIALS_DB[service_name] = {
            "username": data.get("username"),
            "password": data.get("password"),
            "email": data.get("email"),
            "extra_fields": data.get("extra_fields", {})
        }
        
        logger.info(f"Credentials updated for service: {service_name}")
        return jsonify({"status": "success"}), 201
        
    except Exception as e:
        logger.error(f"Error adding credentials: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/credentials/<service_name>", methods=["DELETE"])
def delete_credentials(service_name: str):
    """Delete credentials for a service"""
    if service_name in CREDENTIALS_DB:
        del CREDENTIALS_DB[service_name]
        logger.info(f"Credentials deleted for service: {service_name}")
        return jsonify({"status": "success"}), 200
    
    return jsonify({"error": f"Service '{service_name}' not found"}), 404


@app.route("/api/services", methods=["GET"])
def list_services():
    """List all available services (without exposing passwords)"""
    services = list(CREDENTIALS_DB.keys())
    return jsonify({"services": services}), 200


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=os.getenv("DEBUG", "False") == "True")
