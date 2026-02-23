# handlers/echo_handler.py - EXACT COPY FROM ORIGINAL FILE
from .kitchen_handler import api_get_user_order_batches
from config import *
from utils.cart_utils import *
from utils.image_utils import *
from .payment_handler import pay_now
from .start_handler import start
from .order_handler import order_meal
from decimal import Decimal


async def debug_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):

    # always turn off privacy with /setprivacy so bot can receive all messages sent to group
    print("CHAT ID:", update.effective_chat.id)
    print("CHAT TYPE:", update.effective_chat.type)
    print("CHAT:", update)    

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    telegram_id = update.effective_user.id

    checkout_msg_id = await redis_client.get(f"user:{telegram_id}:checkout_message_id")
    send_to_kitchen_id = await redis_client.get(f"user:{telegram_id}:send_to_kitchen_id")

    print("checkout_msg_id: ", checkout_msg_id)
    print("send_to_kitchen_id: ", send_to_kitchen_id)
    
    if checkout_msg_id:
        try:
            await context.bot.edit_message_reply_markup(
                chat_id=update.effective_chat.id,
                message_id=checkout_msg_id,
                reply_markup=None
            )
        except: pass
        finally: await redis_client.delete(f"user:{telegram_id}:checkout_message_id")

    if send_to_kitchen_id:
        try: 
            await context.bot.edit_message_text(
                text='🍽️ Order sent to the kitchen! 🎉🎉🎉',
                chat_id=update.effective_chat.id,
                message_id=send_to_kitchen_id, 
                reply_markup=None
            )
        except: pass
        finally: await redis_client.delete(f"user:{telegram_id}:send_to_kitchen_id")

    if text == "🍽 Order Food":
        await order_meal(update, context)

    elif text == "📦 Track Order":
        await update.message.reply_text("Coming soon 😊.")
    
    elif text == "📞 Contact Staff":
        first_name = update.effective_chat.first_name
        await update.message.reply_text(f"Good day {first_name} 😊, to contact us you call us on \n\n CONTACT: +234 906 393 8743.")

    elif text == "ℹ️ Help":
        await update.message.reply_text("You have chosen to get help.")
    
    elif text == "⬅️ Back":
        meal_type = await redis_client.get(f"user:{telegram_id}:meal_type")
        more_menu = await redis_client.get(f"user:{telegram_id}:more_menu")
        print("more_menu in back button: ", more_menu)
        
        # if there is a meal_type in user_data, go back to meal ordering menu
        if meal_type:
            await Extract_message_img_ids(update, context)
            await order_meal(update, context)
            return
        
        if more_menu:
            await redis_client.delete(f"user:{telegram_id}:more_menu")
            await order_meal(update, context)
            return

        await start(update, context)

    elif text == "🍚 🍚 🍚Affordable Meals":
        await echo_orders(update, context, category='affordable_meal')

    elif text == "🍗🍗Spiced Fried Chicken":
        await echo_orders(update, context, category='spiced_chicken')  

    elif text == "🍗Flamed Grilled Chicken":
        await echo_orders(update, context, category='flamed_grilled_chicken')  

    elif text == "🥗🍔🍗🍟🥓 Snacks":
        await echo_orders(update, context, category='burgers_wraps_chickwizz')  

    elif text == "🥤🍾🍷 Drinks / Beverages":
        await echo_orders(update, context, category='beverages')  
    
    elif text == "🍗🍗 Rotisserie Chicken":
        await echo_orders(update, context, category='rotisserie_chicken')  
        
    elif text == "🍗🍝 🍜Tasty Sides":
        await echo_orders(update, context, category='tasty_sides')  
        
    elif text == "➡️ More":
        await redis_client.set(f"user:{telegram_id}:more_menu", "more")
        await more_menu_func(update, context)
        
    elif text == "🛍️✅💳 Checkout/Pay":
        active_cart = await get_cart_items(update)
        
        # 1️⃣ Try paying for current cart if not empty
        if active_cart:
            await checkout_pay(update, context)
            return
        
        # 2️⃣ If cart empty, but last_order exists (sent to kitchen), allow paying it
        orders_batches = await api_get_user_order_batches(update)
        if orders_batches:
            await Extract_message_img_ids(update, context)
            copy_order_batches = orders_batches.copy()
            print("copy_order_batches: ", copy_order_batches)
            await pay_now(update, context, copy_order_batches)
            return
        
        # 3️⃣ Otherwise, truly empty cart and no order_batches
        await Extract_message_img_ids(update, context)
        await update.message.reply_text("🛒 Your cart is empty.\nPlease add items before paying.")
        await order_meal(update, context)
        
    elif text == "🛒💚 View Cart":
        meal_type = await redis_client.get(f"user:{telegram_id}:meal_type")
        
        if not meal_type:
            return 
        
        # Exract active cart items from API
        active_cart = await get_cart_items(update)    
        print("active_cart in view cart: ", active_cart) 

        if not active_cart:
           
            await Extract_message_img_ids(update, context)

            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="You have no cart items!"
            )
            
            # Go back to meal category
            await order_meal(update, context)
            return
        
        await Extract_message_img_ids(update, context)
        await show_cart_items(update, context, active_cart, meal_type)


async def echo_orders(update: Update, context: ContextTypes.DEFAULT_TYPE, category):
    telegram_id = update.effective_user.id

    # delete old meal_type
    await redis_client.delete(f"user:{telegram_id}:meal_type")

    # store the actual category
    await redis_client.set(f"user:{telegram_id}:meal_type", category)
    mtype = await redis_client.get(f"user:{telegram_id}:meal_type")
    print("mtype: ", mtype)

    # use category directly (NOT the return value of set)
    await redis_client.set(f"user:{telegram_id}:{category}_page", 0)

    await cart_checkout(update, context)

    # show meal images
    await meal_images(update, context)



async def show_cart_items(update: Update, context: ContextTypes.DEFAULT_TYPE, active_cart, meal_type):
    print("active_cart in show_cart_items: ", active_cart)
    NGROK_URL="https://3748-197-211-63-122.ngrok-free.app"
    
    # send product images
    for p in active_cart:
        product_id = p.get('product_id')
        print("product_id in show_cart_items:", product_id)
        product_name = p.get('product_title')
        price_per_item = p.get('product_price')
        qty = p.get("quantity")
        image_url = p.get('product_image').replace("http://web:8000", NGROK_URL)
        
        total_price = p.get('total_price', price_per_item * qty)
        caption = f"{product_name} - ₦{price_per_item:,} \nQty: {qty} | Total: ₦{total_price:,}"
        
        keyboard = [
            [
                InlineKeyboardButton("🛒💚🛍️", callback_data=f"add_{product_id}"),
                InlineKeyboardButton(f"⚖️ {qty}", callback_data="noop"),
                InlineKeyboardButton("⛔🛍️", callback_data=f"remove_{product_id}"),
            ]
        ]

        send_msg = await context.bot.send_photo(
            chat_id=update.effective_chat.id,
            photo=image_url,
            caption=caption,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        await store_message_id(update, context, send_msg.message_id)