import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# Flutterwave secret hash
SECRET_HASH = os.environ.get("FLW_SECRET_HASH")

# Flutterwave webhook route
@app.route("/flutterwave-webhook", methods=["POST"])
def flutterwave_webhook():
    signature = request.headers.get("verif-hash")
    if signature != SECRET_HASH:
        return jsonify({"status": "error", "message": "Invalid signature"}), 401

    data = request.get_json()
    if data.get('status') == 'successful':
        email = data['data']['customer']['email']
        print("Payment successful for:", email)

    return jsonify({"status": "success", "message": "Webhook received"}), 200

# Telegram webhook route
@app.route("/telegram-webhook", methods=["POST"])
def telegram_webhook():
    data = request.get_json()
    chat_id = data["message"]["chat"]["id"]
    text = data["message"]["text"]

    # Reply back
    requests.post(
        f"https://api.telegram.org/bot{os.environ['TELEGRAM_TOKEN']}/sendMessage",
        json={"chat_id": chat_id, "text": f"You said: {text}"}
    )
    return "ok", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)