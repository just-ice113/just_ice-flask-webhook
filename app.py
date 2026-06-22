import os
import requests
import datetime
import html
import re
from flask import Flask, request, jsonify

app = Flask(__name__)

# --- Environment Variables ---
SECRET_HASH = os.environ.get("FLW_SECRET_HASH")
OPENROUTER_KEY = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OPEN")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN") or os.environ.get("TELE")

# --- Simple user storage ---
user_data = {}

def markdown_to_html(text):
    """
    Converts standard AI Markdown (###, **) into Telegram-friendly HTML strings.
    """
    # Convert markdown headers (### Header) to bold HTML lines
    text = re.sub(re.compile(r'^###\s+(.+)$', re.MULTILINE), r'<b>\1</b>', text)
    text = re.sub(re.compile(r'^##\s+(.+)$', re.MULTILINE), r'<b>\1</b>', text)
    text = re.sub(re.compile(r'^#\s+(.+)$', re.MULTILINE), r'<b>\1</b>', text)
    
    # Convert markdown bold (**text**) into HTML bold (<b>text</b>)
    text = re.sub(r'\*\*(.*?)\*\* ', r'<b>\1</b> ', text)
    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
    
    return text

def generate_ai_content(prompt):
    """
    Generate a blog post using OpenRouter API.
    """
    headers = {
        "Authorization": f"Bearer {OPENROUTER_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "openrouter/free", 
        "messages": [
            {"role": "system", "content": "You are a helpful AI writing assistant. Do not use markdown syntax in your response except basic bold text."},
            {"role": "user", "content": f"Write a detailed blog post about {prompt}. Use headings, bullet points, and emojis like ✨🔥💡 for clarity. Include an introduction, body, and conclusion."}
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
        
        # Clean up Markdown into beautiful Telegram HTML layouts
        formatted_content = markdown_to_html(content)
        formatted = f"<b>Blog Post: {html.escape(prompt.title())}</b>\n\n{formatted_content}"
        return formatted
    elif response.status_code == 429:
        return "⚠️ Daily free quota exceeded. Please try again later or add credits."
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
    if new_user_id not in user_data:
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

    if "message" not in data or "text" not in data["message"]:
        return "ok", 200

    chat_id = data["message"]["chat"]["id"]
    text = data["message"]["text"].strip()

    if text.lower().startswith("refer"):
        parts = text.split()
        if len(parts) == 2:
            try:
                inviter_id = int(parts[1])
                if inviter_id == chat_id:
                    reply = "⚠️ You cannot refer yourself!"
                else:
                    add_referral(inviter_id, chat_id)
                    reply = "✅ Referral successful! Your friend was rewarded, and your access is safe."
            except ValueError:
                reply = "⚠️ Invalid referral ID format."
        else:
            reply = "Usage: refer <friend_chat_id>"

    elif not is_subscribed(chat_id):
        reply = "⛔ Your free trial has ended. Please pay ₦2000 to continue using the bot."

    elif text.lower().startswith("write"):
        prompt = text[5:].strip()
        if not prompt:
            reply = "Please provide a topic! Example: `write healthy eating habits`"
        else:
            reply = generate_ai_content(prompt)

    elif text.lower() == "hi" or text.lower() == "/start":
        first_name = data["message"]["from"].get("first_name", "there")
        reply = (
            f"Hello {first_name}! 👋 I am Cee_bot, your instant AI blogging assistant.\n\n"
            "✍️ <b>How to use me:</b>\n"
            "Type <code>write &lt;your topic&gt;</code> to generate a complete, beautifully formatted blog post.\n\n"
            "🎁 <b>Want 7 Days Premium Free?</b>\n"
            "Invite your friends! Tell them to send this exact command to the bot when they join:\n"
            f"<code>refer {chat_id}</code>"
        )
        
    else:
        reply = f"You said: {text}\n\nType `write <your topic>` to create a blog post!"

    # --- Send to Telegram ---
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": chat_id, "text": reply, "parse_mode": "HTML"},
            timeout=10
        )
        if resp.status_code != 200:
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

@app.route("/status")
def status():
    return jsonify({"status": "ok", "message": "Bot is running"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
