import os
import requests
import datetime
import html
from flask import Flask, request, jsonify

app = Flask(__name__)

# Environment variables (set in Render dashboard)
SECRET_HASH = os.environ.get("FLW_SECRET_HASH")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")

# --- Simple user storage (replace with database later) ---
user_data = {}

def generate_ai_content(prompt):
    """
    Generate a blog post using OpenRouter API.
    """
    headers = {
        "Authorization": f"Bearer {os.environ.get('OPENROUTER_API_KEY')}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "nex-agi/nex-n2-pro:free",
        "messages": [
            {"role": "system", "content": "You are a helpful AI writing assistant."},
            {"role": "user", "content": f"Write a detailed blog post about {prompt}. Include an introduction, body, and conclusion."}
        ]
    }

    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=20
        )
    except requests.exceptions.Timeout:
        return "⚠️ Error: OpenRouter API timed out. Please try again."

    if response.status_code == 200:
        data = response.json()
        content = data["choices"][0]["message"]["content"].strip()
        formatted = f"<b>Blog Post: {html.escape(prompt.title())}</b>\n\n{html.escape(content)}"
        return formatted
    else:
        return f"⚠️ Error {response.status_code}: {response.text}"

# --- Subscription Logic ---
def is_subscribed(chat_id):
    today = datetime.date.today()
    if chat_id not in user_data:
        user_data[chat_id] = {"trial_start": today, "subscribed_until": None}
        return True
    trial_start = user_data[chat_id]["trial_start"]
    subscribed_until = user_data[chat_id]["subscribed_until"]

    if (today - trial_start).days <= 14:
        return True
    if subscribed_until and today <= subscribed_until:
        return True
    return False

def extend_subscription(chat_id, days=14):
    today = datetime.date.today()
    if chat_id not in user_data:
        user_data[chat_id] = {"trial_start": today, "subscribed_until": today + datetime.timedelta(days=days)}
    else:
        current_end = user_data[chat_id].get("subscribed_until")
        if current_end and today <= current_end:
            user_data[chat_id]["subscribed_until"] = current_end + datetime.timedelta(days=days)
        else:
            user_data[chat_id]["subscribed_until"] = today + datetime.timedelta(days=days)

# --- Referral Logic ---
def add_referral(inviter_id, new_user_id):
    extend_subscription(inviter_id, days=7)
    user_data[new_user_id] = {"trial_start": datetime.date.today(), "subscribed_until": None}

# --- Flutterwave Webhook ---
@app.route("/flutterwave-webhook", methods=["POST"])
def flutterwave_webhook():
    signature = request.headers.get("verif-hash")
    if signature != SECRET_HASH:
        return jsonify({"status": "error", "message": "Invalid signature"}), 401

    data = request.get_json()
    if data.get('status') == 'successful':
        email = data['data']['customer']['email']
        chat_id = data['data']['customer'].get('id')
        extend_subscription(chat_id)
        print("Payment successful for:", email)

    return jsonify({"status": "success", "message": "Webhook received"}), 200

# --- Telegram Webhook ---
@app.route("/telegram-webhook", methods=["POST"])
def telegram_webhook():
    data = request.get_json()
    chat_id = data["message"]["chat"]["id"]
    text = data["message"]["text"]

    if text.lower().startswith("refer"):
        parts = text.split()
        if len(parts) == 2:
            inviter_id = int(parts[1])
            add_referral(inviter_id, chat_id)
            reply = "✅ Referral successful! You and your friend both got extra days."
        else:
            reply = "Usage: refer <friend_chat_id>"
    elif not is_subscribed(chat_id):
        reply = "⛔ Your free trial has ended. Please pay ₦2000 to continue using the bot."
    elif text.lower().startswith("write"):
        reply = generate_ai_content(text)
    elif text.lower() == "hi":
        reply = "Hello Justice! 👋 I’m your AI writing bot."
    else:
        reply = f"You said: {text}"

    # --- Send to Telegram with logging + fallback ---
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": chat_id, "text": reply, "parse_mode": "HTML"},
            timeout=10
        )
        print("Telegram response:", resp.status_code, resp.text)
        if resp.status_code != 200:
            # fallback: send plain text
            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                json={"chat_id": chat_id, "text": reply},
                timeout=10
            )
    except Exception as e:
        print("Telegram send error:", e)

    return "ok", 200

@app.route("/")
def home():
    return "✅ Flask app is running on Render!"

# --- OpenRouter Test Route ---
@app.route("/test-openrouter")
def test_openrouter():
    headers = {
        "Authorization": f"Bearer {os.environ.get('OPENROUTER_API_KEY')}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "nex-agi/nex-n2-pro:free",
        "messages": [
            {"role": "system", "content": "You are a helpful AI writing assistant."},
            {"role": "user", "content": "Write a short blog post about motivation."}
        ]
    }

    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=20
        )
    except requests.exceptions.Timeout:
        return "⚠️ Error: OpenRouter API timed out. Please try again."

    return response.text

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)