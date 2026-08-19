import os
import random
import time
import telebot
from firebase_admin import db
from threading import Thread
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from app import app, BOT_TOKEN, get_settings

bot = telebot.TeleBot("8768026422:AAGz2ocG41w1F0jPvD9LoR9kqmydJQcaKhA")

FIRST_NAMES = ["Robert", "Daniel", "Michael", "James", "David", "Pooja", "Rahul", "Neha", "Amit", "Priya"]
LAST_NAMES = ["Odebralski", "Smith", "Johnson", "Williams", "Gupta", "Sharma", "Verma", "Singh"]
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]

def generate_task_details():
    f_name = random.choice(FIRST_NAMES)
    l_name = random.choice(LAST_NAMES)
    rand_num = random.randint(100, 999)
    email = f"{f_name.lower()}{l_name.lower()}{rand_num}@gmail.com"
    reg_id = f"G{random.randint(10000000, 99999999)}"
    month = random.choice(MONTHS)
    day = random.randint(1, 28)
    year = random.randint(1995, 2006)
    return f_name, l_name, email, reg_id, month, day, year

def is_user_banned(user_id):
    u_data = db.reference(f"users/{user_id}").get() or {}
    return u_data.get('banned', False)

def send_main_menu(chat_id, first_name):
    markup = ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add(
        KeyboardButton("📄 Get Task"),
        KeyboardButton("👥 Refer & Earn"),
        KeyboardButton("💰 Wallet Balance"),
        KeyboardButton("📁 Task History"),
        KeyboardButton("🏦 Save UPI"),
        KeyboardButton("🏧 Request Withdrawal")
    )
    bot.send_message(chat_id, f"Welcome {first_name}! Select an option below:", reply_markup=markup)

@bot.message_handler(commands=['start'])
def start_message(message):
    user_id = str(message.from_user.id)
    if is_user_banned(user_id):
        bot.send_message(message.chat.id, "❌ You have been banned by Admin.")
        return

    first_name = message.from_user.first_name or "User"
    username = message.from_user.username or ""

    # Referral Extraction
    args = message.text.split()
    referrer_id = args[1] if len(args) > 1 and args[1] != user_id else None

    u_ref = db.reference(f"users/{user_id}")
    u_data = u_ref.get() or {}

    if not u_data:
        u_ref.set({
            'first_name': first_name,
            'username': username,
            'balance': 0.0,
            'tasks_done': 0,
            'upi_id': '',
            'referred_by': referrer_id,
            'banned': False
        })
    else:
        u_ref.update({'first_name': first_name, 'username': username})

    send_main_menu(message.chat.id, first_name)

@bot.message_handler(func=lambda message: message.text == "📄 Get Task")
def assign_task(message):
    user_id = str(message.from_user.id)
    if is_user_banned(user_id): return

    settings = get_settings()
    f_name, l_name, email, reg_id, month, day, year = generate_task_details()

    task_ref = db.reference("tasks").push()
    task_ref.set({
        'id': task_ref.key,
        'user_id': user_id,
        'assigned_email': email,
        'screenshot_id': '',
        'status': 'Pending',
        'submission_time': time.strftime("%Y-%m-%d %H:%M:%S")
    })

    task_msg = (
        f"⚡ <b>New Task Assigned (ID: #{task_ref.key[-6:]})</b>\n\n"
        f"💵 <b>Reward: ₹{settings['task_reward']}</b>\n"
        "――――――――――――――――\n"
        f"First Name: <code>{f_name}</code>\n"
        f"Last Name: <code>{l_name}</code>\n"
        f"DOB: <code>{day} {month} {year}</code>\n"
        f"Email: <code>{email}</code>\n"
        f"Password: <code>WsxJaggu@#</code>\n"
        "――――――――――――――――\n"
        "📸 Create account and click 'Done' to send screenshot proof."
    )

    inline_btn = InlineKeyboardMarkup()
    inline_btn.add(InlineKeyboardButton("🟢 Submit Proof", callback_data=f"done_{task_ref.key}"))
    bot.send_message(message.chat.id, task_msg, parse_mode="HTML", reply_markup=inline_btn)

@bot.callback_query_handler(func=lambda call: call.data.startswith("done_"))
def handle_done(call):
    try:
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
    except Exception: pass
    bot.send_message(call.message.chat.id, "📸 Now send the screenshot image as proof.")

@bot.message_handler(content_types=['photo'])
def handle_screenshot(message):
    user_id = str(message.from_user.id)
    if is_user_banned(user_id): return

    photo_id = message.photo[-1].file_id
    tasks_data = db.reference("tasks").get() or {}

    user_tasks = [
        (tid, t) for tid, t in tasks_data.items() 
        if t and str(t.get('user_id')) == user_id and not t.get('screenshot_id')
    ]
    
    if user_tasks:
        target_task_id = user_tasks[-1][0]
        db.reference(f"tasks/{target_task_id}").update({
            'screenshot_id': photo_id,
            'submission_time': time.strftime("%Y-%m-%d %H:%M:%S")
        })
        bot.reply_to(message, "✅ <b>Proof Submitted Successfully!</b>\nStatus: <b>Pending Admin Approval</b>", parse_mode="HTML")

@bot.message_handler(func=lambda message: message.text == "👥 Refer & Earn")
def refer_info(message):
    user_id = str(message.from_user.id)
    settings = get_settings()
    bot_info = bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start={user_id}"
    
    msg = (
        "👥 <b>Refer & Earn Program</b>\n\n"
        f"Share your referral link with dosto ko invite karein:\n"
        f"💰 Earn <b>₹{settings['referral_reward']}</b> per valid referral task approval!\n\n"
        f"🔗 <b>Your Link:</b>\n<code>{ref_link}</code>"
    )
    bot.send_message(message.chat.id, msg, parse_mode="HTML")

@bot.message_handler(func=lambda message: message.text == "💰 Wallet Balance")
def balance(message):
    user_id = str(message.from_user.id)
    u_data = db.reference(f"users/{user_id}").get() or {}
    bal = u_data.get('balance', 0)
    bot.send_message(message.chat.id, f"💳 <b>Wallet Balance:</b> ₹{bal}", parse_mode="HTML")

@bot.message_handler(func=lambda message: message.text == "🏦 Save UPI")
def add_upi(message):
    msg = bot.send_message(message.chat.id, "📝 Send your UPI ID:")
    bot.register_next_step_handler(msg, process_upi)

def process_upi(message):
    upi_id = message.text.strip()
    user_id = str(message.from_user.id)
    db.reference(f"users/{user_id}").update({'upi_id': upi_id})
    bot.send_message(message.chat.id, f"✅ UPI Saved: <code>{upi_id}</code>", parse_mode="HTML")

@bot.message_handler(func=lambda message: message.text == "🏧 Request Withdrawal")
def withdraw(message):
    user_id = str(message.from_user.id)
    if is_user_banned(user_id): return

    settings = get_settings()
    min_w = settings['min_withdraw']

    u_data = db.reference(f"users/{user_id}").get() or {}
    bal = float(u_data.get('balance', 0))
    upi_id = u_data.get('upi_id', '')

    if bal < min_w:
        bot.send_message(message.chat.id, f"⚠️ Minimum withdrawal limit is <b>₹{min_w}</b>. Your current balance is ₹{bal}.", parse_mode="HTML")
        return
    if not upi_id:
        bot.send_message(message.chat.id, "⚠️ Save your UPI ID first using '🏦 Save UPI'.")
        return

    w_ref = db.reference("withdrawals").push()
    w_ref.set({
        'id': w_ref.key,
        'user_id': user_id,
        'upi_id': upi_id,
        'amount': bal,
        'status': 'Pending',
        'created_at': time.strftime("%Y-%m-%d %H:%M:%S")
    })

    db.reference(f"users/{user_id}").update({'balance': 0})
    bot.send_message(message.chat.id, f"✅ Withdrawal request for <b>₹{bal}</b> submitted!", parse_mode="HTML")

@bot.message_handler(func=lambda message: message.text == "📁 Task History")
def history(message):
    user_id = str(message.from_user.id)
    tasks_data = db.reference("tasks").get() or {}
    tasks = [t for t in tasks_data.values() if t and str(t.get('user_id')) == user_id]
    
    if not tasks:
        bot.send_message(message.chat.id, "No history found.")
        return

    msg = f"📁 <b>Task History ({len(tasks)} Submissions)</b>\n\n"
    for t in tasks[-10:]:
        msg += f"🆔 <code>#{t.get('id')[-6:]}</code> | {t.get('status')} | {t.get('assigned_email')}\n"
    bot.send_message(message.chat.id, msg, parse_mode="HTML")

def start_bot():
    while True:
        try:
            bot.polling(none_stop=True, timeout=30)
        except Exception as e:
            time.sleep(5)

bot_thread = Thread(target=start_bot)
bot_thread.daemon = True
bot_thread.start()

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
