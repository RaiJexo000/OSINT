import random
import string
import datetime
import requests
import os
import json
import cloudinary
import cloudinary.uploader
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# ==================== CLOUDINARY CONFIG ====================
CLOUDINARY_NAME = "dizwk2qjs"
CLOUDINARY_API_KEY = "348872633595854"
CLOUDINARY_API_SECRET = "Tg4WTiSjVqGguWaeUymWGs-rvkA"

cloudinary.config(
    cloud_name=CLOUDINARY_NAME,
    api_key=CLOUDINARY_API_KEY,
    api_secret=CLOUDINARY_API_SECRET
)

# ==================== FIREBASE CONFIG ====================
FIREBASE_API_KEY = "AIzaSyCz4GqN0qh-kfdiXz1Fa8bF75lVNC3B570"
FIREBASE_DB_URL = "https://bot-hosting-f7cc3-default-rtdb.asia-southeast1.firebasedatabase.app"

# ==================== BOT CONFIG ====================
BOT_TOKEN = "8908999282:AAHsyGFuvwDljrVesDsk3cpyP9gpvIbnJEU"
ADMIN_ID = 8940619322
DEVELOPER_USERNAME = "@RaiJexo"
SOURCE_USERNAME = "@ApiMarket1_bot"
WELCOME_BONUS = 5
REFERRAL_BONUS = 5
REFERRED_BONUS = 5
GROUP_WELCOME_PHOTO = "https://i.ibb.co/7tw58803/file-00000000e7848211821e3506e356e373.png"

# ==================== VERIFICATION CHANNELS ====================
REQUIRED_CHANNELS = ["@NAXupdate", "@NAX_INF0"]

# ==================== ALLOWED GROUPS ====================
ALLOWED_GROUPS = {}

def is_allowed_group(group_id):
    group_id = str(group_id)
    if group_id not in ALLOWED_GROUPS:
        group = get_group(group_id)
        if group:
            ALLOWED_GROUPS[group_id] = group.get("group_name", "NAX INFO")
    return group_id in ALLOWED_GROUPS

def is_infinite_credits_group(group_id):
    return is_allowed_group(group_id)

# ==================== FOLDER SETUP ====================
def setup_folders():
    import platform
    system = platform.system()
    
    if system == "Android" or "TERMUX" in os.environ.get("TERMUX_VERSION", ""):
        base_temp = "/data/data/com.termux/files/home/tmp"
    else:
        base_temp = "/tmp/osint_bot"
    
    folders = [
        base_temp,
        f"{base_temp}/csv_exports",
        f"{base_temp}/images",
        f"{base_temp}/videos",
        f"{base_temp}/logs"
    ]
    
    for folder in folders:
        try:
            os.makedirs(folder, exist_ok=True)
        except Exception as e:
            print(f"⚠️ Error creating {folder}: {e}")
    
    return base_temp

TEMP_FOLDER = setup_folders()

# ==================== FIREBASE HELPERS ====================
def firebase_get(path):
    url = f"{FIREBASE_DB_URL}/{path}.json?auth={FIREBASE_API_KEY}"
    try:
        resp = requests.get(url, timeout=10)
        return resp.json() if resp.status_code == 200 else None
    except:
        return None

def firebase_put(path, data):
    url = f"{FIREBASE_DB_URL}/{path}.json?auth={FIREBASE_API_KEY}"
    try:
        resp = requests.put(url, json=data, timeout=10)
        return resp.status_code == 200
    except:
        return False

def firebase_patch(path, data):
    url = f"{FIREBASE_DB_URL}/{path}.json?auth={FIREBASE_API_KEY}"
    try:
        resp = requests.patch(url, json=data, timeout=10)
        return resp.status_code == 200
    except:
        return False

def firebase_post(path, data):
    url = f"{FIREBASE_DB_URL}/{path}.json?auth={FIREBASE_API_KEY}"
    try:
        resp = requests.post(url, json=data, timeout=10)
        return resp.status_code == 200
    except:
        return False

# ==================== DATABASE FUNCTIONS ====================
def get_user(user_id):
    return firebase_get(f"users/{user_id}")

def get_all_users():
    data = firebase_get("users")
    return data if data else {}

def get_all_group_users():
    group_data = firebase_get("group_verification") or {}
    all_group_users = {}
    
    for group_id, data in group_data.items():
        verified_users = data.get("verified_users", {})
        if verified_users:
            all_group_users[group_id] = list(verified_users.keys())
    
    print(f"📊 Group Users Found: {all_group_users}")
    return all_group_users

def get_all_group_users_flat():
    group_data = firebase_get("group_verification") or {}
    all_users = []
    
    for group_id, data in group_data.items():
        verified_users = data.get("verified_users", {})
        for uid in verified_users.keys():
            all_users.append({
                "user_id": uid,
                "group_id": group_id,
                "is_group_user": True
            })
    
    print(f"📊 Flat Group Users: {len(all_users)}")
    return all_users

def get_all_users_combined():
    private_users = get_all_users()
    group_users = get_all_group_users()
    all_users = private_users.copy()
    
    for gid, users in group_users.items():
        for uid in users:
            if str(uid) not in all_users:
                all_users[str(uid)] = {
                    "user_id": uid,
                    "first_name": f"Group_User_{uid}",
                    "is_group_user": True,
                    "group_id": gid
                }
    
    print(f"📊 Total Users Combined: {len(all_users)}")
    return all_users

def create_user(user_id, username, first_name, last_name, referrer_id=None):
    now = datetime.datetime.now().isoformat()
    data = {
        "user_id": user_id,
        "username": username,
        "first_name": first_name,
        "last_name": last_name,
        "balance": 0,
        "total_purchased": 0,
        "total_redeemed": 0,
        "total_used": 0,
        "joined_date": now,
        "last_active": now,
        "is_banned": False,
        "ban_type": "none",
        "ban_reason": "",
        "ban_until": "",
        "is_verified": False,
        "referred_by": referrer_id,
        "referral_count": 0,
        "referral_code": generate_referral_code(user_id)
    }
    if firebase_put(f"users/{user_id}", data):
        return data
    return None

def update_user(user_id, data):
    return firebase_patch(f"users/{user_id}", data)

def add_credits(user_id, amount, desc="Added"):
    user = get_user(user_id)
    if not user:
        return False
    new_bal = user.get("balance", 0) + amount
    if not update_user(user_id, {"balance": new_bal}):
        return False
    firebase_post(f"transactions/{user_id}", {
        "type": "add",
        "amount": amount,
        "description": desc,
        "timestamp": datetime.datetime.now().isoformat()
    })
    return True

def deduct_credit(user_id, desc="Used"):
    user = get_user(user_id)
    if not user or user.get("balance", 0) < 1:
        return False
    new_bal = user.get("balance", 0) - 1
    if not update_user(user_id, {"balance": new_bal, "total_used": user.get("total_used", 0) + 1}):
        return False
    firebase_post(f"transactions/{user_id}", {
        "type": "deduct",
        "amount": 1,
        "description": desc,
        "timestamp": datetime.datetime.now().isoformat()
    })
    return True

def get_redeem_code(code):
    return firebase_get(f"redeem_codes/{code}")

def save_redeem_code(code, credits, created_by, limit=1, expires=None, name=""):
    data = {
        "code": code,
        "credits": credits,
        "created_by": created_by,
        "created_at": datetime.datetime.now().isoformat(),
        "expires_at": expires,
        "usage_limit": limit,
        "usage_count": 0,
        "is_active": True,
        "code_name": name
    }
    return firebase_put(f"redeem_codes/{code}", data)

def use_redeem_code(code, user_id):
    code_data = get_redeem_code(code)
    if not code_data or not code_data.get("is_active"):
        return False
    if code_data.get("usage_count", 0) >= code_data.get("usage_limit", 1):
        return False
    if code_data.get("expires_at") and datetime.datetime.now().isoformat() > code_data["expires_at"]:
        return False
    used_by = code_data.get("used_by", {})
    if str(user_id) in used_by.values():
        return False
    new_count = code_data.get("usage_count", 0) + 1
    used_by[str(new_count)] = user_id
    update_data = {"usage_count": new_count, "used_by": used_by}
    return firebase_patch(f"redeem_codes/{code}", update_data)

def get_setting(key):
    return firebase_get(f"settings/{key}")

def set_setting(key, value):
    return firebase_put(f"settings/{key}", value)

def get_channels():
    channels = get_setting("channels")
    return channels if channels else []

def set_channels(channels):
    return set_setting("channels", channels)

def get_redeem_verify_status():
    status = get_setting("redeem_verify_status")
    return status if status else "OFF"

def set_redeem_verify_status(status):
    return set_setting("redeem_verify_status", status)

def get_redeem_channels():
    channels = get_setting("redeem_channels")
    return channels if channels else []

def set_redeem_channels(channels):
    return set_setting("redeem_channels", channels)

def is_admin(user_id):
    return user_id == ADMIN_ID

def generate_referral_code(user_id):
    chars = string.ascii_uppercase + string.digits
    random_part = ''.join(random.choices(chars, k=6))
    return f"OSINT_{random_part}"

def generate_code():
    return "OSINT_" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

def get_channel_link(channel):
    if channel.startswith("@"):
        return f"https://t.me/{channel[1:]}"
    elif channel.startswith("https://"):
        return channel
    else:
        return f"https://t.me/{channel}"

# ==================== GROUP MANAGEMENT FUNCTIONS ====================
def get_all_groups():
    return firebase_get("groups") or {}

def get_group(group_id):
    return firebase_get(f"groups/{group_id}")

def add_group_with_code(group_id, group_name, group_link):
    import random
    import string
    code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    group_code = f"GRP-{code}"
    data = {
        "group_name": group_name,
        "group_link": group_link,
        "group_code": group_code,
        "member_count": 0,
        "is_active": True,
        "credits": {
            "daily": 0,
            "weekly": 0,
            "monthly": 0
        },
        "welcome_message": f"Welcome to {group_name}! Use /start to use the bot.",
        "admin_permission": {},
        "verification_required": True,
        "joined_date": datetime.datetime.now().isoformat()
    }
    if firebase_put(f"groups/{group_id}", data):
        ALLOWED_GROUPS[group_id] = group_name
        return group_code
    return None

def get_group_by_code(code):
    groups = get_all_groups()
    for gid, g in groups.items():
        if g.get("group_code") == code:
            return gid
    return None

def toggle_group_active(group_id, status):
    return firebase_patch(f"groups/{group_id}", {"is_active": status})

def set_group_credits(group_id, daily, weekly, monthly):
    return firebase_patch(f"groups/{group_id}/credits", {
        "daily": daily,
        "weekly": weekly,
        "monthly": monthly
    })

def set_welcome_message(group_id, message):
    return firebase_patch(f"groups/{group_id}", {"welcome_message": message})

def is_group_admin(group_id, user_id):
    admins = firebase_get(f"groups/{group_id}/admin_permission") or {}
    return str(user_id) in admins

def add_group_admin(group_id, user_id, role="admin"):
    admins = firebase_get(f"groups/{group_id}/admin_permission") or {}
    admins[str(user_id)] = role
    return firebase_put(f"groups/{group_id}/admin_permission", admins)

def remove_group_admin(group_id, user_id):
    admins = firebase_get(f"groups/{group_id}/admin_permission") or {}
    if str(user_id) in admins:
        del admins[str(user_id)]
        return firebase_put(f"groups/{group_id}/admin_permission", admins)
    return False

def get_group_credits(group_id):
    group = get_group(group_id)
    if group:
        return group.get("credits", {})
    return {}

def get_welcome_message(group_id):
    group = get_group(group_id)
    if group:
        return group.get("welcome_message", "Welcome to the group!")
    return None

# ==================== GROUP USER VERIFICATION ====================
def is_group_user_verified(group_id, user_id):
    verified_users = firebase_get(f"group_verification/{group_id}/verified_users") or {}
    return str(user_id) in verified_users

def verify_group_user(group_id, user_id):
    verified_users = firebase_get(f"group_verification/{group_id}/verified_users") or {}
    verified_users[str(user_id)] = True
    return firebase_put(f"group_verification/{group_id}/verified_users", verified_users)

def unverify_group_user(group_id, user_id):
    verified_users = firebase_get(f"group_verification/{group_id}/verified_users") or {}
    if str(user_id) in verified_users:
        del verified_users[str(user_id)]
        return firebase_put(f"group_verification/{group_id}/verified_users", verified_users)
    return False

def get_group_verified_users(group_id):
    verified_users = firebase_get(f"group_verification/{group_id}/verified_users") or {}
    return verified_users

async def check_group_user_verification(group_id, user_id, context):
    if not is_allowed_group(group_id):
        return False
    if is_group_admin(group_id, user_id):
        verify_group_user(group_id, user_id)
        return True
    if is_group_user_verified(group_id, user_id):
        is_member = await check_user_membership(user_id, context)
        if is_member:
            return True
        else:
            unverify_group_user(group_id, user_id)
            return False
    return False

# ==================== CLOUDINARY UPLOAD ====================
async def upload_to_cloudinary(file_path, resource_type="image"):
    try:
        result = cloudinary.uploader.upload(file_path, resource_type=resource_type)
        return result.get("secure_url")
    except Exception as e:
        print(f"❌ Cloudinary upload error: {e}")
        return None

# ==================== KEYBOARDS ====================
USER_KEYBOARD = [
    [KeyboardButton("📞 Number"), KeyboardButton("🚗 Vehicle"), KeyboardButton("🏦 IFSC")],
    [KeyboardButton("🌐 IP"), KeyboardButton("🌤️ Weather"), KeyboardButton("📮 PIN")],
    [KeyboardButton("🏢 GST"), KeyboardButton("📱 TG Info"), KeyboardButton("📱 IMEI")],
    [KeyboardButton("💳 My Credits"), KeyboardButton("👤 Profile"), KeyboardButton("🆘 Support")]
]
USER_KEYBOARD_MARKUP = ReplyKeyboardMarkup(USER_KEYBOARD, resize_keyboard=True)

ADMIN_USER_KEYBOARD = USER_KEYBOARD + [[KeyboardButton("🛠️ Admin Panel")]]
ADMIN_USER_KEYBOARD_MARKUP = ReplyKeyboardMarkup(ADMIN_USER_KEYBOARD, resize_keyboard=True)

ADMIN_PANEL_KEYBOARD = [
    [KeyboardButton("👥 Users"), KeyboardButton("📢 Broadcast"), KeyboardButton("🎫 Code")],
    [KeyboardButton("📈 Referral"), KeyboardButton("⚙️ Verification"), KeyboardButton("📊 Logs")],
    [KeyboardButton("🎫 Redeem Verify"), KeyboardButton("📊 Groups"), KeyboardButton("🏢 Group Broadcast")],
    [KeyboardButton("📊 User Actions"), KeyboardButton("🔙 Back to User Panel")]
]
ADMIN_PANEL_KEYBOARD_MARKUP = ReplyKeyboardMarkup(ADMIN_PANEL_KEYBOARD, resize_keyboard=True)

LOOKUP_KEYBOARD = [
    [KeyboardButton("❌ Cancel")]
]
LOOKUP_KEYBOARD_MARKUP = ReplyKeyboardMarkup(LOOKUP_KEYBOARD, resize_keyboard=True)

MY_CREDITS_KEYBOARD = [
    [KeyboardButton("🔄 Refresh Balance")],
    [KeyboardButton("🎫 Redeem Code")],
    [KeyboardButton("🔙 Back to Main Menu")]
]
MY_CREDITS_KEYBOARD_MARKUP = ReplyKeyboardMarkup(MY_CREDITS_KEYBOARD, resize_keyboard=True)

VERIFY_KEYBOARD = [
    [InlineKeyboardButton("🔗 Join NAX Update", url="https://t.me/NAXupdate")],
    [InlineKeyboardButton("🔗 Join NAX INFO", url="https://t.me/NAX_INF0")],
    [InlineKeyboardButton("✅ I have Joined", callback_data="verify_membership")]
]
VERIFY_KEYBOARD_MARKUP = InlineKeyboardMarkup(VERIFY_KEYBOARD)

# ==================== GROUP KEYBOARD ====================
GROUP_KEYBOARD = [
    [KeyboardButton("📞 Number"), KeyboardButton("🚗 Vehicle"), KeyboardButton("🏦 IFSC")],
    [KeyboardButton("🌐 IP"), KeyboardButton("🌤️ Weather"), KeyboardButton("📮 PIN")],
    [KeyboardButton("🏢 GST"), KeyboardButton("📱 TG Info"), KeyboardButton("📱 IMEI")]
]
GROUP_KEYBOARD_MARKUP = ReplyKeyboardMarkup(GROUP_KEYBOARD, resize_keyboard=True)

# ==================== MEMBERSHIP CHECK ====================
async def check_user_membership(user_id, context):
    try:
        for channel in REQUIRED_CHANNELS:
            clean_ch = channel.lstrip('@')
            if clean_ch.startswith("https://"):
                continue
            try:
                chat_member = await context.bot.get_chat_member(chat_id=f"@{clean_ch}", user_id=user_id)
                if chat_member.status in ["left", "kicked"]:
                    return False
            except:
                return False
        return True
    except Exception as e:
        print(f"Membership check error: {e}")
        return False

async def check_redeem_membership(user_id, context):
    channels = get_redeem_channels()
    if not channels:
        return True
    try:
        for channel in channels:
            clean_ch = channel.lstrip('@')
            if clean_ch.startswith("https://"):
                continue
            try:
                chat_member = await context.bot.get_chat_member(chat_id=f"@{clean_ch}", user_id=user_id)
                if chat_member.status in ["left", "kicked"]:
                    return False
            except:
                return False
        return True
    except Exception as e:
        print(f"Redeem membership check error: {e}")
        return False

# ==================== START & DASHBOARD ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_type = update.effective_chat.type
    args = context.args
    
    print(f"Start command - User: {user_id}, Chat: {chat_type}")
    
    referrer_id = None
    if args and args[0].startswith("ref_"):
        try:
            referrer_id = int(args[0].split("_")[1])
            if referrer_id == user_id:
                referrer_id = None
        except:
            referrer_id = None
    
    user = get_user(user_id)
    
    if not user:
        user = create_user(
            user_id,
            update.effective_user.username or "",
            update.effective_user.first_name or "User",
            update.effective_user.last_name or "",
            referrer_id
        )
        
        if referrer_id:
            add_credits(user_id, REFERRED_BONUS, f"Welcome bonus from referral")
            add_credits(referrer_id, REFERRAL_BONUS, f"Referral bonus from {user_id}")
            referrer = get_user(referrer_id)
            if referrer:
                update_user(referrer_id, {"referral_count": referrer.get("referral_count", 0) + 1})
                try:
                    await context.bot.send_message(
                        chat_id=referrer_id,
                        text=f"🎉 New referral! +{REFERRAL_BONUS} Credits"
                    )
                except:
                    pass
    
    if user.get("is_banned"):
        await update.message.reply_text(f"❌ Banned!\nReason: {user.get('ban_reason', 'Not specified')}")
        return
    
    if chat_type in ["group", "supergroup"]:
        chat_id = str(update.effective_chat.id)
        print(f"Group start - Group ID: {chat_id}")
        
        group = get_group(chat_id)
        if not group:
            print(f"Group not found, auto-registering: {chat_id}")
            
            try:
                chat = await context.bot.get_chat(chat_id)
                group_name = chat.title or "Unknown Group"
                group_link = f"https://t.me/{chat.username}" if chat.username else f"https://t.me/joinchat/{chat_id}"
            except:
                group_name = "NAX INFO"
                group_link = "https://t.me/NAX_INF0"
            
            group_code = add_group_with_code(chat_id, group_name, group_link)
            
            if group_code:
                print(f"✅ Group registered: {chat_id} with code {group_code}")
                await update.message.reply_text(
                    f"✅ **Group Registered Successfully!**\n\n"
                    f"📌 Group: {group_name}\n"
                    f"🔑 Code: `{group_code}`\n\n"
                    f"📌 Now you can use the bot in this group!\n"
                    f"📌 Type /start again to continue.\n\n"
                    f"📌 Source: {SOURCE_USERNAME}"
                )
                return
            else:
                await update.message.reply_text(
                    f"❌ **Failed to register group!**\n\n"
                    f"Please contact admin.\n\n"
                    f"📌 Source: {SOURCE_USERNAME}"
                )
                return
        
        if not is_allowed_group(chat_id):
            ALLOWED_GROUPS[chat_id] = group.get("group_name", "NAX INFO")
            print(f"✅ Added {chat_id} to allowed groups")
        
        if is_group_user_verified(chat_id, user_id):
            print(f"User {user_id} already verified in group {chat_id}")
            await show_group_welcome(update, context)
            return
        
        is_verified = await check_group_user_verification(chat_id, user_id, context)
        
        if not is_verified:
            print(f"User {user_id} not verified in group {chat_id}")
            kb = [
                [InlineKeyboardButton("🔗 Join NAX Update", url="https://t.me/NAXupdate")],
                [InlineKeyboardButton("🔗 Join NAX INFO", url="https://t.me/NAX_INF0")],
                [InlineKeyboardButton("✅ I have Joined", callback_data=f"verify_group_{chat_id}")]
            ]
            
            await update.message.reply_text(
                f"╔═══════════════════════════════════════════╗\n"
                f"║  🔐 GROUP VERIFICATION REQUIRED            ║\n"
                f"╚═══════════════════════════════════════════╝\n\n"
                f"🚫 You must join our channels to use this bot!\n\n"
                f"📢 **Required Channels:**\n"
                f"   • NAX Update\n"
                f"   • NAX INFO\n\n"
                f"⚠️ After joining, click '✅ I have Joined'\n"
                f"⚠️ If you leave later, bot will stop working\n\n"
                f"📌 Source: {SOURCE_USERNAME}",
                reply_markup=InlineKeyboardMarkup(kb)
            )
            return
        
        print(f"User {user_id} verified in group {chat_id}")
        await show_group_welcome(update, context)
        return
    
    photo_url = GROUP_WELCOME_PHOTO
    
    is_member = await check_user_membership(user_id, context)
    
    if not is_member:
        await update.message.reply_text(
            f"╔═══════════════════════════════════════════╗\n"
            f"║  🔐 VERIFICATION REQUIRED                  ║\n"
            f"╚═══════════════════════════════════════════╝\n\n"
            f"🚫 You must join the following channels/groups:\n\n"
            f"📢 1. NAX Update\n"
            f"📢 2. NAX INFO\n\n"
            f"⚠️ After joining, click '✅ I have Joined'\n\n"
            f"📌 Source: {SOURCE_USERNAME}",
            reply_markup=VERIFY_KEYBOARD_MARKUP
        )
        return
    
    if not user.get("is_verified"):
        update_user(user_id, {"is_verified": True, "balance": WELCOME_BONUS})
        user = get_user(user_id)
    
    caption = (
        f"╔═══════════════════════════════════════════╗\n"
        f"║  🕵️ OSINT TOOLBOX  v1.0                  ║\n"
        f"╚═══════════════════════════════════════════╝\n\n"
        f"👋 Welcome, {user.get('first_name', 'User')}!\n\n"
        f"💳 Balance: {user.get('balance', 0)} Credits\n"
        f"📊 Used: {user.get('total_used', 0)}\n\n"
        f"👨‍💻 Developer: {DEVELOPER_USERNAME}"
    )
    
    if is_admin(user_id):
        await update.message.reply_photo(
            photo=photo_url,
            caption=caption,
            reply_markup=ADMIN_USER_KEYBOARD_MARKUP
        )
    else:
        await update.message.reply_photo(
            photo=photo_url,
            caption=caption,
            reply_markup=USER_KEYBOARD_MARKUP
        )

async def verify_membership_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    
    user_id = q.from_user.id
    
    await q.edit_message_text("⏳ Checking your membership...")
    
    is_member = await check_user_membership(user_id, context)
    
    if is_member:
        update_user(user_id, {"is_verified": True, "balance": WELCOME_BONUS})
        user = get_user(user_id)
        
        await q.edit_message_text(
            f"✅ **Verification Successful!**\n\n"
            f"🎁 +{WELCOME_BONUS} Credits added!\n"
            f"💰 Balance: {user.get('balance', 0)} Credits\n\n"
            f"📌 You can now use all features."
        )
        await user_dashboard(update, context)
    else:
        await q.edit_message_text(
            f"❌ **Verification Failed!**\n\n"
            f"You haven't joined both channels/groups yet.\n\n"
            f"📢 Please join both and try again.",
            reply_markup=VERIFY_KEYBOARD_MARKUP
        )

async def verify_group_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    
    user_id = q.from_user.id
    data = q.data
    
    group_id = data.replace("verify_group_", "")
    print(f"Verify group callback - User: {user_id}, Group: {group_id}")
    
    is_member = await check_user_membership(user_id, context)
    
    if is_member:
        verify_group_user(group_id, user_id)
        
        await q.edit_message_text(
            f"✅ **Verification Successful!**\n\n"
            f"🎉 You can now use the bot in this group!\n\n"
            f"💰 **CREDITS:** ♾️ INFINITE\n\n"
            f"⚠️ **Note:** If you leave channels, bot will stop working.\n\n"
            f"📌 Type /start to begin."
        )
        await show_group_welcome_from_callback(update, context, group_id)
    else:
        kb = [
            [InlineKeyboardButton("🔗 Join NAX Update", url="https://t.me/NAXupdate")],
            [InlineKeyboardButton("🔗 Join NAX INFO", url="https://t.me/NAX_INF0")],
            [InlineKeyboardButton("✅ I have Joined", callback_data=f"verify_group_{group_id}")]
        ]
        
        await q.edit_message_text(
            f"❌ **Verification Failed!**\n\n"
            f"You haven't joined both channels/groups yet.\n\n"
            f"📢 **Please join both:**\n"
            f"   • NAX Update\n"
            f"   • NAX INFO\n\n"
            f"Then click '✅ I have Joined' again.",
            reply_markup=InlineKeyboardMarkup(kb)
        )

async def show_group_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = str(update.effective_chat.id)
    group = get_group(chat_id)
    
    print(f"show_group_welcome - User: {user_id}, Group: {chat_id}")
    
    if not group:
        print(f"Group not found: {chat_id}")
        await update.message.reply_text(
            f"⚠️ **Group Not Registered!**\n\n"
            f"Group ID: `{chat_id}`\n\n"
            f"📌 Please type /start again to register.\n\n"
            f"📌 Source: {SOURCE_USERNAME}"
        )
        return
    
    welcome_msg = group.get("welcome_message", "Welcome to NAX INFO!")
    photo_url = GROUP_WELCOME_PHOTO
    
    caption = (
        f"╔═══════════════════════════════════════════╗\n"
        f"║  🕵️ OSINT TOOLBOX  v1.0                  ║\n"
        f"╚═══════════════════════════════════════════╝\n\n"
        f"👋 Welcome, {update.effective_user.first_name or 'User'}!\n\n"
        f"{welcome_msg}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💰 **CREDITS:** ♾️ INFINITE\n"
        f"✅ **You are VERIFIED**\n\n"
        f"📌 Source: {SOURCE_USERNAME}\n"
        f"👨‍💻 Developer:- {DEVELOPER_USERNAME}"
    )
    
    await update.message.reply_photo(
        photo=photo_url,
        caption=caption,
        reply_markup=GROUP_KEYBOARD_MARKUP
    )

async def show_group_welcome_from_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, group_id):
    user_id = update.effective_user.id
    group = get_group(group_id)
    
    if not group:
        return
    
    welcome_msg = group.get("welcome_message", "Welcome to NAX INFO!")
    photo_url = GROUP_WELCOME_PHOTO
    
    caption = (
        f"╔═══════════════════════════════════════════╗\n"
        f"║  🕵️ OSINT TOOLBOX  v1.0                  ║\n"
        f"╚═══════════════════════════════════════════╝\n\n"
        f"👋 Welcome, {update.effective_user.first_name or 'User'}!\n\n"
        f"{welcome_msg}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💰 **CREDITS:** ♾️ INFINITE\n"
        f"✅ **You are VERIFIED**\n\n"
        f"📌 Source: {SOURCE_USERNAME}\n"
        f"👨‍💻 Developer:- {DEVELOPER_USERNAME}"
    )
    
    await update.callback_query.message.reply_photo(
        photo=photo_url,
        caption=caption,
        reply_markup=GROUP_KEYBOARD_MARKUP
    )

async def user_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)
    chat_type = update.effective_chat.type
    
    if not user:
        await start(update, context)
        return
    
    if chat_type in ["group", "supergroup"]:
        await update.message.reply_text(
            f"╔═══════════════════════════════════════════╗\n"
            f"║  🤖 NAX INFO BOT                           ║\n"
            f"╚═══════════════════════════════════════════╝\n\n"
            f"👋 Welcome, {user.get('first_name', 'User')}!\n\n"
            f"💰 Credits: ♾️ INFINITE\n"
            f"📊 Used: {user.get('total_used', 0)}\n\n"
            f"📌 Source: {SOURCE_USERNAME}",
            reply_markup=GROUP_KEYBOARD_MARKUP
        )
        return
    
    photo_url = GROUP_WELCOME_PHOTO
    
    caption = (
        f"╔═══════════════════════════════════════════╗\n"
        f"║  🕵️ OSINT TOOLBOX  v1.0                  ║\n"
        f"╚═══════════════════════════════════════════╝\n\n"
        f"👋 Welcome, {user.get('first_name', 'User')}!\n\n"
        f"💳 Balance: {user.get('balance', 0)} Credits\n"
        f"📊 Used: {user.get('total_used', 0)}\n\n"
        f"👨‍💻 Developer: {DEVELOPER_USERNAME}"
    )
    
    if is_admin(user_id):
        await update.message.reply_photo(
            photo=photo_url,
            caption=caption,
            reply_markup=ADMIN_USER_KEYBOARD_MARKUP
        )
    else:
        await update.message.reply_photo(
            photo=photo_url,
            caption=caption,
            reply_markup=USER_KEYBOARD_MARKUP
        )

# ==================== LOOKUPS ====================
async def fetch_lookup(update: Update, context: ContextTypes.DEFAULT_TYPE, lookup_type, query):
    user_id = update.effective_user.id
    user = get_user(user_id)
    
    if not user:
        return
    
    is_group = update.effective_chat.type in ["group", "supergroup"]
    
    if user.get("is_banned"):
        await update.message.reply_text("❌ Banned!")
        return
    
    if is_group:
        chat_id = str(update.effective_chat.id)
        
        if not is_allowed_group(chat_id):
            await update.message.reply_text("❌ This bot only works in registered groups.")
            return
        
        is_verified = await check_group_user_verification(chat_id, user_id, context)
        
        if not is_verified:
            kb = [
                [InlineKeyboardButton("🔗 Join NAX Update", url="https://t.me/NAXupdate")],
                [InlineKeyboardButton("🔗 Join NAX INFO", url="https://t.me/NAX_INF0")],
                [InlineKeyboardButton("✅ I have Joined", callback_data=f"verify_group_{chat_id}")]
            ]
            
            await update.message.reply_text(
                f"🔐 Verification required! Please /start",
                reply_markup=InlineKeyboardMarkup(kb)
            )
            return
        
        balance_display = "♾️ INFINITE"
        credits_used_display = "0 (Free in Group)"
        balance = user.get("balance", 0)
        
    else:
        if user.get("balance", 0) < 1:
            await update.message.reply_text("❌ Insufficient Credits!")
            return
        
        if not deduct_credit(user_id, f"{lookup_type.upper()} Lookup: {query}"):
            await update.message.reply_text("❌ Deduct failed.")
            return
        balance = user.get("balance", 0) - 1
        balance_display = balance
        credits_used_display = "1"

    processing_msg = await update.message.reply_text(f"⏳ Processing {lookup_type.upper()} lookup...")

    try:
        if lookup_type == "number":
            API_URL = "https://ethicaltabbo.in/api/lookup"
            API_KEY = "Sahil"
            url = f"{API_URL}?key={API_KEY}&mobile={query}"
            
            try:
                response = requests.get(url, timeout=10)
                
                if response.status_code != 200:
                    await processing_msg.edit_text(f"❌ API Error (Status: {response.status_code})")
                    return
                
                try:
                    data = response.json()
                except ValueError:
                    await processing_msg.edit_text("❌ Invalid API response")
                    return
                
                print(f"📊 Number API Response: {data}")
                
                if not data or not isinstance(data, dict):
                    await processing_msg.edit_text("❌ Invalid response from API")
                    return
                
                if data.get("status") == False:
                    error_msg = data.get("error", "No data found")
                    remaining = data.get("api_info", {}).get("remaining", "N/A")
                    await processing_msg.edit_text(
                        f"❌ **Number Lookup Failed**\n\n"
                        f"📱 Number: `{query}`\n"
                        f"❌ {error_msg}\n"
                        f"💳 Credits Remaining: {remaining}\n\n"
                        f"💡 Tips:\n"
                        f"   • Check if number is correct (10 digits)\n"
                        f"   • Try without +91 or 0\n"
                        f"   • Example: 9876543210\n\n"
                        f"📌 Source: {SOURCE_USERNAME}"
                    )
                    return
                
                records = data.get("data", [])
                if not records:
                    await processing_msg.edit_text(
                        f"❌ No data found for this number.\n\n"
                        f"📱 Number: `{query}`\n\n"
                        f"💡 Try:\n"
                        f"   • Different number\n"
                        f"   • Check number format\n\n"
                        f"📌 Source: {SOURCE_USERNAME}"
                    )
                    return
                    
            except requests.exceptions.Timeout:
                await processing_msg.edit_text("❌ Request timed out. Please try again.")
                return
            except requests.exceptions.ConnectionError:
                await processing_msg.edit_text("❌ Network error. Please check your connection.")
                return
            except Exception as e:
                await processing_msg.edit_text(f"❌ Error: {str(e)}")
                return
            
        elif lookup_type == "vehicle":
            # ✅ Vehicle APIs - Primary API pehle
            apis = [
                {
                    "name": "Primary",
                    "url": f"https://nitin-api-free-user-1k-spacial.vercel.app/api?type=vehicle&search={query}",
                    "timeout": 15
                },
                {
                    "name": "Backup 1",
                    "url": f"https://vehicleinfobyterabaap.vercel.app/lookup?rc={query}",
                    "timeout": 20
                },
                {
                    "name": "Backup 2",
                    "url": f"https://rto-vehicle-info-api.vercel.app/api?reg_no={query}",
                    "timeout": 15
                }
            ]
            
            data = None
            used_api = "None"
            error_messages = []
            
            for api in apis:
                try:
                    print(f"🔄 Trying {api['name']} API...")
                    response = requests.get(api["url"], timeout=api["timeout"])
                    
                    if response.status_code == 200:
                        try:
                            data = response.json()
                            used_api = api['name']
                            print(f"✅ {api['name']} API Success!")
                            
                            # Check if data is valid
                            if data and not data.get("error"):
                                # Check if we have vehicle data
                                if "response" in data:
                                    result_data = data.get("response", {})
                                    if result_data and result_data.get("vehicle"):
                                        break
                                elif data.get("data") and data.get("data").get("vehicle_model"):
                                    break
                                elif data.get("model"):
                                    break
                                else:
                                    data = None
                                    print(f"⚠️ {api['name']} API returned empty data")
                                    error_messages.append(f"{api['name']}: No vehicle data")
                                    continue
                            else:
                                data = None
                                error_messages.append(f"{api['name']}: {data.get('error', 'Unknown error') if data else 'No data'}")
                                continue
                                
                        except ValueError as e:
                            print(f"❌ {api['name']} API Invalid JSON: {e}")
                            error_messages.append(f"{api['name']}: Invalid response format")
                            continue
                            
                    else:
                        error_messages.append(f"{api['name']}: HTTP {response.status_code}")
                        
                except requests.exceptions.Timeout:
                    print(f"❌ {api['name']} API Timeout")
                    error_messages.append(f"{api['name']}: Timeout")
                    continue
                except requests.exceptions.ConnectionError:
                    print(f"❌ {api['name']} API Connection Error")
                    error_messages.append(f"{api['name']}: Connection error")
                    continue
                except Exception as e:
                    print(f"❌ {api['name']} API Error: {str(e)}")
                    error_messages.append(f"{api['name']}: {str(e)}")
                    continue
            
            if not data or data.get("error"):
                error_text = "\n".join(error_messages[:3])
                await processing_msg.edit_text(
                    f"❌ No data found for this vehicle.\n\n"
                    f"🚗 Registration: `{query}`\n"
                    f"💡 Tips:\n"
                    f"   • Check registration number\n"
                    f"   • Format: RJ14CV0002\n"
                    f"   • Try without spaces\n\n"
                    f"🔍 Debug:\n"
                    f"{error_text}\n\n"
                    f"📌 Source: {SOURCE_USERNAME}"
                )
                return
            
            # Get result
            if "response" in data:
                result = data.get("response", {})
            elif "data" in data:
                result = data.get("data", {})
            else:
                result = data
            
            print(f"📊 Vehicle data from {used_api} API")
            
        elif lookup_type == "ifsc":
            url = f"https://ifsc.razorpay.com/{query}"
            try:
                response = requests.get(url, timeout=10)
                
                if response.status_code != 200:
                    await processing_msg.edit_text(f"❌ Invalid IFSC code (Status: {response.status_code})")
                    return
                
                try:
                    data = response.json()
                except requests.exceptions.JSONDecodeError:
                    await processing_msg.edit_text("❌ Invalid response from IFSC API")
                    return
                
                if not data or not isinstance(data, dict):
                    await processing_msg.edit_text("❌ No data found for this IFSC code")
                    return
                    
                if "IFSC" not in data:
                    await processing_msg.edit_text("❌ Invalid IFSC code format")
                    return
                    
            except requests.exceptions.RequestException as e:
                await processing_msg.edit_text(f"❌ Network error: {str(e)}")
                return
            
        elif lookup_type == "ip":
            url = f"https://ipwho.is/{query}"
            data = requests.get(url, timeout=10).json()
            
        elif lookup_type == "weather":
            WEATHER_API_KEY = "a9125012222bf075821d6ec3250201ea"
            url = f"https://api.openweathermap.org/data/2.5/weather?q={query}&appid={WEATHER_API_KEY}&units=metric"
            data = requests.get(url, timeout=15).json()
            
        elif lookup_type == "pin":
            url = f"https://api.postalpincode.in/pincode/{query}"
            data = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"}).json()
            
        elif lookup_type == "gst":
            api_key = "e38f40a3fc6cf5b672123adf6f3f55"
            url = f"https://api-pro-v2.vercel.app/key/{api_key}/get_data?gst_number={query}"
            data = requests.get(url, timeout=10).json()
            
        elif lookup_type == "tg_info":
            url = f"https://nitin-tg-to-number-api-free-hi-free-six.vercel.app/api?action=tgid&tg_user={query}"
            data = requests.get(url, timeout=10).json()
            
        elif lookup_type == "imei":
            api_key = "24182f4202ba3cfdf631a6507b911f"
            url = f"https://api-pro-v2.vercel.app/key/{api_key}/get_data?imei_number={query}"
            data = requests.get(url, timeout=10).json()
            
        else:
            await processing_msg.edit_text("❌ Invalid type.")
            return
            
    except requests.exceptions.Timeout:
        await processing_msg.edit_text("❌ Request timed out. Please try again.")
        return
    except requests.exceptions.ConnectionError:
        await processing_msg.edit_text("❌ Network error. Please check your connection.")
        return
    except Exception as e:
        await processing_msg.edit_text(f"❌ Error: {str(e)}")
        return

    # Check for errors
    if lookup_type == "number":
        if not data.get("status"):
            await processing_msg.edit_text("❌ No data found for this number.")
            return
        records = data.get("data", [])
        if not records:
            await processing_msg.edit_text("❌ No data found for this number.")
            return
            
    elif lookup_type == "vehicle":
        if "response" in data:
            result = data.get("response", {})
        else:
            result = data
            
    elif lookup_type == "ifsc":
        if not isinstance(data, dict) or "IFSC" not in data:
            await processing_msg.edit_text("❌ Invalid IFSC code or no data found.")
            return
            
    elif lookup_type == "ip":
        if not data.get("success"):
            await processing_msg.edit_text("❌ Invalid IP address.")
            return
            
    elif lookup_type == "weather":
        if data.get("cod") == 401:
            await processing_msg.edit_text("❌ Weather API key is invalid or expired.")
            return
        if data.get("cod") != 200:
            error_msg = data.get("message", "City not found")
            await processing_msg.edit_text(f"❌ {error_msg}")
            return
            
    elif lookup_type == "pin":
        if not data or data[0].get("Status") != "Success":
            await processing_msg.edit_text("❌ Invalid pincode or no data found.")
            return
            
    elif lookup_type == "gst":
        if isinstance(data, list) or data.get("result", {}).get("status") != "success":
            await processing_msg.edit_text("❌ Invalid GST number or no data found.")
            return
            
    elif lookup_type == "tg_info":
        if not data.get("status"):
            await processing_msg.edit_text("❌ User not found.")
            return
            
    elif lookup_type == "imei":
        if data.get("result", {}).get("status") != "success":
            await processing_msg.edit_text("❌ Invalid IMEI number.")
            return

    # Format output
    txt = f"╔═══════════════════════════════════════════╗\n"
    txt += f"║  🔍 {lookup_type.upper()} LOOKUP RESULT     ║\n"
    txt += f"╚═══════════════════════════════════════════╝\n\n"

    if lookup_type == "number":
        total_records = data.get("total_records", len(records))
        txt += f"📱 Number: {query}\n"
        txt += f"📊 Total Records: {total_records}\n\n"
        txt += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        for i, record in enumerate(records[:5], 1):
            txt += f"👤 Record #{i}\n"
            txt += f"├─ Name        : {record.get('name', 'N/A')}\n"
            txt += f"├─ Father      : {record.get('father_name', 'N/A')}\n"
            txt += f"├─ Mobile      : {record.get('mobile', 'N/A')}\n"
            
            alt = record.get('alt_number')
            txt += f"├─ Alt. Number : {alt if alt else 'N/A'}\n"
            
            txt += f"├─ 🆔 ID       : {record.get('id', 'N/A')}\n"
            
            email = record.get('email')
            txt += f"├─ Email       : {email if email else 'N/A'}\n"
            
            txt += f"├─ Circle      : {record.get('circle', 'N/A')}\n"
            
            address = record.get('address', 'N/A')
            if address and address != 'N/A':
                if len(address) > 30:
                    parts = address.split()
                    txt += f"├─ Address     : {parts[0]}\n"
                    for part in parts[1:]:
                        txt += f"│                {part}\n"
                else:
                    txt += f"└─ Address     : {address}\n"
            else:
                txt += f"└─ Address     : N/A\n"
            
            txt += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        if total_records > 5:
            txt += f"... and {total_records - 5} more records.\n\n"
    
    elif lookup_type == "vehicle":
        txt += f"🚘 Vehicle: {query}\n"
        txt += f"📊 Status: {'✅ Active' if result.get('status') != '0' else '❌ Inactive'}\n\n"
        txt += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        txt += f"📋 VEHICLE DETAILS:\n"
        txt += f"├─ RTO Code      : {result.get('rtoCode', 'N/A')}\n"
        txt += f"├─ Manufacturer  : {result.get('manufacturer', 'N/A')}\n"
        txt += f"├─ Model         : {result.get('vehicle', 'N/A')}\n"
        txt += f"├─ Variant       : {result.get('variant', 'N/A')}\n"
        txt += f"├─ Vehicle Class : {result.get('vehicleClass', 'N/A')}\n"
        txt += f"├─ Fuel Type     : {result.get('fuelType', 'N/A')}\n"
        txt += f"├─ CC            : {result.get('cubicCapacity', 'N/A')}\n"
        txt += f"├─ Seats         : {result.get('seatCapacity', 'N/A')}\n"
        txt += f"├─ Registration  : {result.get('regDate', 'N/A')}\n"
        txt += f"└─ Manufacturer  : {result.get('manufacturerMonthYear', 'N/A')}\n\n"
        txt += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        txt += f"🔧 TECHNICAL:\n"
        txt += f"├─ Chassis No    : {result.get('chassis', 'N/A')}\n"
        txt += f"├─ Engine No     : {result.get('engine', 'N/A')}\n"
        txt += f"└─ PUC No        : {result.get('puccNumber', 'N/A')}\n\n"
        txt += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        txt += f"📍 ADDRESS:\n"
        txt += f"├─ Present       : {result.get('presentAddress', 'N/A')}\n"
        txt += f"└─ Permanent     : {result.get('permAddress', 'N/A')}\n\n"
        txt += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        txt += f"📄 DOCUMENTS:\n"
        txt += f"├─ Insurance Upto: {result.get('insuranceUpto', 'N/A')}\n"
        txt += f"├─ Insurance Exp : {'✅ No' if not result.get('insuranceExpired') else '❌ Yes'}\n"
        txt += f"├─ PUC Upto      : {result.get('puccValidUpto', 'N/A')}\n"
        txt += f"└─ Status        : {result.get('status', 'N/A')}\n"
    
    elif lookup_type == "ifsc":
        txt += f"🏦 Bank: {data.get('BANK', 'N/A')}\n"
        txt += f"📍 Branch: {data.get('BRANCH', 'N/A')}\n"
        txt += f"📌 Address: {data.get('ADDRESS', 'N/A')}\n"
        txt += f"🏙️ City: {data.get('CITY', 'N/A')}\n"
        txt += f"📋 District: {data.get('DISTRICT', 'N/A')}\n"
        txt += f"🏛️ State: {data.get('STATE', 'N/A')}\n"
        txt += f"🔑 IFSC: {data.get('IFSC', 'N/A')}\n"
    
    elif lookup_type == "ip":
        txt += f"🌐 IP: {data.get('ip', 'N/A')}\n"
        txt += f"📍 Country: {data.get('country', 'N/A')} {data.get('flag', {}).get('emoji', '')}\n"
        txt += f"🏙️ Region: {data.get('region', 'N/A')}\n"
        txt += f"🗺️ City: {data.get('city', 'N/A')}\n"
        txt += f"📮 Postal: {data.get('postal', 'N/A')}\n"
        txt += f"📡 ISP: {data.get('connection', {}).get('isp', 'N/A')}\n"
    
    elif lookup_type == "weather":
        main = data.get("main", {})
        weather = data.get("weather", [{}])[0]
        wind = data.get("wind", {})
        sys = data.get("sys", {})
        clouds = data.get("clouds", {})
        
        if sys.get("sunrise"):
            sunrise_time = datetime.datetime.fromtimestamp(sys.get("sunrise", 0)).strftime("%I:%M %p")
        else:
            sunrise_time = "N/A"
        if sys.get("sunset"):
            sunset_time = datetime.datetime.fromtimestamp(sys.get("sunset", 0)).strftime("%I:%M %p")
        else:
            sunset_time = "N/A"
        
        txt += f"📍 {data.get('name', query)}, {sys.get('country', '')}\n"
        txt += f"🌡️ Temp: {main.get('temp', 'N/A')}°C\n"
        txt += f"🌤️ Condition: {weather.get('description', 'N/A').title()}\n"
        txt += f"💧 Humidity: {main.get('humidity', 'N/A')}%\n"
        txt += f"💨 Wind: {wind.get('speed', 'N/A')} m/s\n"
        txt += f"🌅 Sunrise: {sunrise_time}\n"
        txt += f"🌇 Sunset: {sunset_time}\n"
        txt += f"☁️ Cloud: {clouds.get('all', 'N/A')}%\n"
    
    elif lookup_type == "pin":
        post_offices = data[0].get("PostOffice", [])
        first = post_offices[0] if post_offices else {}
        txt += f"📍 Pincode: {query}\n"
        txt += f"📋 District: {first.get('District', 'N/A')}\n"
        txt += f"🏛️ State: {first.get('State', 'N/A')}\n"
        txt += f"📌 Circle: {first.get('Circle', 'N/A')}\n"
        txt += f"🏢 Post Offices: {len(post_offices)}\n"
        for i, po in enumerate(post_offices[:5], 1):
            star = " ⭐" if po.get("BranchType") == "Head Post Office" else ""
            txt += f"   {i}. {po.get('Name', 'N/A')}{star}\n"
        if len(post_offices) > 5:
            txt += f"   ... and {len(post_offices) - 5} more\n"
    
    elif lookup_type == "gst":
        result = data.get("result", {}).get("data", {})
        txt += f"🔑 GST: {result.get('Gstin', 'N/A')}\n"
        txt += f"🏢 Name: {result.get('LegalName', 'N/A')}\n"
        txt += f"📋 Status: {result.get('Status', 'N/A')}\n"
        txt += f"📅 Reg Date: {result.get('DtReg', 'N/A')[:10] if result.get('DtReg') else 'N/A'}\n"
        txt += f"📍 State: {result.get('StateCode', 'N/A')}\n"
        txt += f"📮 Pincode: {result.get('AddrPncd', 'N/A')}\n"
    
    elif lookup_type == "tg_info":
        result = data.get("result", {}).get("result", {})
        txt += f"📱 Username: {result.get('info', query)}\n"
        txt += f"📞 Mobile: {result.get('mobile', 'N/A')}\n"
        txt += f"🌍 Country: {result.get('country', 'N/A')}\n"
        txt += f"📌 Code: {result.get('country_code', 'N/A')}\n"
    
    elif lookup_type == "imei":
        result = data.get("result", {}).get("result", {})
        header = result.get("header", {})
        items = result.get("items", [])
        device_data = {}
        for item in items:
            if item.get("role") == "item":
                device_data[item.get("title")] = item.get("content")
        
        txt += f"📱 Brand: {header.get('brand', 'N/A')}\n"
        txt += f"📱 Model: {header.get('model', 'N/A')}\n"
        txt += f"📅 Release: {device_data.get('Relase Year', 'N/A')}\n"
        txt += f"💻 OS: {device_data.get('Operating systems', 'N/A')}\n"
        txt += f"🔋 Battery: {device_data.get('Capacity', 'N/A')}\n"
        txt += f"📸 Camera: {device_data.get('Main', 'N/A')} MP\n"

    txt += f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    txt += f"💳 Credits Used: {credits_used_display}\n"
    txt += f"💰 Remaining: {balance_display}\n"
    txt += f"📌 Source: {SOURCE_USERNAME}"

    await processing_msg.delete()
    await update.message.reply_text(txt)

# ==================== MY CREDITS ====================
async def my_credits_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)
    
    if not user:
        await start(update, context)
        return
    
    is_group = update.effective_chat.type in ["group", "supergroup"]
    
    if is_group:
        chat_id = str(update.effective_chat.id)
        
        if is_allowed_group(chat_id):
            txt = f"╔═══════════════════════════════════════════╗\n"
            txt += f"║  💳 MY CREDITS (GROUP MODE)               ║\n"
            txt += f"╚═══════════════════════════════════════════╝\n\n"
            txt += f"💰 Balance: ♾️ **INFINITE**\n"
            txt += f"📊 Status: ✅ Unlimited Lookups\n\n"
            txt += f"💡 **Group Benefits:**\n"
            txt += f"   • Unlimited lookups\n"
            txt += f"   • No credit deduction\n"
            txt += f"   • All features free\n\n"
            txt += f"📌 **Private Chat Balance:** {user.get('balance', 0)} Credits\n"
        else:
            txt = f"❌ This bot only works in registered groups."
        
        await update.message.reply_text(txt, reply_markup=MY_CREDITS_KEYBOARD_MARKUP)
        return
    
    balance = user.get('balance', 0)
    used = user.get('total_used', 0)
    referrals = user.get('referral_count', 0)
    referral_bonus = referrals * REFERRAL_BONUS
    total_earned = balance + used
    
    txt = f"╔═══════════════════════════════════════════╗\n"
    txt += f"║  💳 MY CREDITS                            ║\n"
    txt += f"╚═══════════════════════════════════════════╝\n\n"
    txt += f"👤 User: {user.get('first_name', 'User')}\n"
    txt += f"🆔 ID: {user_id}\n\n"
    txt += f"💰 BALANCE: {balance} CREDITS\n\n"
    txt += f"📊 USAGE:\n"
    txt += f"├─ Used: {used}\n"
    txt += f"├─ Remaining: {balance}\n"
    txt += f"└─ Total Earned: {total_earned}\n\n"
    txt += f"🎁 REFERRALS:\n"
    txt += f"├─ Total: {referrals}\n"
    txt += f"├─ Bonus Per Referral: {REFERRAL_BONUS} Credits\n"
    txt += f"└─ Total Bonus: {referral_bonus} Credits\n\n"
    txt += f"🔗 Referral Link:\n"
    txt += f"   https://t.me/OsintToolboxbot?start=ref_{user_id}\n\n"
    txt += f"📌 Share & Earn +{REFERRAL_BONUS} Credits per referral!"
    
    txt += f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    txt += f"📌 Source: {SOURCE_USERNAME}"
    
    await update.message.reply_text(txt, reply_markup=MY_CREDITS_KEYBOARD_MARKUP)

async def handle_redeem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    code = update.message.text.strip().upper()
    
    redeem_status = get_redeem_verify_status()
    redeem_channels = get_redeem_channels()
    
    if redeem_status == "ON" and redeem_channels:
        is_member = await check_redeem_membership(user_id, context)
        
        if not is_member:
            kb = []
            for ch in redeem_channels:
                link = get_channel_link(ch)
                kb.append([InlineKeyboardButton(f"🔗 Join {ch}", url=link)])
            kb.append([InlineKeyboardButton("✅ I have Joined", callback_data="verify_redeem_membership")])
            
            await update.message.reply_text(
                f"╔═══════════════════════════════════════════╗\n"
                f"║  🎫 REDEEM VERIFICATION REQUIRED          ║\n"
                f"╚═══════════════════════════════════════════╝\n\n"
                f"🚫 You must join these channels/groups to redeem codes!\n\n",
                reply_markup=InlineKeyboardMarkup(kb)
            )
            return
    
    code_data = get_redeem_code(code)
    
    if not code_data:
        await update.message.reply_text("❌ Invalid Code!")
        return
    
    if not code_data.get("is_active"):
        await update.message.reply_text("❌ Inactive Code!")
        return
    
    if code_data.get("expires_at") and datetime.datetime.now().isoformat() > code_data["expires_at"]:
        await update.message.reply_text("❌ Code Expired!")
        return
    
    if code_data.get("usage_count", 0) >= code_data.get("usage_limit", 1):
        await update.message.reply_text("❌ Already Used!")
        return
    
    if use_redeem_code(code, user_id):
        add_credits(user_id, code_data["credits"], f"Redeemed {code}")
        user = get_user(user_id)
        await update.message.reply_text(
            f"✅ **Code Redeemed Successfully!**\n\n"
            f"🎫 Code: {code}\n"
            f"💳 Credits Added: +{code_data['credits']}\n"
            f"💰 New Balance: {user.get('balance', 0)} Credits"
        )
    else:
        await update.message.reply_text("❌ Failed to redeem!")

async def verify_redeem_membership_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    
    user_id = q.from_user.id
    
    await q.edit_message_text("⏳ Checking membership...")
    
    is_member = await check_redeem_membership(user_id, context)
    
    if is_member:
        await q.edit_message_text(
            f"✅ **Verification Successful!**\n\n"
            f"📌 Please enter your redeem code now."
        )
    else:
        kb = []
        for ch in get_redeem_channels():
            link = get_channel_link(ch)
            kb.append([InlineKeyboardButton(f"🔗 Join {ch}", url=link)])
        kb.append([InlineKeyboardButton("✅ I have Joined", callback_data="verify_redeem_membership")])
        
        await q.edit_message_text(
            f"❌ **Verification Failed!**\n\n"
            f"You haven't joined all required channels.\n\n"
            f"Please join and try again.",
            reply_markup=InlineKeyboardMarkup(kb)
        )

# ==================== PROFILE & SUPPORT ====================
async def profile_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)
    
    if not user:
        await start(update, context)
        return
    
    try:
        photos = await context.bot.get_user_profile_photos(user_id, limit=1)
        if photos.total_count > 0:
            profile_photo = photos.photos[0][-1].file_id
        else:
            profile_photo = None
    except:
        profile_photo = None
    
    caption = (
        f"╔═══════════════════════════════════════════╗\n"
        f"║  👤 USER PROFILE                          ║\n"
        f"╚═══════════════════════════════════════════╝\n\n"
        f"🆔 ID: {user_id}\n"
        f"👤 Name: {user.get('first_name', 'User')}\n"
        f"📛 Username: @{user.get('username', 'N/A')}\n"
        f"📅 Joined: {user.get('joined_date', 'N/A')[:10]}\n"
        f"✅ Verified: {'Yes' if user.get('is_verified') else 'No'}\n"
        f"🚫 Banned: {'Yes' if user.get('is_banned') else 'No'}\n\n"
        f"💰 Balance: {user.get('balance', 0)} Credits\n"
        f"📊 Used: {user.get('total_used', 0)}\n"
        f"🎁 Referrals: {user.get('referral_count', 0)}\n\n"
        f"🔗 Referral Link:\n"
        f"   https://t.me/OsintToolboxbot?start=ref_{user_id}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📌 Source: {SOURCE_USERNAME}"
    )
    
    if profile_photo:
        await update.message.reply_photo(
            photo=profile_photo,
            caption=caption,
            reply_markup=USER_KEYBOARD_MARKUP
        )
    else:
        await update.message.reply_text(
            caption,
            reply_markup=USER_KEYBOARD_MARKUP
        )

async def support_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("💬 Telegram Support", url="https://t.me/RJSupp0rtbot")]
    ]
    
    await update.message.reply_text(
        f"╔═══════════════════════════════════════════╗\n"
        f"║  🆘 SUPPORT CENTER                        ║\n"
        f"╚═══════════════════════════════════════════╝\n\n"
        f"👋 Need help? Contact our support team!\n\n"
        f"💬 **Telegram Support**\n"
        f"   • Chat with support\n"
        f"   • Quick response\n"
        f"   • 24/7 availability\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📌 Source: {SOURCE_USERNAME}",
        reply_markup=InlineKeyboardMarkup(keyboard),
        disable_web_page_preview=True
    )

# ==================== USERS MANAGEMENT ====================
async def show_user_management(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("❌ Unauthorized access!")
        return
    
    users = get_all_users()
    total_users = len(users)
    verified = sum(1 for u in users.values() if u.get("is_verified"))
    banned = sum(1 for u in users.values() if u.get("is_banned"))
    
    msg = f"╔═══════════════════════════════════════════╗\n"
    msg += f"║  👥 USER MANAGEMENT                      ║\n"
    msg += f"╚═══════════════════════════════════════════╝\n\n"
    msg += f"📊 **STATISTICS**\n"
    msg += f"   ┌─────────────────────────────────────┐\n"
    msg += f"   │  👥 Total Users    :  {total_users}           │\n"
    msg += f"   │  ✅ Verified      :  {verified}           │\n"
    msg += f"   │  🚫 Banned        :  {banned}           │\n"
    msg += f"   └─────────────────────────────────────┘\n\n"
    
    msg += f"📋 **Recent Users:**\n"
    sorted_users = sorted(users.items(), key=lambda x: x[1].get('joined_date', ''), reverse=True)[:10]
    
    for uid, u in sorted_users:
        name = u.get('first_name', 'Unknown')
        balance = u.get('balance', 0)
        status = "🚫" if u.get('is_banned') else "✅"
        msg += f"   {status} {name} (ID: `{uid}`) - {balance} Credits\n"
    
    msg += f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    msg += f"📌 **Commands:**\n"
    msg += f"   • `/user <id>` - View user details\n"
    msg += f"   • `/ban <id>` - Ban user\n"
    msg += f"   • `/unban <id>` - Unban user\n"
    msg += f"   • `/addcredits <id> <amount>` - Add credits\n"
    msg += f"   • `/removecredits <id> <amount>` - Remove credits\n"
    msg += f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    msg += f"📌 Source: {SOURCE_USERNAME}"
    
    await update.message.reply_text(msg, reply_markup=ADMIN_PANEL_KEYBOARD_MARKUP)

# ==================== USER COMMAND HANDLER ====================
async def user_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("❌ Unauthorized!")
        return
    
    args = context.args
    if not args:
        await update.message.reply_text("❌ Please provide user ID!\nExample: `/user 8940619322`")
        return
    
    cmd = update.message.text.split()[0].lower()
    target_id = int(args[0])
    target_user = get_user(target_id)
    
    if not target_user:
        await update.message.reply_text(f"❌ User `{target_id}` not found!")
        return
    
    if cmd == "/user":
        msg = f"╔═══════════════════════════════════════════╗\n"
        msg += f"║  👤 USER PROFILE                        ║\n"
        msg += f"╚═══════════════════════════════════════════╝\n\n"
        msg += f"🆔 ID: `{target_id}`\n"
        msg += f"👤 Name: {target_user.get('first_name', 'N/A')}\n"
        msg += f"📛 Username: @{target_user.get('username', 'N/A')}\n"
        msg += f"📅 Joined: {target_user.get('joined_date', 'N/A')[:10]}\n"
        msg += f"✅ Verified: {'Yes' if target_user.get('is_verified') else 'No'}\n"
        msg += f"🚫 Banned: {'Yes' if target_user.get('is_banned') else 'No'}\n"
        msg += f"💳 Balance: {target_user.get('balance', 0)} Credits\n"
        msg += f"📊 Used: {target_user.get('total_used', 0)}\n"
        msg += f"🎁 Referrals: {target_user.get('referral_count', 0)}\n"
        await update.message.reply_text(msg)
        
    elif cmd == "/ban":
        reason = " ".join(args[1:]) if len(args) > 1 else "No reason provided"
        update_user(target_id, {"is_banned": True, "ban_reason": reason})
        await update.message.reply_text(f"✅ User `{target_id}` banned!\nReason: {reason}")
        
    elif cmd == "/unban":
        update_user(target_id, {"is_banned": False, "ban_reason": ""})
        await update.message.reply_text(f"✅ User `{target_id}` unbanned!")
        
    elif cmd == "/addcredits":
        if len(args) < 2:
            await update.message.reply_text("❌ Please provide amount!\nExample: `/addcredits 8940619322 10`")
            return
        amount = int(args[1])
        add_credits(target_id, amount, f"Admin added {amount} credits")
        user = get_user(target_id)
        await update.message.reply_text(f"✅ Added {amount} credits to `{target_id}`\n💰 New Balance: {user.get('balance', 0)}")
        
    elif cmd == "/removecredits":  # ✅ New command
        if len(args) < 2:
            await update.message.reply_text("❌ Please provide amount!\nExample: `/removecredits 8940619322 10`")
            return
        amount = int(args[1])
        
        current_balance = target_user.get("balance", 0)
        if current_balance < amount:
            await update.message.reply_text(f"❌ User has only {current_balance} credits. Can't remove {amount}!")
            return
        
        new_balance = current_balance - amount
        update_user(target_id, {"balance": new_balance})
        
        firebase_post(f"transactions/{target_id}", {
            "type": "remove",
            "amount": amount,
            "description": f"Admin removed {amount} credits",
            "timestamp": datetime.datetime.now().isoformat()
        })
        
        user = get_user(target_id)
        await update.message.reply_text(
            f"✅ Removed {amount} credits from `{target_id}`\n"
            f"💰 New Balance: {user.get('balance', 0)}"
        )

# ==================== BROADCAST ====================
async def init_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("❌ Unauthorized!")
        return
    
    context.user_data['broadcast_mode'] = True
    context.user_data['broadcast_type'] = None
    
    kb = [
        [KeyboardButton("📢 All Users (Private + Group)")],
        [KeyboardButton("👥 Only Private Users")],
        [KeyboardButton("🏢 Only Group Users")],
        [KeyboardButton("❌ Cancel Broadcast")]
    ]
    
    await update.message.reply_text(
        f"╔═══════════════════════════════════════════╗\n"
        f"║  📢 BROADCAST WIZARD                      ║\n"
        f"╚═══════════════════════════════════════════╝\n\n"
        f"📤 Select broadcast type:\n\n"
        f"📌 **Options:**\n"
        f"   • All Users (Private + Group)\n"
        f"   • Only Private Users\n"
        f"   • Only Group Users\n\n"
        f"📌 Then send your message.\n\n"
        f"📌 Type `/cancel` to cancel.",
        reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True)
    )

async def handle_broadcast_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    
    if not is_admin(user_id):
        return
    
    if not context.user_data.get('broadcast_mode'):
        return
    
    if text == "❌ Cancel Broadcast":
        context.user_data['broadcast_mode'] = False
        await update.message.reply_text("❌ Broadcast cancelled.", reply_markup=ADMIN_PANEL_KEYBOARD_MARKUP)
        return
    
    if text == "📢 All Users (Private + Group)":
        context.user_data['broadcast_type'] = "all"
        users = get_all_users_combined()
        await update.message.reply_text(
            f"✅ **All Users Selected**\n\n"
            f"📊 Total Users: {len(users)}\n\n"
            f"📤 Send your broadcast message:\n\n"
            f"💡 You can send:\n"
            f"   • Text message\n"
            f"   • Photo with caption\n"
            f"   • Video with caption\n\n"
            f"📌 Type `/cancel` to cancel."
        )
        return
    
    if text == "👥 Only Private Users":
        context.user_data['broadcast_type'] = "private"
        users = get_all_users()
        await update.message.reply_text(
            f"✅ **Private Users Selected**\n\n"
            f"📊 Total Users: {len(users)}\n\n"
            f"📤 Send your broadcast message:\n\n"
            f"💡 You can send:\n"
            f"   • Text message\n"
            f"   • Photo with caption\n"
            f"   • Video with caption\n\n"
            f"📌 Type `/cancel` to cancel."
        )
        return
    
    if text == "🏢 Only Group Users":
        context.user_data['broadcast_type'] = "group"
        users = get_all_group_users_flat()
        await update.message.reply_text(
            f"✅ **Group Users Selected**\n\n"
            f"📊 Total Users: {len(users)}\n\n"
            f"📤 Send your broadcast message:\n\n"
            f"💡 You can send:\n"
            f"   • Text message\n"
            f"   • Photo with caption\n"
            f"   • Video with caption\n\n"
            f"📌 Type `/cancel` to cancel."
        )
        return

async def handle_broadcast_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        return
    
    if not context.user_data.get('broadcast_mode'):
        return
    
    if context.user_data.get('broadcast_type') is None:
        await handle_broadcast_type(update, context)
        return
    
    broadcast_type = context.user_data.get('broadcast_type')
    
    # ✅ Get users based on type
    if broadcast_type == "all":
        users = get_all_users_combined()
    elif broadcast_type == "private":
        users = get_all_users()
    elif broadcast_type == "group":
        users = get_all_group_users_flat()
    else:
        users = get_all_users_combined()
    
    # ✅ Convert to list if dict
    user_list = []
    if isinstance(users, dict):
        for uid, u in users.items():
            if isinstance(u, dict):
                user_list.append({"user_id": uid, **u})
            else:
                user_list.append({"user_id": uid})
    elif isinstance(users, list):
        user_list = users
    else:
        user_list = []
    
    total = len(user_list)
    
    if total == 0:
        await update.message.reply_text("❌ No users to broadcast!")
        context.user_data['broadcast_mode'] = False
        return
    
    progress_msg = await update.message.reply_text(f"📢 Broadcasting to {total} users... Please wait.")
    
    sent = 0
    failed = 0
    failed_users = []
    
    # ✅ Send message to each user
    if update.message.photo:
        media_id = update.message.photo[-1].file_id
        caption = update.message.caption or ""
        for user in user_list:
            try:
                uid = int(user.get("user_id") if isinstance(user, dict) else user)
                
                try:
                    await context.bot.send_photo(chat_id=uid, photo=media_id, caption=caption)
                    sent += 1
                except Exception as e:
                    print(f"❌ Failed to send to {uid}: {e}")
                    failed += 1
                    failed_users.append(uid)
                
                await asyncio.sleep(0.05)
                
            except Exception as e:
                print(f"❌ Error with user {user}: {e}")
                failed += 1
                continue
                
    elif update.message.video:
        media_id = update.message.video.file_id
        caption = update.message.caption or ""
        for user in user_list:
            try:
                uid = int(user.get("user_id") if isinstance(user, dict) else user)
                
                try:
                    await context.bot.send_video(chat_id=uid, video=media_id, caption=caption)
                    sent += 1
                except Exception as e:
                    print(f"❌ Failed to send to {uid}: {e}")
                    failed += 1
                    failed_users.append(uid)
                
                await asyncio.sleep(0.05)
                
            except Exception as e:
                print(f"❌ Error with user {user}: {e}")
                failed += 1
                continue
                
    else:
        text = update.message.text
        for user in user_list:
            try:
                uid = int(user.get("user_id") if isinstance(user, dict) else user)
                
                try:
                    await context.bot.send_message(chat_id=uid, text=text)
                    sent += 1
                except Exception as e:
                    print(f"❌ Failed to send to {uid}: {e}")
                    failed += 1
                    failed_users.append(uid)
                
                await asyncio.sleep(0.05)
                
            except Exception as e:
                print(f"❌ Error with user {user}: {e}")
                failed += 1
                continue
    
    result_text = (
        f"╔═══════════════════════════════════════════╗\n"
        f"║  ✅ BROADCAST COMPLETE                    ║\n"
        f"╚═══════════════════════════════════════════╝\n\n"
        f"📊 **Delivery Report**\n"
        f"   ┌─────────────────────────────────────┐\n"
        f"   │  👥 Total Users    :  {total}           │\n"
        f"   │  ✅ Delivered      :  {sent}           │\n"
        f"   │  ❌ Failed         :  {failed}           │\n"
        f"   │  📋 Type          :  {broadcast_type.upper()}\n"
        f"   └─────────────────────────────────────┘\n"
    )
    
    if failed_users and len(failed_users) <= 10:
        result_text += f"\n❌ Failed Users:\n"
        for uid in failed_users[:10]:
            result_text += f"   • `{uid}`\n"
    
    result_text += f"\n📌 Source: {SOURCE_USERNAME}"
    
    await progress_msg.edit_text(result_text)
    
    await update.message.reply_text(
        "📌 Back to Admin Panel",
        reply_markup=ADMIN_PANEL_KEYBOARD_MARKUP
    )
    
    context.user_data['broadcast_mode'] = False
    context.user_data['broadcast_type'] = None

# ==================== GROUP BROADCAST ====================
async def group_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bot ko specific group mein message bhejna"""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ Unauthorized!")
        return
    
    context.user_data['group_broadcast_mode'] = True
    context.user_data['group_broadcast_target'] = None
    
    groups = get_all_groups()
    
    if not groups:
        await update.message.reply_text("❌ Koi group registered nahi hai!")
        return
    
    msg = "📢 **Group Broadcast**\n\n"
    msg += "Select a group to broadcast:\n\n"
    
    kb = []
    for gid, g in groups.items():
        group_name = g.get('group_name', 'Unknown Group')
        group_code = g.get('group_code', 'N/A')
        button_text = f"📌 {group_name} ({group_code})"
        kb.append([InlineKeyboardButton(button_text, callback_data=f"group_broadcast_{gid}")])
    
    kb.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel_group_broadcast")])
    
    await update.message.reply_text(
        msg,
        reply_markup=InlineKeyboardMarkup(kb)
    )

async def group_broadcast_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    
    user_id = q.from_user.id
    if not is_admin(user_id):
        await q.edit_message_text("❌ Unauthorized!")
        return
    
    data = q.data
    
    if data == "cancel_group_broadcast":
        context.user_data['group_broadcast_mode'] = False
        context.user_data['group_broadcast_target'] = None
        await q.edit_message_text("❌ Broadcast cancelled.")
        return
    
    if data.startswith("group_broadcast_"):
        group_id = data.replace("group_broadcast_", "")
        group = get_group(group_id)
        
        if not group:
            await q.edit_message_text("❌ Group not found!")
            return
        
        context.user_data['group_broadcast_mode'] = True
        context.user_data['group_broadcast_target'] = group_id
        
        await q.edit_message_text(
            f"✅ **Group Selected:** {group.get('group_name', 'Unknown')}\n\n"
            f"📤 Send your broadcast message:\n\n"
            f"💡 You can send:\n"
            f"   • Text message\n"
            f"   • Photo with caption\n"
            f"   • Video with caption\n\n"
            f"📌 Type `/cancel` to cancel."
        )

async def handle_group_broadcast_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        return
    
    if not context.user_data.get('group_broadcast_mode'):
        return
    
    group_id = context.user_data.get('group_broadcast_target')
    if not group_id:
        await update.message.reply_text("❌ Pehle group select karo!")
        return
    
    group = get_group(group_id)
    if not group:
        await update.message.reply_text("❌ Group not found!")
        context.user_data['group_broadcast_mode'] = False
        return
    
    group_name = group.get('group_name', 'Unknown Group')
    
    try:
        progress_msg = await update.message.reply_text(f"📢 Sending broadcast to {group_name}...")
        
        if update.message.photo:
            await context.bot.send_photo(
                chat_id=int(group_id),
                photo=update.message.photo[-1].file_id,
                caption=update.message.caption or ""
            )
        elif update.message.video:
            await context.bot.send_video(
                chat_id=int(group_id),
                video=update.message.video.file_id,
                caption=update.message.caption or ""
            )
        else:
            await context.bot.send_message(
                chat_id=int(group_id),
                text=update.message.text
            )
        
        await progress_msg.edit_text(
            f"✅ **Broadcast Sent Successfully!**\n\n"
            f"📌 Group: {group_name}\n"
            f"🆔 Group ID: `{group_id}`\n\n"
            f"📌 Message delivered to group."
        )
        
    except Exception as e:
        await progress_msg.edit_text(
            f"❌ **Broadcast Failed!**\n\n"
            f"Error: {str(e)}\n\n"
            f"💡 Check:\n"
            f"   • Bot is admin in group?\n"
            f"   • Group ID is correct?\n"
            f"   • Bot has permissions?"
        )
    
    context.user_data['group_broadcast_mode'] = False
    context.user_data['group_broadcast_target'] = None

async def cancel_group_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        return
    
    if context.user_data.get('group_broadcast_mode'):
        context.user_data['group_broadcast_mode'] = False
        context.user_data['group_broadcast_target'] = None
        await update.message.reply_text(
            "❌ Broadcast cancelled.",
            reply_markup=ADMIN_PANEL_KEYBOARD_MARKUP
        )

# ==================== CODE MANAGEMENT ====================
async def show_code_management(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("❌ Unauthorized!")
        return
    
    codes = firebase_get("redeem_codes") or {}
    total = len(codes)
    active = sum(1 for c in codes.values() if c.get("is_active"))
    used = sum(1 for c in codes.values() if c.get("usage_count", 0) >= c.get("usage_limit", 1))
    
    msg = f"╔═══════════════════════════════════════════╗\n"
    msg += f"║  🎫 CODE MANAGEMENT                      ║\n"
    msg += f"╚═══════════════════════════════════════════╝\n\n"
    msg += f"📊 **STATISTICS**\n"
    msg += f"   ┌─────────────────────────────────────┐\n"
    msg += f"   │  📦 Total Codes    :  {total}           │\n"
    msg += f"   │  🟢 Active        :  {active}           │\n"
    msg += f"   │  🔴 Used          :  {used}           │\n"
    msg += f"   └─────────────────────────────────────┘\n\n"
    
    msg += f"📋 **Recent Codes:**\n"
    sorted_codes = sorted(codes.items(), key=lambda x: x[1].get('created_at', ''), reverse=True)[:10]
    
    for key, val in sorted_codes:
        name = val.get('code_name', 'Auto')
        credits = val.get('credits', 0)
        status = "🟢" if val.get('is_active') else "🔴"
        msg += f"   {status} {name} - {credits} Credits\n"
        msg += f"      Code: `{key}`\n"
    
    msg += f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    msg += f"📌 **Commands:**\n"
    msg += f"   • `/gencode <credits> <limit>` - Generate code\n"
    msg += f"   • `/listcodes` - List all codes\n"
    msg += f"   • `/deletecode <code>` - Delete code\n"
    msg += f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    msg += f"📌 Source: {SOURCE_USERNAME}"
    
    await update.message.reply_text(msg, reply_markup=ADMIN_PANEL_KEYBOARD_MARKUP)

async def gencode_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("❌ Unauthorized!")
        return
    
    args = context.args
    if len(args) < 2:
        await update.message.reply_text(
            f"❌ **Usage:** `/gencode <credits> <limit>`\n\n"
            f"💡 Example: `/gencode 10 100`\n"
            f"   Generates a code with 10 credits, 100 uses"
        )
        return
    
    try:
        credits = int(args[0])
        limit = int(args[1])
        
        code = generate_code()
        save_redeem_code(code, credits, ADMIN_ID, limit)
        
        await update.message.reply_text(
            f"✅ **Code Generated Successfully!**\n\n"
            f"🔑 Code: `{code}`\n"
            f"💳 Credits: {credits}\n"
            f"👥 Limit: {limit} uses\n"
            f"📌 Status: Active\n\n"
            f"📌 Share this code with users!"
        )
    except ValueError:
        await update.message.reply_text("❌ Please enter valid numbers!")

async def listcodes_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("❌ Unauthorized!")
        return
    
    codes = firebase_get("redeem_codes") or {}
    
    if not codes:
        await update.message.reply_text("📋 No codes found!")
        return
    
    msg = f"╔═══════════════════════════════════════════╗\n"
    msg += f"║  📋 ALL REDEEM CODES                     ║\n"
    msg += f"╚═══════════════════════════════════════════╝\n\n"
    
    for key, val in codes.items():
        name = val.get('code_name', 'Auto')
        credits = val.get('credits', 0)
        used = val.get('usage_count', 0)
        limit = val.get('usage_limit', 1)
        status = "Active" if val.get('is_active') else "Inactive"
        msg += f"🔑 `{key}`\n"
        msg += f"   ├─ Name: {name}\n"
        msg += f"   ├─ Credits: {credits}\n"
        msg += f"   ├─ Used: {used}/{limit}\n"
        msg += f"   └─ Status: {status}\n\n"
    
    await update.message.reply_text(msg)

async def deletecode_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("❌ Unauthorized!")
        return
    
    args = context.args
    if not args:
        await update.message.reply_text("❌ **Usage:** `/deletecode <code>`")
        return
    
    code = args[0].upper()
    
    if firebase_patch(f"redeem_codes/{code}", {"is_active": False}):
        await update.message.reply_text(f"✅ Code `{code}` deactivated successfully!")
    else:
        await update.message.reply_text(f"❌ Code `{code}` not found!")

# ==================== GROUP MANAGEMENT ADMIN PANEL ====================
async def show_group_management(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("❌ Unauthorized access!")
        return
    
    groups = get_all_groups()
    
    msg = f"╔═══════════════════════════════════════════╗\n"
    msg += f"║  📊 GROUP MANAGEMENT                      ║\n"
    msg += f"╚═══════════════════════════════════════════╝\n\n"
    msg += f"📊 **TOTAL GROUPS:** {len(groups)}\n\n"
    
    if groups:
        for gid, g in groups.items():
            code = g.get('group_code', 'N/A')
            status = "✅ Active" if g.get('is_active') else "❌ Inactive"
            
            msg += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            msg += f"🔑 **Code:** `{code}`\n"
            msg += f"📌 **{g.get('group_name', 'Unknown')}**\n"
            msg += f"├─ ID: `{gid}`\n"
            msg += f"├─ Status: {status}\n"
            msg += f"├─ Members: {g.get('member_count', 0)}\n"
            msg += f"├─ Daily: {g.get('credits', {}).get('daily', 0)}\n"
            msg += f"├─ Weekly: {g.get('credits', {}).get('weekly', 0)}\n"
            msg += f"└─ Monthly: {g.get('credits', {}).get('monthly', 0)}\n\n"
    else:
        msg += "❌ No groups added yet.\n"
    
    msg += f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    msg += f"📌 **Enter group code to manage:**\n"
    msg += f"   Example: `GRP-001`\n\n"
    msg += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    msg += f"📌 Source: {SOURCE_USERNAME}"
    
    await update.message.reply_text(msg, reply_markup=ADMIN_PANEL_KEYBOARD_MARKUP)

async def show_group_settings(update: Update, context: ContextTypes.DEFAULT_TYPE, group_id):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return
    
    group = get_group(group_id)
    if not group:
        await update.message.reply_text("❌ Group not found!")
        return
    
    code = group.get('group_code', 'N/A')
    
    msg = f"╔═══════════════════════════════════════════╗\n"
    msg += f"║  📊 GROUP SETTINGS                       ║\n"
    msg += f"╚═══════════════════════════════════════════╝\n\n"
    msg += f"🔑 **Code:** `{code}`\n"
    msg += f"📌 **{group.get('group_name', 'Unknown')}**\n"
    msg += f"🆔 ID: `{group_id}`\n"
    msg += f"🔗 Link: {group.get('group_link', 'N/A')}\n"
    msg += f"📊 Status: {'✅ Active' if group.get('is_active') else '❌ Inactive'}\n"
    msg += f"👥 Members: {group.get('member_count', 0)}\n\n"
    msg += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    msg += f"💳 **CREDITS:**\n"
    msg += f"├─ Daily: {group.get('credits', {}).get('daily', 0)}\n"
    msg += f"├─ Weekly: {group.get('credits', {}).get('weekly', 0)}\n"
    msg += f"└─ Monthly: {group.get('credits', {}).get('monthly', 0)}\n\n"
    msg += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    msg += f"💬 **WELCOME MESSAGE:**\n"
    msg += f"{group.get('welcome_message', 'Not set')[:100]}...\n\n"
    msg += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    msg += f"📌 Source: {SOURCE_USERNAME}"
    
    kb = [
        [InlineKeyboardButton("🔄 Toggle Active", callback_data=f"group_toggle_{group_id}")],
        [InlineKeyboardButton("🔐 Toggle Verification", callback_data=f"group_toggle_verification_{group_id}")],
        [InlineKeyboardButton("💳 Set Credits", callback_data=f"group_credits_{group_id}")],
        [InlineKeyboardButton("💬 Set Welcome", callback_data=f"group_welcome_{group_id}")],
        [InlineKeyboardButton("👥 Manage Admins", callback_data=f"group_admins_{group_id}")],
        [InlineKeyboardButton("⬅️ Back", callback_data="group_management")]
    ]
    
    await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(kb))

async def group_toggle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    
    user_id = q.from_user.id
    if not is_admin(user_id):
        await q.edit_message_text("❌ Unauthorized access!")
        return
    
    group_id = q.data.replace("group_toggle_", "")
    group = get_group(group_id)
    
    if not group:
        await q.edit_message_text("❌ Group not found!")
        return
    
    current = group.get("is_active", False)
    new_status = not current
    toggle_group_active(group_id, new_status)
    
    status = "Activated" if new_status else "Deactivated"
    await q.edit_message_text(f"✅ Group {status} successfully!")
    await show_group_settings(update, context, group_id)

async def group_toggle_verification_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    
    user_id = q.from_user.id
    if not is_admin(user_id):
        await q.edit_message_text("❌ Unauthorized access!")
        return
    
    group_id = q.data.replace("group_toggle_verification_", "")
    group = get_group(group_id)
    
    if not group:
        await q.edit_message_text("❌ Group not found!")
        return
    
    current = group.get("verification_required", True)
    new_status = not current
    firebase_patch(f"groups/{group_id}", {"verification_required": new_status})
    
    status = "ON" if new_status else "OFF"
    await q.edit_message_text(
        f"✅ **Group Verification turned {status}!**\n\n"
        f"🔹 When ON: Users must verify to use bot\n"
        f"🔹 When OFF: Anyone can use the bot\n\n"
        f"[⬅️ Back to Settings]",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="group_management")]])
    )

async def group_credits_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    
    user_id = q.from_user.id
    if not is_admin(user_id):
        await q.edit_message_text("❌ Unauthorized access!")
        return
    
    group_id = q.data.replace("group_credits_", "")
    
    await q.edit_message_text(
        f"💳 **Set Group Credits**\n\n"
        f"Enter daily, weekly, monthly credits:\n\n"
        f"📌 **Format:**\n"
        f"   Daily | Weekly | Monthly\n\n"
        f"💡 **Example:**\n"
        f"   5 | 25 | 100\n\n"
        f"Type `/cancel` to cancel."
    )
    context.user_data['set_group_credits'] = group_id

async def group_welcome_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    
    user_id = q.from_user.id
    if not is_admin(user_id):
        await q.edit_message_text("❌ Unauthorized access!")
        return
    
    group_id = q.data.replace("group_welcome_", "")
    
    await q.edit_message_text(
        f"💬 **Set Welcome Message**\n\n"
        f"Enter welcome message for the group:\n\n"
        f"📌 This message will show when user types /start\n\n"
        f"💡 **Example:**\n"
        f"   Welcome to NAX INFO! Use /start to begin.\n\n"
        f"Type `/cancel` to cancel."
    )
    context.user_data['set_group_welcome'] = group_id

async def group_admins_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    
    user_id = q.from_user.id
    if not is_admin(user_id):
        await q.edit_message_text("❌ Unauthorized access!")
        return
    
    group_id = q.data.replace("group_admins_", "")
    group = get_group(group_id)
    
    if not group:
        await q.edit_message_text("❌ Group not found!")
        return
    
    admins = group.get("admin_permission", {})
    
    msg = f"👥 **Group Admins**\n\n"
    msg += f"📌 Group: {group.get('group_name', 'Unknown')}\n\n"
    
    if admins:
        for uid, role in admins.items():
            msg += f"├─ User ID: `{uid}` - {role}\n"
    else:
        msg += "❌ No admins added.\n"
    
    msg += f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    msg += f"📌 Source: {SOURCE_USERNAME}"
    
    kb = [
        [InlineKeyboardButton("➕ Add Admin", callback_data=f"group_add_admin_{group_id}")],
        [InlineKeyboardButton("➖ Remove Admin", callback_data=f"group_remove_admin_{group_id}")],
        [InlineKeyboardButton("⬅️ Back", callback_data=f"group_settings_{group_id}")]
    ]
    
    await q.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(kb))

async def group_add_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    
    user_id = q.from_user.id
    if not is_admin(user_id):
        await q.edit_message_text("❌ Unauthorized access!")
        return
    
    group_id = q.data.replace("group_add_admin_", "")
    
    await q.edit_message_text(
        f"👥 **Add Group Admin**\n\n"
        f"Enter user ID to add as admin:\n\n"
        f"💡 **Example:**\n"
        f"   8940619322\n\n"
        f"Type `/cancel` to cancel."
    )
    context.user_data['add_group_admin'] = group_id

async def group_remove_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    
    user_id = q.from_user.id
    if not is_admin(user_id):
        await q.edit_message_text("❌ Unauthorized access!")
        return
    
    group_id = q.data.replace("group_remove_admin_", "")
    group = get_group(group_id)
    
    if not group:
        await q.edit_message_text("❌ Group not found!")
        return
    
    admins = group.get("admin_permission", {})
    
    if not admins:
        await q.edit_message_text("❌ No admins to remove!")
        return
    
    msg = f"👥 **Remove Admin**\n\n"
    msg += f"Select user to remove:\n\n"
    
    kb = []
    for uid, role in admins.items():
        kb.append([InlineKeyboardButton(f"🗑️ {uid} ({role})", callback_data=f"group_confirm_remove_{group_id}_{uid}")])
    kb.append([InlineKeyboardButton("⬅️ Back", callback_data=f"group_admins_{group_id}")])
    
    await q.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(kb))

async def group_confirm_remove_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    
    user_id = q.from_user.id
    if not is_admin(user_id):
        await q.edit_message_text("❌ Unauthorized access!")
        return
    
    parts = q.data.replace("group_confirm_remove_", "").split("_")
    group_id = parts[0]
    admin_id = parts[1]
    
    if remove_group_admin(group_id, admin_id):
        await q.edit_message_text(f"✅ Admin `{admin_id}` removed successfully!")
    else:
        await q.edit_message_text("❌ Failed to remove admin!")
    
    await group_admins_callback(update, context)

# ==================== VERIFICATION SETTINGS ====================
async def show_verification_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("❌ Unauthorized!")
        return
    
    channels = get_channels()
    status = get_setting("verification_active")
    
    msg = f"⚙️ **Verification Settings**\n\n"
    msg += f"🔹 Status: {'ON' if status != 'False' else 'OFF'}\n"
    msg += f"📢 Channels: {len(channels)}\n"
    
    for ch in channels:
        msg += f"   • {ch}\n"
    
    kb = [
        [InlineKeyboardButton("🔄 Toggle", callback_data="v_toggle")],
        [InlineKeyboardButton("➕ Add Channel", callback_data="v_add_channel")],
        [InlineKeyboardButton("⬅️ Back", callback_data="admin_back_panel")]
    ]
    
    await update.effective_message.reply_text(msg, reply_markup=InlineKeyboardMarkup(kb))

async def v_toggle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    
    user_id = q.from_user.id
    if not is_admin(user_id):
        await q.edit_message_text("❌ Unauthorized!")
        return
    
    current = get_setting("verification_active")
    new = "False" if current != "False" else "True"
    set_setting("verification_active", new)
    
    await q.edit_message_text(f"✅ Verification turned {'ON' if new == 'True' else 'OFF'}!")

async def v_add_channel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    
    user_id = q.from_user.id
    if not is_admin(user_id):
        await q.edit_message_text("❌ Unauthorized!")
        return
    
    context.user_data['v_add_channel'] = True
    
    await q.edit_message_text(
        f"📢 **Add Channel/Group**\n\n"
        f"Enter username or link:\n\n"
        f"Example: @NAXupdate\n"
        f"Type `/cancel` to cancel."
    )

# ==================== REDEEM VERIFICATION ADMIN ====================
async def show_redeem_verify_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("❌ Unauthorized!")
        return
    
    status = get_redeem_verify_status()
    channels = get_redeem_channels()
    
    status_display = "✅ ON" if status == "ON" else "❌ OFF"
    
    msg = f"╔═══════════════════════════════════════════╗\n"
    msg += f"║  🎫 REDEEM VERIFICATION SETTINGS          ║\n"
    msg += f"╚═══════════════════════════════════════════╝\n\n"
    msg += f"📊 STATUS: {status_display}\n\n"
    msg += f"📢 CHANNELS ({len(channels)}):\n"
    
    if channels:
        for i, ch in enumerate(channels, 1):
            msg += f"   {i}. {ch}\n"
    else:
        msg += "   ❌ No channels\n"
    
    msg += f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    msg += f"📌 Source: {SOURCE_USERNAME}"
    
    kb = [
        [InlineKeyboardButton(f"🔄 Toggle {status}", callback_data="redeem_toggle")],
        [InlineKeyboardButton("➕ Add Channel", callback_data="redeem_add_channel")],
        [InlineKeyboardButton("🗑️ Remove Channel", callback_data="redeem_remove_channel")],
        [InlineKeyboardButton("⬅️ Back", callback_data="admin_back_panel")]
    ]
    
    await update.effective_message.reply_text(msg, reply_markup=InlineKeyboardMarkup(kb))

async def redeem_toggle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    
    user_id = q.from_user.id
    if not is_admin(user_id):
        await q.edit_message_text("❌ Unauthorized!")
        return
    
    current = get_redeem_verify_status()
    new_status = "OFF" if current == "ON" else "ON"
    set_redeem_verify_status(new_status)
    
    await q.edit_message_text(
        f"✅ **Redeem Verification turned {new_status}!**\n\n"
        f"[⬅️ Back]",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="admin_redeem_verify")]])
    )

async def redeem_add_channel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    
    user_id = q.from_user.id
    if not is_admin(user_id):
        await q.edit_message_text("❌ Unauthorized!")
        return
    
    context.user_data['redeem_add_channel'] = True
    
    await q.edit_message_text(
        f"📢 **Add Redeem Channel/Group**\n\n"
        f"Enter channel/group username or link:\n\n"
        f"💡 Examples:\n"
        f"   • @NAXupdate\n"
        f"   • https://t.me/NAXupdate\n"
        f"   • https://t.me/+kbHecvNH8OBmZTRl\n\n"
        f"Type `/cancel` to cancel."
    )

async def redeem_remove_channel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    
    user_id = q.from_user.id
    if not is_admin(user_id):
        await q.edit_message_text("❌ Unauthorized!")
        return
    
    channels = get_redeem_channels()
    
    if not channels:
        await q.edit_message_text("❌ No channels to remove.")
        return
    
    msg = f"📢 **Select channel to remove:**\n\n"
    for i, ch in enumerate(channels, 1):
        msg += f"   {i}. {ch}\n"
    msg += f"\nType the number to remove.\nType /cancel to cancel."
    
    context.user_data['redeem_remove_channel'] = True
    await q.edit_message_text(msg)

# ==================== ADMIN PANEL ====================
async def show_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("❌ Unauthorized!")
        return
    
    users = get_all_users()
    txt = f"🛠️ **Admin Panel**\n\nTotal Users: {len(users)}\n👨‍💻 Developer: {DEVELOPER_USERNAME}"
    await update.message.reply_text(txt, reply_markup=ADMIN_PANEL_KEYBOARD_MARKUP)

async def handle_admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("❌ Unauthorized!")
        return
    
    txt = update.message.text
    if txt == "👥 Users":
        await show_user_management(update, context)
    elif txt == "📢 Broadcast":
        await init_broadcast(update, context)
    elif txt == "🎫 Code":
        await show_code_management(update, context)
    elif txt == "📈 Referral":
        await show_referral_section(update, context)
    elif txt == "⚙️ Verification":
        await show_verification_settings(update, context)
    elif txt == "📊 Logs":
        await show_system_logs(update, context)
    elif txt == "🎫 Redeem Verify":
        await show_redeem_verify_settings(update, context)
    elif txt == "📊 Groups":
        await show_group_management(update, context)
    elif txt == "🏢 Group Broadcast":
        await group_broadcast(update, context)
    elif txt == "📊 User Actions":
        await show_user_actions(update, context)
    else:
        await update.message.reply_text("Unknown button.")

async def show_user_actions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("❌ Unauthorized access!")
        return
    
    kb = [
        [KeyboardButton("➕ Add Credits")],
        [KeyboardButton("➖ Remove Credits")],
        [KeyboardButton("🚫 Ban User")],
        [KeyboardButton("✅ Unban User")],
        [KeyboardButton("👤 View User")],
        [KeyboardButton("🔙 Back to Admin Panel")]
    ]
    
    await update.message.reply_text(
        "📊 **User Actions**\n\n"
        "Select an action:\n\n"
        "📌 Use `/user <id>` - View user\n"
        "📌 Use `/addcredits <id> <amount>` - Add credits\n"
        "📌 Use `/removecredits <id> <amount>` - Remove credits\n"
        "📌 Use `/ban <id>` - Ban user\n"
        "📌 Use `/unban <id>` - Unban user",
        reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True)
    )

# ==================== ADMIN CALLBACKS ====================
async def admin_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data
    
    user_id = q.from_user.id
    if not is_admin(user_id):
        await q.edit_message_text("❌ Unauthorized!")
        return
    
    if data == "admin_back_panel":
        await show_admin_panel(update, context)
    elif data == "admin_redeem_verify":
        await show_redeem_verify_settings(update, context)
    elif data == "group_management":
        await show_group_management(update, context)
    elif data.startswith("group_settings_"):
        group_id = data.split("_")[2]
        await show_group_settings(update, context, group_id)

# ==================== DUMMY FUNCTIONS ====================
async def show_referral_section(update, context):
    await update.message.reply_text("📈 Referral section coming soon.")

async def show_system_logs(update, context):
    await update.message.reply_text("📊 System logs coming soon.")

# ==================== ERROR HANDLER ====================
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log errors and notify user"""
    try:
        print(f"❌ Error occurred: {context.error}")
        
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "❌ An unexpected error occurred. Please try again later."
            )
    except Exception as e:
        print(f"❌ Error in error handler: {e}")

# ==================== MAIN MENU HANDLER ====================
async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    chat_type = update.effective_chat.type
    
    if is_admin(user_id) and context.user_data.get('broadcast_mode'):
        await handle_broadcast_input(update, context)
        return
    
    if is_admin(user_id) and context.user_data.get('group_broadcast_mode'):
        await handle_group_broadcast_input(update, context)
        return
    
    if text == "❌ Cancel Broadcast":
        context.user_data['broadcast_mode'] = False
        context.user_data['broadcast_type'] = None
        await update.message.reply_text(
            "❌ Broadcast cancelled.",
            reply_markup=ADMIN_PANEL_KEYBOARD_MARKUP
        )
        return
    
    if text == "❌ Cancel Group Broadcast":
        context.user_data['group_broadcast_mode'] = False
        context.user_data['group_broadcast_target'] = None
        await update.message.reply_text(
            "❌ Group Broadcast cancelled.",
            reply_markup=ADMIN_PANEL_KEYBOARD_MARKUP
        )
        return
    
    # User actions handling
    if is_admin(user_id):
        if text == "➕ Add Credits":
            context.user_data['awaiting'] = 'add_credits'
            await update.message.reply_text(
                "📝 **Add Credits**\n\n"
                "Send: `user_id | amount`\n\n"
                "💡 Example:\n"
                "`8940619322 | 50`\n\n"
                "Type `/cancel` to cancel."
            )
            return
        
        elif text == "➖ Remove Credits":
            context.user_data['awaiting'] = 'remove_credits'
            await update.message.reply_text(
                "📝 **Remove Credits**\n\n"
                "Send: `user_id | amount`\n\n"
                "💡 Example:\n"
                "`8940619322 | 30`\n\n"
                "Type `/cancel` to cancel."
            )
            return
        
        elif text == "🚫 Ban User":
            context.user_data['awaiting'] = 'ban_user'
            await update.message.reply_text(
                "📝 **Ban User**\n\n"
                "Send: `user_id | reason`\n\n"
                "💡 Example:\n"
                "`8940619322 | Spamming`\n\n"
                "Type `/cancel` to cancel."
            )
            return
        
        elif text == "✅ Unban User":
            context.user_data['awaiting'] = 'unban_user'
            await update.message.reply_text(
                "📝 **Unban User**\n\n"
                "Send: `user_id`\n\n"
                "💡 Example:\n"
                "`8940619322`\n\n"
                "Type `/cancel` to cancel."
            )
            return
        
        elif text == "👤 View User":
            context.user_data['awaiting'] = 'view_user'
            await update.message.reply_text(
                "📝 **View User**\n\n"
                "Send: `user_id`\n\n"
                "💡 Example:\n"
                "`8940619322`\n\n"
                "Type `/cancel` to cancel."
            )
            return
    
    # Handle user action inputs
    if context.user_data.get('awaiting') in ['add_credits', 'remove_credits', 'ban_user', 'unban_user', 'view_user']:
        await handle_user_action_input(update, context)
        return
    
    # ... rest of existing code ...
    
    if chat_type in ["group", "supergroup"]:
        chat_id = str(update.effective_chat.id)
        
        if not is_allowed_group(chat_id):
            await update.message.reply_text(
                f"❌ This bot only works in registered groups.\n"
                f"📌 Type /start to register this group."
            )
            return
        
        if not is_group_user_verified(chat_id, user_id):
            is_verified = await check_group_user_verification(chat_id, user_id, context)
            
            if not is_verified:
                kb = [
                    [InlineKeyboardButton("🔗 Join NAX Update", url="https://t.me/NAXupdate")],
                    [InlineKeyboardButton("🔗 Join NAX INFO", url="https://t.me/NAX_INF0")],
                    [InlineKeyboardButton("✅ I have Joined", callback_data=f"verify_group_{chat_id}")]
                ]
                
                await update.message.reply_text(
                    f"🔐 Verification required! Please /start",
                    reply_markup=InlineKeyboardMarkup(kb)
                )
                return
    
    if chat_type not in ["group", "supergroup"]:
        is_member = await check_user_membership(user_id, context)
        if not is_member:
            await update.message.reply_text(
                "🔐 Verification required! Please /start",
                reply_markup=VERIFY_KEYBOARD_MARKUP
            )
            return
    
    if text == "❌ Cancel":
        context.user_data['awaiting'] = None
        context.user_data['lookup_mode'] = False
        context.user_data['admin_user_search'] = False
        context.user_data['admin_action_type'] = None
        context.user_data['admin_broadcast'] = False
        context.user_data['admin_code'] = False
        context.user_data['admin_verification'] = False
        
        if chat_type in ["group", "supergroup"]:
            markup = GROUP_KEYBOARD_MARKUP
        else:
            markup = ADMIN_USER_KEYBOARD_MARKUP if is_admin(user_id) else USER_KEYBOARD_MARKUP
        
        await update.message.reply_text(
            "✅ Cancelled. Back to main menu.",
            reply_markup=markup
        )
        return
    
    if is_admin(user_id):
        if text == "🛠️ Admin Panel":
            context.user_data['awaiting'] = None
            context.user_data['lookup_mode'] = False
            await show_admin_panel(update, context)
            return
        if text == "🔙 Back to User Panel":
            context.user_data['awaiting'] = None
            context.user_data['lookup_mode'] = False
            await user_dashboard(update, context)
            return
        if text in ["👥 Users", "📢 Broadcast", "🎫 Code", "📈 Referral", "⚙️ Verification", "📊 Logs", "🎫 Redeem Verify", "📊 Groups", "🏢 Group Broadcast", "📊 User Actions"]:
            context.user_data['awaiting'] = None
            context.user_data['lookup_mode'] = False
            await handle_admin_menu(update, context)
            return
    
    if text == "🔄 Refresh Balance":
        context.user_data['awaiting'] = None
        context.user_data['lookup_mode'] = False
        await my_credits_menu(update, context)
        return
    if text == "🎫 Redeem Code":
        context.user_data['awaiting'] = 'redeem'
        context.user_data['lookup_mode'] = False
        await update.message.reply_text("🎫 Enter your redeem code:")
        return
    if text == "🔙 Back to Main Menu":
        context.user_data['awaiting'] = None
        context.user_data['lookup_mode'] = False
        await user_dashboard(update, context)
        return
    
    if context.user_data.get('awaiting') == 'redeem':
        await handle_redeem(update, context)
        context.user_data['awaiting'] = None
        context.user_data['lookup_mode'] = False
        return
    
    if context.user_data.get('lookup_mode'):
        lookup_type = context.user_data.get('awaiting')
        
        if lookup_type in ["number", "vehicle", "ifsc", "ip", "weather", "pin", "gst", "tg_info", "imei"]:
            await fetch_lookup(update, context, lookup_type, text)
            return
    
    map_action = {
        "📞 Number": "number",
        "🚗 Vehicle": "vehicle",
        "🏦 IFSC": "ifsc",
        "🌐 IP": "ip",
        "🌤️ Weather": "weather",
        "📮 PIN": "pin",
        "🏢 GST": "gst",
        "📱 TG Info": "tg_info",
        "📱 IMEI": "imei"
    }
    
    if text in map_action:
        context.user_data['awaiting'] = map_action[text]
        context.user_data['lookup_mode'] = True
        
        examples = {
            "📞 Number": "9876543210",
            "🚗 Vehicle": "RJ14CV0002",
            "🏦 IFSC": "KKBK0000261",
            "🌐 IP": "8.8.8.8",
            "🌤️ Weather": "Delhi",
            "📮 PIN": "411001",
            "🏢 GST": "22AAAAA0000A1Z5",
            "📱 TG Info": "rajkumar",
            "📱 IMEI": "123456789012345"
        }
        
        await update.message.reply_text(
            f"Send **{text}** value:\nExample: `{examples[text]}`\n\n💡 You can send multiple values one by one.",
            reply_markup=LOOKUP_KEYBOARD_MARKUP
        )
        return
    
    if text == "💳 My Credits":
        context.user_data['awaiting'] = None
        context.user_data['lookup_mode'] = False
        await my_credits_menu(update, context)
        return
    elif text == "👤 Profile":
        context.user_data['awaiting'] = None
        context.user_data['lookup_mode'] = False
        await profile_menu(update, context)
        return
    elif text == "🆘 Support":
        context.user_data['awaiting'] = None
        context.user_data['lookup_mode'] = False
        await support_menu(update, context)
        return
    
    await update.message.reply_text(
        "Please use the buttons below.",
        reply_markup=ADMIN_USER_KEYBOARD_MARKUP if is_admin(user_id) else USER_KEYBOARD_MARKUP
    )

# ==================== USER ACTION INPUT HANDLER ====================
async def handle_user_action_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle user action inputs"""
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return
    
    action = context.user_data.get('awaiting')
    text = update.message.text.strip()
    
    if text == "/cancel":
        context.user_data['awaiting'] = None
        await update.message.reply_text("❌ Cancelled.")
        return
    
    if action == 'add_credits':
        try:
            parts = text.split('|')
            if len(parts) == 2:
                target_id = int(parts[0].strip())
                amount = int(parts[1].strip())
                
                add_credits(target_id, amount, f"Admin added {amount} credits")
                user = get_user(target_id)
                await update.message.reply_text(
                    f"✅ Added {amount} credits to `{target_id}`\n"
                    f"💰 New Balance: {user.get('balance', 0)}"
                )
            else:
                await update.message.reply_text("❌ Invalid format! Use: `user_id | amount`")
        except ValueError:
            await update.message.reply_text("❌ Invalid input! Please enter valid numbers.")
        
        context.user_data['awaiting'] = None
        
    elif action == 'remove_credits':
        try:
            parts = text.split('|')
            if len(parts) == 2:
                target_id = int(parts[0].strip())
                amount = int(parts[1].strip())
                
                target_user = get_user(target_id)
                if not target_user:
                    await update.message.reply_text(f"❌ User `{target_id}` not found!")
                    context.user_data['awaiting'] = None
                    return
                
                current_balance = target_user.get("balance", 0)
                if current_balance < amount:
                    await update.message.reply_text(
                        f"❌ User has only {current_balance} credits. Can't remove {amount}!"
                    )
                    context.user_data['awaiting'] = None
                    return
                
                new_balance = current_balance - amount
                update_user(target_id, {"balance": new_balance})
                
                firebase_post(f"transactions/{target_id}", {
                    "type": "remove",
                    "amount": amount,
                    "description": f"Admin removed {amount} credits",
                    "timestamp": datetime.datetime.now().isoformat()
                })
                
                user = get_user(target_id)
                await update.message.reply_text(
                    f"✅ Removed {amount} credits from `{target_id}`\n"
                    f"💰 New Balance: {user.get('balance', 0)}"
                )
            else:
                await update.message.reply_text("❌ Invalid format! Use: `user_id | amount`")
        except ValueError:
            await update.message.reply_text("❌ Invalid input! Please enter valid numbers.")
        
        context.user_data['awaiting'] = None
        
    elif action == 'ban_user':
        try:
            parts = text.split('|')
            target_id = int(parts[0].strip())
            reason = parts[1].strip() if len(parts) > 1 else "No reason provided"
            
            update_user(target_id, {"is_banned": True, "ban_reason": reason})
            await update.message.reply_text(f"✅ User `{target_id}` banned!\nReason: {reason}")
        except:
            await update.message.reply_text("❌ Invalid format! Use: `user_id | reason`")
        
        context.user_data['awaiting'] = None
        
    elif action == 'unban_user':
        try:
            target_id = int(text.strip())
            update_user(target_id, {"is_banned": False, "ban_reason": ""})
            await update.message.reply_text(f"✅ User `{target_id}` unbanned!")
        except:
            await update.message.reply_text("❌ Invalid user ID!")
        
        context.user_data['awaiting'] = None
        
    elif action == 'view_user':
        try:
            target_id = int(text.strip())
            target_user = get_user(target_id)
            
            if not target_user:
                await update.message.reply_text(f"❌ User `{target_id}` not found!")
                context.user_data['awaiting'] = None
                return
            
            msg = f"╔═══════════════════════════════════════════╗\n"
            msg += f"║  👤 USER PROFILE                        ║\n"
            msg += f"╚═══════════════════════════════════════════╝\n\n"
            msg += f"🆔 ID: `{target_id}`\n"
            msg += f"👤 Name: {target_user.get('first_name', 'N/A')}\n"
            msg += f"📛 Username: @{target_user.get('username', 'N/A')}\n"
            msg += f"📅 Joined: {target_user.get('joined_date', 'N/A')[:10]}\n"
            msg += f"✅ Verified: {'Yes' if target_user.get('is_verified') else 'No'}\n"
            msg += f"🚫 Banned: {'Yes' if target_user.get('is_banned') else 'No'}\n"
            msg += f"💳 Balance: {target_user.get('balance', 0)} Credits\n"
            msg += f"📊 Used: {target_user.get('total_used', 0)}\n"
            msg += f"🎁 Referrals: {target_user.get('referral_count', 0)}"
            
            await update.message.reply_text(msg)
        except:
            await update.message.reply_text("❌ Invalid user ID!")
        
        context.user_data['awaiting'] = None

# ==================== INPUT HANDLERS ====================
async def handle_group_code_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return
    
    text = update.message.text.strip().upper()
    
    if text.startswith("GRP-"):
        group_id = get_group_by_code(text)
        
        if group_id:
            await show_group_settings(update, context, group_id)
        else:
            await update.message.reply_text(
                f"❌ **Invalid Group Code!**\n\n"
                f"Code: `{text}`\n\n"
                f"📌 Please check the code and try again.\n"
                f"📌 Use `/groups` to see all codes."
            )

async def handle_group_add_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return
    
    if not context.user_data.get('add_group'):
        return
    
    text = update.message.text.strip()
    
    if text == "/cancel":
        context.user_data['add_group'] = False
        await update.message.reply_text("❌ Cancelled.")
        return
    
    try:
        parts = text.split('|')
        if len(parts) >= 3:
            group_id = parts[0].strip()
            group_name = parts[1].strip()
            group_link = parts[2].strip()
            
            group_code = add_group_with_code(group_id, group_name, group_link)
            if group_code:
                await update.message.reply_text(
                    f"✅ **Group Added Successfully!**\n\n"
                    f"🔑 **Group Code:** `{group_code}`\n"
                    f"📌 **Save this code to manage the group.**\n\n"
                    f"📌 ID: {group_id}\n"
                    f"📌 Name: {group_name}\n"
                    f"🔗 Link: {group_link}\n\n"
                    f"📌 Use the code to access settings.\n"
                    f"📌 Type `{group_code}` to manage this group."
                )
                await show_group_settings(update, context, group_id)
            else:
                await update.message.reply_text("❌ Failed to add group!")
        else:
            await update.message.reply_text(
                f"❌ **Invalid Format!**\n\n"
                f"Please use:\n"
                f"`Group ID | Group Name | Group Link`"
            )
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")
    
    context.user_data['add_group'] = False

async def handle_group_admin_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return
    
    group_id = context.user_data.get('add_group_admin')
    if not group_id:
        return
    
    text = update.message.text.strip()
    
    if text == "/cancel":
        context.user_data['add_group_admin'] = None
        await update.message.reply_text("❌ Cancelled.")
        return
    
    try:
        admin_id = int(text)
        if add_group_admin(group_id, admin_id):
            await update.message.reply_text(f"✅ Admin `{admin_id}` added successfully!")
        else:
            await update.message.reply_text("❌ Failed to add admin!")
        
        context.user_data['add_group_admin'] = None
        await group_admins_callback(update, context)
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID! Please enter a number.")

async def handle_group_credits_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return
    
    group_id = context.user_data.get('set_group_credits')
    if not group_id:
        return
    
    text = update.message.text.strip()
    
    if text == "/cancel":
        context.user_data['set_group_credits'] = None
        await update.message.reply_text("❌ Cancelled.")
        return
    
    try:
        parts = text.split('|')
        if len(parts) == 3:
            daily = int(parts[0].strip())
            weekly = int(parts[1].strip())
            monthly = int(parts[2].strip())
            
            set_group_credits(group_id, daily, weekly, monthly)
            
            await update.message.reply_text(
                f"✅ **Credits Set Successfully!**\n\n"
                f"📊 Daily: {daily}\n"
                f"📊 Weekly: {weekly}\n"
                f"📊 Monthly: {monthly}"
            )
            
            context.user_data['set_group_credits'] = None
            await show_group_settings(update, context, group_id)
        else:
            await update.message.reply_text("❌ Invalid format! Use: `Daily | Weekly | Monthly`")
    except ValueError:
        await update.message.reply_text("❌ Please enter valid numbers!")

async def handle_group_welcome_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return
    
    group_id = context.user_data.get('set_group_welcome')
    if not group_id:
        return
    
    text = update.message.text.strip()
    
    if text == "/cancel":
        context.user_data['set_group_welcome'] = None
        await update.message.reply_text("❌ Cancelled.")
        return
    
    set_welcome_message(group_id, text)
    
    await update.message.reply_text(
        f"✅ **Welcome Message Set!**\n\n"
        f"📌 Message:\n"
        f"{text}\n\n"
        f"📌 This will show when users type /start in the group."
    )
    
    context.user_data['set_group_welcome'] = None
    await show_group_settings(update, context, group_id)

async def verify_input_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return
    
    text = update.message.text
    
    if context.user_data.get('v_add_channel'):
        if text == "/cancel":
            context.user_data['v_add_channel'] = False
            await update.message.reply_text("❌ Cancelled.")
            return
        
        channels = get_channels()
        if text not in channels:
            channels.append(text)
            set_channels(channels)
            await update.message.reply_text(f"✅ Added: {text}")
        else:
            await update.message.reply_text("❌ Already exists.")
        context.user_data['v_add_channel'] = False

async def handle_redeem_channel_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return
    
    text = update.message.text.strip()
    
    if text == "/cancel":
        context.user_data['redeem_add_channel'] = False
        context.user_data['redeem_remove_channel'] = False
        await update.message.reply_text("❌ Cancelled.")
        return
    
    if context.user_data.get('redeem_add_channel'):
        channels = get_redeem_channels()
        
        if text in channels:
            await update.message.reply_text(f"❌ Already exists: {text}")
            return
        
        channels.append(text)
        set_redeem_channels(channels)
        
        channel_list = ""
        for i, ch in enumerate(channels, 1):
            channel_list += f"   {i}. {ch}\n"
        
        await update.message.reply_text(
            f"✅ **Added: {text}**\n\n"
            f"📢 Updated List ({len(channels)}):\n{channel_list}"
        )
        context.user_data['redeem_add_channel'] = False
    
    elif context.user_data.get('redeem_remove_channel'):
        try:
            index = int(text) - 1
            channels = get_redeem_channels()
            
            if 0 <= index < len(channels):
                removed = channels.pop(index)
                set_redeem_channels(channels)
                
                channel_list = ""
                for i, ch in enumerate(channels, 1):
                    channel_list += f"   {i}. {ch}\n"
                
                await update.message.reply_text(
                    f"✅ **Removed: {removed}**\n\n"
                    f"📢 Updated List ({len(channels)}):\n{channel_list}"
                )
            else:
                await update.message.reply_text("❌ Invalid number!")
        except ValueError:
            await update.message.reply_text("❌ Please enter a valid number!")
        
        context.user_data['redeem_remove_channel'] = False

# ==================== DAILY RESET TASK ====================
async def reset_daily_usage():
    while True:
        now = datetime.datetime.now()
        midnight = datetime.datetime(now.year, now.month, now.day + 1, 0, 0, 0)
        seconds_until_midnight = (midnight - now).total_seconds()
        
        await asyncio.sleep(seconds_until_midnight)
        
        groups = get_all_groups()
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        for gid in groups:
            firebase_put(f"group_usage/{gid}/{today}", 0)
        
        print(f"✅ Daily usage reset at {datetime.datetime.now()}")

# ==================== ADD GROUP COMMAND ====================
async def add_group_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("❌ Unauthorized access!")
        return
    
    context.user_data['add_group'] = True
    
    await update.message.reply_text(
        f"📢 **Add New Group**\n\n"
        f"Enter group details:\n\n"
        f"📌 **Format:**\n"
        f"   Group ID | Group Name | Group Link\n\n"
        f"💡 **Example:**\n"
        f"   -1003988488077 | NAX INFO | https://t.me/NAX_INF0\n\n"
        f"Type `/cancel` to cancel."
    )

# ==================== MAIN ====================
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("groups", show_group_management))
    app.add_handler(CommandHandler("addgroup", add_group_command))
    
    app.add_handler(CommandHandler("user", user_command_handler))
    app.add_handler(CommandHandler("ban", user_command_handler))
    app.add_handler(CommandHandler("unban", user_command_handler))
    app.add_handler(CommandHandler("addcredits", user_command_handler))
    app.add_handler(CommandHandler("removecredits", user_command_handler))  # ✅ New command
    
    app.add_handler(CommandHandler("gencode", gencode_command))
    app.add_handler(CommandHandler("listcodes", listcodes_command))
    app.add_handler(CommandHandler("deletecode", deletecode_command))
    
    app.add_handler(CommandHandler("groupbroadcast", group_broadcast))
    
    app.add_handler(CallbackQueryHandler(verify_membership_callback, pattern="^verify_membership$"))
    app.add_handler(CallbackQueryHandler(verify_redeem_membership_callback, pattern="^verify_redeem_membership$"))
    app.add_handler(CallbackQueryHandler(verify_group_callback, pattern="^verify_group_"))
    
    app.add_handler(CallbackQueryHandler(admin_callback_handler, pattern="^admin_"))
    app.add_handler(CallbackQueryHandler(redeem_toggle_callback, pattern="^redeem_toggle$"))
    app.add_handler(CallbackQueryHandler(redeem_add_channel_callback, pattern="^redeem_add_channel$"))
    app.add_handler(CallbackQueryHandler(redeem_remove_channel_callback, pattern="^redeem_remove_channel$"))
    app.add_handler(CallbackQueryHandler(v_toggle_callback, pattern="^v_toggle$"))
    app.add_handler(CallbackQueryHandler(v_add_channel_callback, pattern="^v_add_channel$"))
    
    app.add_handler(CallbackQueryHandler(group_toggle_callback, pattern="^group_toggle_"))
    app.add_handler(CallbackQueryHandler(group_toggle_verification_callback, pattern="^group_toggle_verification_"))
    app.add_handler(CallbackQueryHandler(group_credits_callback, pattern="^group_credits_"))
    app.add_handler(CallbackQueryHandler(group_welcome_callback, pattern="^group_welcome_"))
    app.add_handler(CallbackQueryHandler(group_admins_callback, pattern="^group_admins_"))
    app.add_handler(CallbackQueryHandler(group_add_admin_callback, pattern="^group_add_admin_"))
    app.add_handler(CallbackQueryHandler(group_remove_admin_callback, pattern="^group_remove_admin_"))
    app.add_handler(CallbackQueryHandler(group_confirm_remove_admin, pattern="^group_confirm_remove_"))
    
    app.add_handler(CallbackQueryHandler(group_broadcast_callback, pattern="^group_broadcast_"))
    app.add_handler(CallbackQueryHandler(group_broadcast_callback, pattern="^cancel_group_broadcast$"))
    
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_menu))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_user_action_input))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_group_code_input))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_group_add_input))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_group_admin_input))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_group_credits_input))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_group_welcome_input))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, verify_input_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_redeem_channel_input))
    app.add_handler(MessageHandler(filters.PHOTO, handle_menu))
    app.add_handler(MessageHandler(filters.VIDEO, handle_menu))
    
    app.add_error_handler(error_handler)
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.create_task(reset_daily_usage())
    
    print("🤖 OSINT Toolbox Bot is running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()