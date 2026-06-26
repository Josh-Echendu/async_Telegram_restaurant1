import asyncio
from pydoll.browser import Chrome
from pydoll.constants import By
from pydoll.commands.network_commands import NetworkCommands
import aiofiles
from pydoll.browser.options import ChromiumOptions

import json
from pydoll.commands.dom_commands import DomCommands
import glob
import os
from functools import partial
from pydoll.exceptions import ElementNotFound




async def create_bot(task, tab):

    message_input_xpath = "//div[@id='editable-message-text']"
    message_arrow_xpath = "//i[@class='icon icon-check']"

    bot_name = task.get('bot_name')
    bot_user_name = task.get('bot_user_name')

    # -------------------------
    # STEP 1: /newbot
    # -------------------------
    await safe_click(tab, message_input_xpath, timeout=120)
    await safe_type(tab, message_input_xpath, '/newbot', timeout=120)
    await safe_click(tab, message_arrow_xpath, timeout=120)
    print("typed /newbot")



    # -------------------------
    # STEP 2: BOT NAME
    # -------------------------

    await safe_click(tab, message_input_xpath, timeout=120)
    await safe_type(tab, message_input_xpath, bot_name, timeout=120)
    await safe_click(tab, message_arrow_xpath, timeout=120)

    for i in range(10):

        messages = await tab.find_or_wait_element(By.XPATH, "//div[contains(@class,'text-content')]", find_all=True)
        latest_message = messages[-1]
        name_message = await latest_message.text
        name_message_text = name_message.lower()

        print("name message text:", name_message_text)

        # Telegram usually replies asking for username next
        if "good" in name_message_text or "username" in name_message_text:
            break

        if i == 9:
            return False
        
        await asyncio.sleep(1)

    # -------------------------
    # STEP 3: BOT USERNAME
    # -------------------------

    await safe_click(tab, message_input_xpath, timeout=120)
    await safe_type(tab, message_input_xpath, bot_user_name, timeout=120)
    await safe_click(tab, message_arrow_xpath, timeout=120)

    for i in range(10):

        messages = await tab.find_or_wait_element(By.XPATH, "//div[contains(@class,'text-content')]", find_all=True)
        latest_message = messages[-1]
        username_message = await latest_message.text
        username_message_text = username_message.lower()

        print("username message text:", username_message_text)

        # ❌ username already taken
        if "sorry" in username_message_text:
            return False, "Bot username already exists"

        # 🎯 SUCCESS CONDITION (BotFather confirmation)
        if "use this token to access the http api" in username_message_text or "done" in username_message_text or 'congratulations' in username_message_text:

            token_from_code = await safe_text(tab, "//code[contains(@class, 'text-entity-code')]", 120)

            if token_from_code:
                return token_from_code

            # fallback regex (just in case UI fails)
            token_from_text = await extract_token(username_message_text)
            if token_from_text:
                return token_from_text

        if i == 9:
            return False
        
        await asyncio.sleep(2)

    return False


async def extract_token(message): 

    import re 
    """ 
    Done! Congratulations on your new bot.
    Use this token to access the HTTP API:
    8545999939:AAEqYejtJIhj6SfxXxoy7LYrpllkLB4pqWo 
    Keep your token secure and store it safely. 
    """ 

    match = re.search(r"\d+:[A-Za-z0-9_-]{35,}", message)
    if match: 
        token = match.group() 
        print(token) 
        return token 
    return None 



async def safe_click(tab, xpath, timeout=60):
    try:
        element = await tab.find_or_wait_element(By.XPATH, xpath, timeout=timeout)
        await asyncio.sleep(1)
        await element.scroll_into_view()
        await asyncio.sleep(1)
        await element.click()

        return element

    except Exception as e:
        print(f"Could not click: {xpath}")
        print(e)
        return False


async def safe_type(tab, xpath, text, timeout=60):
    element = await tab.find_or_wait_element(By.XPATH, xpath, timeout=timeout)
    await asyncio.sleep(1)
    await element.scroll_into_view()
    await element.click()
    await element.type_text(text)
    return element


async def safe_text(tab, xpath, timeout=60):
    try: 
        element = await tab.find_or_wait_element(By.XPATH, xpath, timeout=timeout) 
        await asyncio.sleep(1) 
        await element.scroll_into_view() 
        message_text = await element.text
        return message_text
    
    except Exception as e:
        print('couldnt find text') 
        return False

async def is_logged_in(tab):
    try:
        await tab.find_or_wait_element(
            By.XPATH,
            "//input[@id='telegram-search-input']",
            timeout=15
        )
        return True
    except:
        return False


async def main():
    options = ChromiumOptions()

    print("Working directory:", os.getcwd())
    print("Profile path:", os.path.abspath("./telegram_persistent_profile"))
    session_folder = os.path.abspath(r'C:\Users\Admin\Music\async_Telegram_restaurant\PYDOLL_TELEGRAM_WEB_AUTOMATION\web_automation\telegram_persistent_profile')
    os.makedirs(session_folder, exist_ok=True)
    
    options.binary_location = r"C:\Users\Admin\AppData\Local\Google\Chrome\Application\chrome.exe"
    options.add_argument(f"--user-data-dir={session_folder}")


    async with Chrome(options=options) as browser:
        tab = await browser.start()

        await browser.set_window_maximized()

        await tab.go_to("https://web.telegram.org/a/", timeout=120)
        print("Telegram loaded")

        logged_in = await is_logged_in(tab)

        # 🔥 CASE 1: already logged in
        if logged_in:
            print("Already logged in — skipping login flow")
        
        else:
            print("Not logged in — running login flow")

            # 1. Click login by phone
            await safe_click(tab, "//button[contains(., 'Log in by phone')]", timeout=120)
            print("Clicked login by phone")

            # 2. Open country selector
            await safe_click(tab, "//input[@id='sign-in-phone-code']", timeout=120)
            print("Opened country selector")

            # 3. Select Nigeria
            await safe_type(tab, "//input[@id='sign-in-phone-code']", "NNigeria", timeout=60)

            await asyncio.sleep(2)

            await safe_click(tab, "//div[@role='menuitem']", timeout=60)
            print("Selected Nigeria")

            # 4. Enter phone number
            await safe_type(tab, "//input[@id='sign-in-phone-number']", "XXXXXXXXXXX", timeout=120)
            print("Entered phone number")

            # 5. Click Next
            await safe_click(tab, "//button[contains(., 'Next')]", timeout=120)
            print("Clicked Next")

        # ✔ NOW SAFE TO USE TELEGRAM UI
        await safe_click(tab, "//input[@id='telegram-search-input']", timeout=120)
        print("search clicked icon")
        
        # 7. Type @BotFather
        await safe_type(tab, "//input[@id='telegram-search-input']", text="@BotFather", timeout=120)
        print("typed @BotFather")
        await asyncio.sleep(3)

        # 8. pick the @BotFather account
        await safe_click(tab, "(//div[contains(@class,'info')]//h3[normalize-space()='BotFather'])[2]", timeout=15)
        print("clicked @BotFather account")

        start_button = await safe_click(tab, "//button[normalize-space()='START']", timeout=15)
        print("click start button")

        if not start_button:
            await safe_click(tab, "//div[@id='editable-message-text']", timeout=120)
            await safe_type(tab, "//div[@id='editable-message-text']", "/start")
            await safe_click(tab, "//i[@class='icon icon-check']", timeout=120)
            print("typed /start now")
        
        user_data = {
            "bot_name": "hungryfoods",
            "bot_user_name": "hungry123456789_bot",
            "about_text": "i just wanna be the greatest soccer analyst"
            }
        token = await create_bot(user_data, tab)
        print("token: ", token)

        set_about = await set_about_text(user_data, tab)

        await asyncio.sleep(60)

        await tab.close()


asyncio.run(main())



async def safe_hover(tab, xpath, timeout=60):
    element =  await tab.find_or_wait_element(By.XPATH, xpath, timeout=timeout)
    await element.hover_element()
    return


async def set_about_text(task, tab):
    message_input_xpath = "//div[@id='editable-message-text']"
    message_arrow_xpath = "//i[@class='icon icon-check']"

    bot_about_text = task.get('about_text')
    bot_user_name = task.get("bot_user_name")

    # -------------------------
    # STEP 1: /setabouttext
    # -------------------------
    await safe_click(tab, message_input_xpath, timeout=120)
    await safe_type(tab, message_input_xpath, '/setabouttext', timeout=120)
    await safe_click(tab, message_arrow_xpath, timeout=120)
    print("typed /setabouttext ")

    await safe_hover(tab, "//i[@class='icon icon-bot-command']", 120)
    await safe_click(tab, f"//button/span[normalize-space()='{bot_user_name}']", 120)

    for i in range(10):

        messages = await tab.find_or_wait_element(By.XPATH, "//div[contains(@class,'text-content')]", find_all=True)
        latest_message = messages[-1]
        set_about_text_preview = await latest_message.text
        set_about_text_preview = set_about_text_preview.lower()

        print("about message text:", set_about_text_preview)

        if 'send' in set_about_text_preview or "profile" in set_about_text_preview or "people" in set_about_text_preview:
            
            await safe_click(tab, message_input_xpath, timeout=120)
            await safe_type(tab, message_input_xpath, bot_about_text, timeout=120)
            await safe_click(tab, message_arrow_xpath, timeout=120)
        
        else:
            if i == 9:
                return False, "couldnt update about text"

    for i in range(10):

        messages = await tab.find_or_wait_element(By.XPATH, "//div[contains(@class,'text-content')]", find_all=True)
        latest_message = messages[-1]
        set_about_text_response= await latest_message.text
        set_about_text_response = set_about_text_response.lower()

        print("username message text:", set_about_text_response)

        if 'success' in set_about_text_response or "updated" in set_about_text_response:
            print("already updated the about text")
            return True, "already updated"
            

























# import asyncio
# from pydoll.browser import Chrome
# from pydoll.constants import By
# from pydoll.commands.network_commands import NetworkCommands
# import aiofiles
# from pydoll.browser.options import ChromiumOptions

# import json
# from pydoll.commands.dom_commands import DomCommands
# import glob
# import os
# from functools import partial
# from pydoll.exceptions import ElementNotFound


# async def safe_click(tab, xpath, timeout=60):
#     try:
#         element = await tab.find_or_wait_element(By.XPATH, xpath, timeout=timeout)
#         await asyncio.sleep(1)
#         await element.scroll_into_view()
#         await asyncio.sleep(1)
#         await element.click()

#         return element

#     except Exception as e:
#         print(f"Could not click: {xpath}")
#         print(e)
#         return False


# async def safe_type(tab, xpath, text, timeout=60):
#     element = await tab.find_or_wait_element(By.XPATH, xpath, timeout=timeout)
#     await asyncio.sleep(1)
#     await element.scroll_into_view()
#     await element.click()
#     await element.type_text(text)
#     return element


# async def is_logged_in(tab):
#     try:
#         await tab.find_or_wait_element(
#             By.XPATH,
#             "//input[@id='telegram-search-input']",
#             timeout=15
#         )
#         return True
#     except:
#         return False


# async def main():
#     options = ChromiumOptions()

#     print("Working directory:", os.getcwd())
#     print("Profile path:", os.path.abspath("./telegram_persistent_profile"))
#     session_folder = os.path.abspath(r'C:\Users\Admin\Music\async_Telegram_restaurant\PYDOLL_TELEGRAM_WEB_AUTOMATION\web_automation\telegram_persistent_profile')
#     os.makedirs(session_folder, exist_ok=True)
    
#     options.binary_location = r"C:\Users\Admin\AppData\Local\Google\Chrome\Application\chrome.exe"
#     options.add_argument(f"--user-data-dir={session_folder}")


#     async with Chrome(options=options) as browser:
#         tab = await browser.start()

#         await browser.set_window_maximized()

#         await tab.go_to("https://web.telegram.org/a/", timeout=120)
#         print("Telegram loaded")

#         logged_in = await is_logged_in(tab)

#         # 🔥 CASE 1: already logged in
#         if logged_in:
#             print("Already logged in — skipping login flow")
        
#         else:
#             print("Not logged in — running login flow")

#             # 1. Click login by phone
#             await safe_click(tab, "//button[contains(., 'Log in by phone')]", timeout=120)
#             print("Clicked login by phone")

#             # 2. Open country selector
#             await safe_click(tab, "//input[@id='sign-in-phone-code']", timeout=120)
#             print("Opened country selector")

#             # 3. Select Nigeria
#             await safe_type(tab, "//input[@id='sign-in-phone-code']", "NNigeria", timeout=60)

#             await asyncio.sleep(2)

#             await safe_click(tab, "//div[@role='menuitem']", timeout=60)
#             print("Selected Nigeria")

#             # 4. Enter phone number
#             await safe_type(tab, "//input[@id='sign-in-phone-number']", "9131634156", timeout=120)
#             print("Entered phone number")

#             # 5. Click Next
#             await safe_click(tab, "//button[contains(., 'Next')]", timeout=120)
#             print("Clicked Next")

#         # ✔ NOW SAFE TO USE TELEGRAM UI
#         await safe_click(tab, "//input[@id='telegram-search-input']", timeout=120)
#         print("search clicked icon")
        
#         # 7. Type @BotFather
#         await safe_type(tab, "//input[@id='telegram-search-input']", text="@BotFather", timeout=120)
#         print("typed @BotFather")
#         await asyncio.sleep(3)

#         # 8. pick the @BotFather account
#         await safe_click(tab, "//span[normalize-space()='BotFather']", timeout=120)
#         print("clicked @BotFather account")

#         start_button = await safe_click(tab, "//button[normalize-space()='START']", timeout=15)
#         print("click start button")

#         if not start_button:
#             await safe_click(tab, "//div[@id='editable-message-text']", timeout=120)
#             await safe_type(tab, "//div[@id='editable-message-text']", "/start")
#             await safe_type(tab, "//i[@class='icon icon-check']", "/start")
#             print("typed /start now")



#         await asyncio.sleep(60)

#         await tab.close()


# asyncio.run(main())