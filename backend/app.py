from flask import Flask, request, jsonify
from automation.check_shifts_handler import check_shifts_and_notify
import asyncio

app = Flask(__name__)

@app.route("/api/check-shifts", methods=["POST"])
def check_shifts():
    service_name = request.json.get("service_name", "hahs_vic3495")
    result = asyncio.run(check_shifts_and_notify(service_name, notify_method="log"))
    return jsonify(result)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=False)