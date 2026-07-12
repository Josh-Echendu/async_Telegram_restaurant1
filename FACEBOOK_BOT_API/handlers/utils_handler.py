from FACEBOOK_BOT_API.core.config import _request_with_retry


async def send_button_message(recipient_id, text, access_token, buttons=None):

    payload = {
        "recipient": {
            "id": recipient_id,
        },
        "messaging_type": "RESPONSE",
        "message": {
            "attachment": {
                "type": "template",
                "payload": {
                    "template_type": "button",
                    "text": text,
                    "buttons": buttons or [],
                },
            }
        },
    }

    response, success = await _request_with_retry(
        method="POST",
        url="https://graph.facebook.com/v23.0/me/messages",
        params={
            "access_token": access_token,
        },
        json=payload,
    )

    return response, success
