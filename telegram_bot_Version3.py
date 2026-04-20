import telebot
from telebot import types
import requests

# معلومات التوكنات والتخصيصات
BOT_TOKEN = "PUT_YOUR_BOT_TOKEN_HERE"
API_URL_PRODUCTS = "https://example.com/api/products"
API_URL_ORDER = "https://example.com/api/order"
API_URL_UPDATE = "https://example.com/api/update-products"
API_TOKEN = "API_TOKEN_HERE"
ADMIN_ID = 123456789  # معرف الأدمن الرئيسي (غيّره)
CHANNEL_SUPPORT = "@support_name"  # حساب دعم البوت

# بيانات افتراضية - استبدلها لاحقاً بقاعدة بيانات أو ملفات مُخزّنة
users = {}  # {id: {'balance': int, 'orders': [], ...}}
orders = []  # [{'id':, 'pid':, 'user':, 'price':, 'status':, ...}]
products_cache = []
bot_on = True
profit_percent = 10
exchange_rate = 1

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

def get_user(uid):
    if uid not in users:
        users[uid] = {"balance": 0, "orders": []}
    return users[uid]

def get_products():
    # جلب المنتجات من الـ API
    try:
        r = requests.get(API_URL_PRODUCTS, headers={'Authorization': f"Bearer {API_TOKEN}"})
        if r.status_code == 200:
            return r.json().get('products', [])
        return []
    except:
        return []

def find_product_by_id(pid):
    for p in products_cache:
        if p['id'] == pid: return p
    return None

def make_keyboard(btn_rows):
    kb = types.InlineKeyboardMarkup(row_width=1)
    for row in btn_rows: kb.row(*row)
    return kb

def notify_admin(text, kb=None):
    bot.send_message(ADMIN_ID, text, reply_markup=kb)

#########################
#         start         #
#########################
@bot.message_handler(commands=['start'])
def start(msg):
    kb = make_keyboard([
        [types.InlineKeyboardButton("🛒 عرض المنتجات", callback_data="show_products")],
        [types.InlineKeyboardButton("💰 تعبئة حسابي", callback_data="charge_balance")],
        [types.InlineKeyboardButton("📞 دعم البوت", callback_data="support")],
    ])
    if msg.from_user.id == ADMIN_ID:
        kb.row(types.InlineKeyboardButton("⚙️ لوحة الأدمن", callback_data="admin_panel"))
    bot.send_message(msg.chat.id, f"أهلاً <b>{msg.from_user.first_name}</b>!\nاختر من الأزرار:", reply_markup=kb)

#########################
#    عرض المنتجات       #
#########################
@bot.callback_query_handler(func=lambda c: c.data == "show_products")
def show_products(call):
    global products_cache
    products_cache = get_products()
    if not products_cache:
        bot.answer_callback_query(call.id, "لا توجد منتجات متاحة حالياً.")
        return
    kb = types.InlineKeyboardMarkup()
    for prod in products_cache:
        prc = int(prod['price']*exchange_rate*(1+profit_percent/100))
        kb.add(types.InlineKeyboardButton(f"{prod['name']} - {prc} ل.س", callback_data=f"prod_{prod['id']}"))
    bot.send_message(call.message.chat.id, "اختر المنتج:", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("prod_"))
def product_details(call):
    pid = int(call.data.split("_")[1])
    prod = find_product_by_id(pid)
    if not prod:
        bot.answer_callback_query(call.id, "المنتج غير متوفر الان")
        return
    price = int(prod['price']*exchange_rate*(1+profit_percent/100))
    txt = (f"🛒 <b>المنتج:</b> {prod['name']}\n"
           f"💸 <b>السعر:</b> {price} ل.س\n"
           f"ℹ️ {prod.get('description','')}\n")
    order_id = len(orders)+1
    kb = make_keyboard([
        [types.InlineKeyboardButton("✅ تأكيد الطلب", callback_data=f"order_yes_{pid}_{order_id}")],
        [types.InlineKeyboardButton("❌ إلغاء الطلب", callback_data=f"order_no_{order_id}")]
    ])
    bot.send_message(call.message.chat.id, txt, reply_markup=kb)

###############################
# معالجة التأكيد او الإلغاء   #
###############################
@bot.callback_query_handler(func=lambda c: c.data.startswith("order_"))
def order_action(call):
    parts = call.data.split("_")
    action = parts[1]
    if action == "yes":
        pid = int(parts[2])
        order_id = int(parts[3])
        prod = find_product_by_id(pid)
        user = get_user(call.from_user.id)
        price = int(prod['price']*exchange_rate*(1+profit_percent/100))
        if user['balance'] < price:
            bot.send_message(call.message.chat.id, "⚠️ رصيدك غير كافٍ!")
            return
        user['balance'] -= price
        order = {"id": order_id, "pid": pid, "user": call.from_user.id, "price": price, "status": "قيد التنفيذ"}
        orders.append(order)
        user['orders'].append(order_id)
        notify_admin(
            f"🔔 طلب جديد من <a href='tg://user?id={call.from_user.id}'>{call.from_user.first_name}</a>\n"
            f"طلب #{order_id}\nمنتج: {prod['name']}\nالسعر: {price} ل.س"
        )
        # مثال إرسال الطلب لـ API الموقع، عدله حسب API موقعك:
        # resp = requests.post(API_URL_ORDER, headers={"Authorization": f"Bearer {API_TOKEN}"}, json={"product_id": pid, "user_id": call.from_user.id})
        bot.send_message(call.message.chat.id, f"✅ تم تقديم طلبك رقم {order_id}. سيتم تنفيذه قريباً.")
    elif action == "no":
        order_id = int(parts[2])
        bot.send_message(call.message.chat.id, f"❌ تم إلغاء الطلب رقم {order_id}.")

#########################
#      تعبئة حسابي      #
#########################
@bot.callback_query_handler(func=lambda c: c.data == "charge_balance")
def charge_balance(call):
    kb = make_keyboard([
        [types.InlineKeyboardButton("سيريَتل كاش", callback_data="fill_syriatel")],
        [types.InlineKeyboardButton("شام كاش", callback_data="fill_shamcash")],
    ])
    bot.send_message(call.message.chat.id, "اختر طريقة الدفع:", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("fill_"))
def fill_method(call):
    if call.data == "fill_syriatel":
        msg = bot.send_message(call.message.chat.id, "أدخل المبلغ المُرسل ورقم العملية:")
        bot.register_next_step_handler(msg, handle_syriatel, call.from_user.id)
    else:
        msg = bot.send_message(call.message.chat.id, "أرسل صورة إيصال شام كاش:")
        bot.register_next_step_handler(msg, handle_shamcash, call.from_user.id)

def handle_syriatel(msg, uid):
    vals = msg.text.strip().split()
    if len(vals) < 2:
        msg2 = bot.send_message(msg.chat.id, "يرجى كتابة: [المبلغ] [رقم العملية]")
        bot.register_next_step_handler(msg2, handle_syriatel, uid)
        return
    amnt, op_id = vals[0], vals[1]
    notify_admin(
        f"💰 طلب تعبئة من <a href='tg://user?id={uid}'>{msg.from_user.first_name}</a>\n"
        f"المبلغ: {amnt}\nرقم العملية: {op_id}",
        make_keyboard([
            [types.InlineKeyboardButton("قبول", callback_data=f"approve_fill_{uid}_{amnt}")],
            [types.InlineKeyboardButton("رفض", callback_data=f"refuse_fill_{uid}")]
        ])
    )
    bot.send_message(msg.chat.id, "تم إرسال الطلب للإدارة للمراجعة.")

def handle_shamcash(msg, uid):
    if not msg.photo:
        msg2 = bot.send_message(msg.chat.id, "يجب رفع صورة الإشعار")
        bot.register_next_step_handler(msg2, handle_shamcash, uid)
        return
    file_id = msg.photo[-1].file_id
    notify_admin(
        f"💰 طلب إيداع شام كاش من <a href='tg://user?id={uid}'>{msg.from_user.first_name}</a>",
        make_keyboard([
            [types.InlineKeyboardButton("قبول", callback_data=f"approve_fill_{uid}_0")],
            [types.InlineKeyboardButton("رفض", callback_data=f"refuse_fill_{uid}")]
        ])
    )
    bot.send_photo(ADMIN_ID, file_id)
    bot.send_message(msg.chat.id, "تم إرسال الطلب للإدارة.")

@bot.callback_query_handler(func=lambda c: c.data.startswith("approve_fill_") or c.data.startswith("refuse_fill_"))
def fill_approval(call):
    parts = call.data.split("_")
    action = parts[0]
    uid = int(parts[2])
    if call.data.startswith("approve_fill_"):
        amount = int(parts[3])
        get_user(uid)['balance'] += amount
        bot.send_message(uid, f"✅ تم زيادة رصيدك بمبلغ {amount} ل.س.")
        bot.send_message(call.message.chat.id, "✔️ تمت العملية بنجاح.")
    else:
        bot.send_message(uid, "❌ تم رفض طلب التعبئة.")
        bot.send_message(call.message.chat.id, "❌ تم رفض الطلب.")

#########################
#        الدعم          #
#########################
@bot.callback_query_handler(func=lambda c: c.data == "support")
def support_info(call):
    bot.send_message(call.message.chat.id, f"للتواصل مع الدعم: {CHANNEL_SUPPORT}")

#########################
#    لوحة الأدمن        #
#########################
@bot.callback_query_handler(func=lambda c: c.data == "admin_panel" and c.from_user.id == ADMIN_ID)
def admin_panel(call):
    kb = make_keyboard([
        [types.InlineKeyboardButton("📈 إحصائيات", callback_data="stats")],
        [types.InlineKeyboardButton("👥 إحصائيات المستخدمين", callback_data="users_stats")],
        [types.InlineKeyboardButton("🔧 إدارة الإعدادات", callback_data="settings")],
        [types.InlineKeyboardButton("⬆️ تحديث المنتجات", callback_data="refresh_products")],
        [types.InlineKeyboardButton("🖼️ إدارة الصور", callback_data="images_panel")],
        [types.InlineKeyboardButton("تشغيل/إيقاف البوت", callback_data="toggle_bot")],
    ])
    bot.send_message(call.message.chat.id, "لوحة التحكم:", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "toggle_bot" and c.from_user.id == ADMIN_ID)
def toggle_bot(call):
    global bot_on
    bot_on = not bot_on
    state = "✅ مفعل" if bot_on else "⛔️ متوقف"
    bot.send_message(call.message.chat.id, f"حالة البوت الآن: {state}")

@bot.callback_query_handler(func=lambda c: c.data == "stats" and c.from_user.id == ADMIN_ID)
def show_stats(call):
    txt = (
        f"👥 عدد المستخدمين: {len(users)}\n"
        f"📦 المنتجات: {len(products_cache)}\n"
        f"📄 الطلبات: {len(orders)}"
    )
    bot.send_message(call.message.chat.id, txt)

@bot.callback_query_handler(func=lambda c: c.data == "users_stats" and c.from_user.id == ADMIN_ID)
def users_stats(call):
    for uid, info in users.items():
        kb = make_keyboard([
            [types.InlineKeyboardButton("➕ إضافة رصيد", callback_data=f"add_bal_{uid}")],
            [types.InlineKeyboardButton("➖ خصم رصيد", callback_data=f"sub_bal_{uid}")],
            [types.InlineKeyboardButton("🔄 تصفير الرصيد", callback_data=f"reset_bal_{uid}")]
        ])
        bot.send_message(call.message.chat.id, f"مستخدم: {uid}\nالرصيد: {info['balance']}", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("add_bal_") and c.from_user.id == ADMIN_ID)
def add_balance(call):
    uid = int(call.data.split("_")[2])
    msg = bot.send_message(call.message.chat.id, "أدخل قيمة الزيادة:")
    bot.register_next_step_handler(msg, lambda m: perform_add_bal(m, uid))

def perform_add_bal(msg, uid):
    try:
        amount = int(msg.text)
        get_user(uid)['balance'] += amount
        bot.send_message(msg.chat.id, f"تمت زيادة رصيد المستخدم ({uid}) بمقدار {amount}")
        bot.send_message(uid, f"تمت زيادة رصيدك بمقدار {amount} ل.س من الأدمن.")
    except:
        bot.send_message(msg.chat.id, "يرجى إدخال رقم صحيح!")

@bot.callback_query_handler(func=lambda c: c.data.startswith("sub_bal_") and c.from_user.id == ADMIN_ID)
def sub_balance(call):
    uid = int(call.data.split("_")[2])
    msg = bot.send_message(call.message.chat.id, "أدخل قيمة الخصم:")
    bot.register_next_step_handler(msg, lambda m: perform_sub_bal(m, uid))

def perform_sub_bal(msg, uid):
    try:
        amount = int(msg.text)
        get_user(uid)['balance'] -= amount
        bot.send_message(msg.chat.id, f"تم خصم {amount} من رصيد المستخدم ({uid}).")
        bot.send_message(uid, f"تم خصم {amount} ل.س من رصيدك من الأدمن.")
    except:
        bot.send_message(msg.chat.id, "يرجى إدخال رقم صحيح!")

@bot.callback_query_handler(func=lambda c: c.data.startswith("reset_bal_") and c.from_user.id == ADMIN_ID)
def reset_balance(call):
    uid = int(call.data.split("_")[2])
    get_user(uid)['balance'] = 0
    bot.send_message(call.message.chat.id, f"تم تصفير رصيد المستخدم ({uid}).")
    bot.send_message(uid, "رصيدك تم تصفيره من الأدمن.")

@bot.callback_query_handler(func=lambda c: c.data == "settings" and c.from_user.id == ADMIN_ID)
def show_settings(call):
    kb = make_keyboard([
        [types.InlineKeyboardButton("تعيين سعر الصرف", callback_data="set_rate")],
        [types.InlineKeyboardButton("تعديل نسبة الربح", callback_data="set_profit")],
        [types.InlineKeyboardButton("إعداد API", callback_data="edit_api")],
    ])
    bot.send_message(call.message.chat.id, "إدارة الإعدادات:", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "set_rate" and c.from_user.id == ADMIN_ID)
def set_rate(call):
    msg = bot.send_message(call.message.chat.id, "أدخل سعر الصرف الجديد:")
    bot.register_next_step_handler(msg, perform_set_rate)

def perform_set_rate(msg):
    global exchange_rate
    try:
        exchange_rate = float(msg.text)
        bot.send_message(msg.chat.id, f"تم تحديث سعر الصرف إلى: {exchange_rate}")
    except:
        bot.send_message(msg.chat.id, "يرجى إدخال رقم صحيح!")

@bot.callback_query_handler(func=lambda c: c.data == "set_profit" and c.from_user.id == ADMIN_ID)
def set_profit(call):
    msg = bot.send_message(call.message.chat.id, "أدخل نسبة الربح الجديدة:")
    bot.register_next_step_handler(msg, perform_set_profit)

def perform_set_profit(msg):
    global profit_percent
    try:
        profit_percent = int(msg.text)
        bot.send_message(msg.chat.id, f"تم تحديث نسبة الربح إلى: {profit_percent}%")
    except:
        bot.send_message(msg.chat.id, "يرجى إدخال رقم صحيح!")

@bot.callback_query_handler(func=lambda c: c.data == "refresh_products" and c.from_user.id == ADMIN_ID)
def refresh_products(call):
    # مثال لتحديث المنتجات من API
    try:
        resp = requests.post(API_URL_UPDATE, headers={'Authorization': f"Bearer {API_TOKEN}"})
        if resp.ok:
            bot.send_message(call.message.chat.id, "تم تحديث المنتجات بنجاح!")
        else:
            bot.send_message(call.message.chat.id, "حدث خطأ أثناء تحديث المنتجات.")
    except Exception as e:
        bot.send_message(call.message.chat.id, "فشل الاتصال بـ API")

@bot.callback_query_handler(func=lambda c: c.data == "images_panel" and c.from_user.id == ADMIN_ID)
def images_panel(call):
    bot.send_message(call.message.chat.id, "إدارة الصور وإضافة صور للأقسام والمنتجات: (تخصيص لاحق)")

@bot.callback_query_handler(func=lambda c: c.data == "edit_api" and c.from_user.id == ADMIN_ID)
def edit_api(call):
    bot.send_message(call.message.chat.id, "تعديل معلومات API وتحميل ملفات: (تخصيص لاحق)")

############################
#     فلترة البوت في حال إيقافه
############################
@bot.message_handler(func=lambda message: not bot_on and message.from_user.id != ADMIN_ID)
def bot_off(msg):
    bot.reply_to(msg, "البوت متوقف حالياً، راجع الأدمن.")

############################
#         run
############################
print("Bot is running ...")
bot.infinity_polling()