import os
import logging
import asyncio
from flask import Flask, request, jsonify, render_template_string
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, ContextTypes
from pymongo import MongoClient
from bson.objectid import ObjectId

# Logging setup
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Configuration ---
TOKEN = os.environ.get('TOKEN')
MONGO_URI = os.environ.get('MONGO_URI')
WEBHOOK_URL = os.environ.get('WEBHOOK_URL')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD')
PORT = int(os.environ.get('PORT', 8080))

# --- Database Initialization ---
try:
    client = MongoClient(MONGO_URI)
    db = client.get_default_database()
    users_collection = db['users']
    accounts_collection = db['netflix_accounts']
    profiles_collection = db['profiles']
    logger.info("Successfully connected to MongoDB.")
except Exception as e:
    logger.error(f"Error connecting to MongoDB: {e}")
    # Exit if DB connection fails
    exit()

# --- Telegram Bot Logic (Updated for v20+) ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the /start command."""
    user_id = update.effective_user.id
    
    user = users_collection.find_one({'telegram_id': user_id})
    
    if not user:
        referrer_id = None
        if context.args:
            try:
                referrer_id = int(context.args[0].split('_')[1])
            except (IndexError, ValueError):
                pass
        
        new_user = {
            'telegram_id': user_id,
            'first_name': update.effective_user.first_name,
            'username': update.effective_user.username,
            'referral_code': f'ref_{user_id}',
            'referred_by': referrer_id,
            'referral_count': 0,
            'has_access': False,
            'assigned_profile_id': None,
            'createdAt': update.message.date
        }
        users_collection.insert_one(new_user)
        user = new_user
        
        await update.message.reply_text("আপনাকে আমাদের বটে স্বাগতম! আপনার রেজিস্ট্রেশন সম্পন্ন হয়েছে।")
        
        if referrer_id:
            referrer = users_collection.find_one({'telegram_id': referrer_id})
            if referrer:
                new_count = referrer.get('referral_count', 0) + 1
                users_collection.update_one({'telegram_id': referrer_id}, {'$set': {'referral_count': new_count}})
                
                if new_count >= 5:
                    users_collection.update_one({'telegram_id': referrer_id}, {'$set': {'has_access': True}})
                    await context.bot.send_message(
                        chat_id=referrer_id,
                        text="🎉 অভিনন্দন! আপনি ৫ জনকে সফলভাবে রেফার করেছেন।\n\nএখন /getaccount কমান্ড ব্যবহার করে আপনার Netflix প্রোফাইল সংগ্রহ করতে পারেন।"
                    )
                else:
                    await context.bot.send_message(
                        chat_id=referrer_id,
                        text=f"✅ আপনার রেফারেল লিঙ্কে একজন নতুন ব্যবহারকারী জয়েন করেছে। আপনার বর্তমান রেফারেল সংখ্যা: {new_count}"
                    )
    
    bot_username = context.bot.username
    referral_link = f'https://t.me/{bot_username}?start={user["referral_code"]}'
    status_message = (
        f"👋 হ্যালো {user['first_name']}!\n\n"
        f"🔗 আপনার রেফারেল লিঙ্ক:\n`{referral_link}`\n\n"
        f"👥 আপনার রেফারেল সংখ্যা: **{user.get('referral_count', 0)}/5**\n\n"
        "এই লিঙ্কটি আপনার বন্ধুদের সাথে শেয়ার করুন। ৫ জন জয়েন করলেই আপনি একটি Netflix প্রোফাইল পাবেন।"
    )
    await update.message.reply_text(status_message, parse_mode='Markdown')

async def get_account(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the /getaccount command."""
    user_id = update.effective_user.id
    user = users_collection.find_one({'telegram_id': user_id})

    if not user or not user.get('has_access'):
        await update.message.reply_text("দুঃখিত, আপনার এখনো অ্যাক্সেস আনলক হয়নি। ৫টি রেফারেল পূর্ণ করুন।")
        return

    if user.get('assigned_profile_id'):
        await update.message.reply_text("আপনি ইতোমধ্যে একটি অ্যাকাউন্ট সংগ্রহ করেছেন।")
        return

    profile = profiles_collection.find_one_and_update(
        {'status': 'available'},
        {'$set': {'status': 'used', 'assigned_to_user_id': user_id, 'assignedAt': update.message.date}}
    )

    if not profile:
        await update.message.reply_text("দুঃখিত, এই মুহূর্তে কোনো প্রোফাইল খালি নেই। অনুগ্রহ করে পরে আবার চেষ্টা করুন।")
        return

    users_collection.update_one({'telegram_id': user_id}, {'$set': {'assigned_profile_id': profile['_id']}})
    parent_account = accounts_collection.find_one({'_id': profile['account_id']})

    account_details = (
        "🎉 অভিনন্দন! আপনার জন্য একটি প্রোফাইল বরাদ্দ করা হয়েছে।\n\n"
        "**আপনার অ্যাকাউন্টের বিবরণ:**\n"
        "-----------------------------------\n"
        f"📧 Netflix ইমেইল: `{parent_account['netflix_email']}`\n"
        f"🔑 Netflix পাসওয়ার্ড: `{parent_account['netflix_password']}`\n"
        f"👤 আপনার প্রোফাইলের নাম: `{profile['profile_name']}`\n"
        f"🔒 প্রোফাইলের পাসওয়ার্ড: `{profile['profile_password']}`\n"
        "-----------------------------------\n\n"
        "**সতর্কতা:** এই তথ্য কারো সাথে শেয়ার করবেন না।"
    )
    await update.message.reply_text(account_details, parse_mode='Markdown')

# --- Bot and Flask Application Initialization ---
application = Application.builder().token(TOKEN).build()
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("getaccount", get_account))

app = Flask(__name__, static_url_path='/admin', static_folder='admin')

@app.route(f'/{TOKEN}', methods=['POST'])
async def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    await application.process_update(update)
    return 'ok'

@app.route('/set_webhook', methods=['GET'])
async def set_webhook():
    if WEBHOOK_URL:
        await application.bot.set_webhook(url=f'{WEBHOOK_URL}/{TOKEN}')
        return "Webhook set successfully"
    return "WEBHOOK_URL not set."

@app.route('/admin', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        password = request.form.get('password')
        if password == ADMIN_PASSWORD:
            return jsonify({'success': True})
        return jsonify({'success': False, 'message': 'ভুল পাসওয়ার্ড'}), 401
    
    with open('admin/index.html', 'r', encoding='utf-8') as f:
        return render_template_string(f.read())

@app.route('/api/admin/data', methods=['GET'])
def get_admin_data():
    auth_header = request.headers.get('Authorization')
    if not auth_header or auth_header.split(' ')[1] != ADMIN_PASSWORD:
        return jsonify({'error': 'Unauthorized'}), 401
    
    users = list(users_collection.find({}, {'_id': 0}))
    accounts_with_profiles = list(accounts_collection.aggregate([
        {'$lookup': {'from': 'profiles', 'localField': '_id', 'foreignField': 'account_id', 'as': 'profiles'}}
    ]))
    for acc in accounts_with_profiles:
        acc['_id'] = str(acc['_id'])
        for prof in acc['profiles']:
            prof['_id'] = str(prof['_id'])
            prof['account_id'] = str(prof['account_id'])

    return jsonify({'users': users, 'accounts': accounts_with_profiles})

@app.route('/api/admin/accounts', methods=['POST'])
def add_account():
    auth_header = request.headers.get('Authorization')
    if not auth_header or auth_header.split(' ')[1] != ADMIN_PASSWORD:
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.json
    if not data.get('netflix_email') or not data.get('profiles'):
        return jsonify({'error': 'প্রয়োজনীয় তথ্য দেওয়া হয়নি'}), 400

    account_doc = {'netflix_email': data['netflix_email'], 'netflix_password': data.get('netflix_password'), 'gmail_account': data.get('gmail_account')}
    account_id = accounts_collection.insert_one(account_doc).inserted_id

    profiles_to_insert = [{'account_id': account_id, 'profile_name': p.get('profile_name'), 'profile_password': p.get('profile_password'), 'status': 'available', 'assigned_to_user_id': None, 'assignedAt': None} for p in data['profiles']]
    
    if profiles_to_insert:
        profiles_collection.insert_many(profiles_to_insert)

    return jsonify({'message': 'অ্যাকাউন্ট সফলভাবে যোগ করা হয়েছে'}), 201

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=PORT)

