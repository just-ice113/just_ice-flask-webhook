import datetime

# Simple in-memory storage (replace with database later)
user_data = {}

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

@app.route("/telegram-webhook", methods=["POST"])
def telegram_webhook():
    data = request.get_json()
    chat_id = data["message"]["chat"]["id"]
    text = data["message"]["text"]

    if not is_subscribed(chat_id):
        reply = "⛔ Your free trial has ended. Please pay ₦2000 to continue using the bot."
    elif text.lower().startswith("write"):
        reply = generate_ai_content(text)
    else:
        reply = f"You said: {text}"

    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        json={"chat_id": chat_id, "text": reply}
    )
    return "ok", 200