from FACEBOOK_BOT_API.core.config import *
from FACEBOOK_BOT_API.handlers.echo_handler import echo
from FACEBOOK_BOT_API.handlers.button_handler import handle_postback



async def dispatch_event(event, restaurant):

    # Persistent menu / Get Started / Button template
    if "postback" in event:
        await handle_postback(event, restaurant)
        return

    if "message" in event:

        # # Image, video, location...
        # if "attachments" in event["message"]:
        #     await handle_attachments(event, restaurant)
        #     return

        # Plain text
        if "text" in event["message"]:
            await echo(event, restaurant)
            return
