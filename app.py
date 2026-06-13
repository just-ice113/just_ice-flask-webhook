import os
import requests
import datetime
from flask import Flask, request, jsonify

app = Flask(__name__)

# Environment variables (set in Render dashboard)
SECRET_HASH = os.environ.get("FLW_SECRET_HASH")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")

# --- Simple user storage (replace with database later) ---
user_data = {}

# --- AI Content Generation Function ---
def generate_ai_content(prompt):
    """
    Replace this with a real AI API call later.
    For now, it simulates blog writing.
    """
    return f"""📝 Blog Draft:

Title: {prompt}

Introduction:
This article explores {prompt.lower()} in detail...

Main Body:
- Point 1: Why {prompt.lower()} matters
- Point 2: How it affects people
- Point 3: Practical tips

Conclusion:
In summary, {prompt.lower()} is essential for growth and success.
"""

# --- Subscription Logic ---
def is_subscribed(chat_id):
    today = datetime.date.today()
    if chat_id not in user_data:
        # New user → start free trial
        user_data[chat_id] = {"trial_start": today, "subscribed_until": None}
        return True
    trial_start = user_data[chat_id]["trial_start"]
    subscribed_until = user_data[chat_id]["subscribed_until"]

    # Free trial for 14 days
    if (today - trial_start).days <= 14:
        return True
    # Check subscription
    if subscribed_until and today <= subscribed_until:
        return True
    return False

def extend_subscription(chat_id):
    today = datetime.date.today()
    if chat_id not in user_data:
        user_data[chat_id] = {"trial_start": today, "subscribed_until": today + datetime.timedelta(days=14)}
    else:
        user_data[chat_id]["subscribed_until"] = today + datetime.timedelta(days=14)

# --- Flutterwave Webhook ---
@app.route("/flutterwave-webhook", methods=["POST"])
def flutterwave_webhook():
    signature = request.headers.get("verif-hash")
    if signature != SECRET_HASH:
        return jsonify({"status": "error", "message": "Invalid signature"}), 401

    data = request.get_json()
    if data.get('status') == 'successful':
        email = data['data']['customer']['email']
        chat_id = data['data']['customer'].get('id')  # You can map email to chat_id in real DB
        extend_subscription(chat_id)
        print("Payment successful for:", email)

    return jsonify({"status": "success", "message": "Webhook received"}), 200

# --- Telegram Webhook ---
@app.route("/telegram-webhook", methods=["POST"])
def telegram_webhook():
    data = request.get_json()
    chat_id = data["message"]["chat"]["id"]
    text = data["message"]["text"]

    if not is_subscribed(chat_id):
        reply = "⛔ Your free trial has ended. Please pay ₦2000 to continue using the bot."
    elif text.lower().startswith("write"):
        reply = generate_ai_content(text)
    elif text.lower() == "hi":
        reply = "Hello Justice! 👋 I’m your AI writing bot."
    else:
        reply = f"You said: {text}"

    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        json={"chat_id": chat_id, "text": reply}
    )
    return "ok", 200

# --- Run locally (not used on Render) ---
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)