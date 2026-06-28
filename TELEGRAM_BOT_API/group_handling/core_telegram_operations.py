from config import *
from helper import make_api_request

async def establish_bot_contact(bot_username: str) -> Dict[str, Any]:

    """
    Establish mutual contact betweSen admin account and bot
    Required before adding bot to groups
    
    Args:
        bot_username: Username of the bot (with @)
    
    Returns:
        Response from API
    """
    logger.info(f"Establishing contact with {bot_username}")
    
    payload = {
        'user_id': CONFIG['ADMIN_USER_ID'],
        "target": bot_username,
        "message": "/start"
    }

    response =  await make_api_request("POST", "/send_message", payload)

    # Wait for Telegram to process
    await asyncio.sleep(CONFIG['RATE_LIMIT_DELAY'])

    logger.info(f"✅ Contact established with {bot_username}")
    return response


async def create_telegram_group(group_name: str, description: str = "") -> Dict[str, Any]:
    
    """
    Create a new Telegram supergroup
    
    Args:
        group_name: Name of the group
        description: Group description
    
    Returns:
        Group details including group_id
    """
    logger.info(f"Creating group: {group_name}")

    payload = {
        "title": group_name,
        "about": description
    }

    response = await make_api_request("POST", "/create_supergroup", payload)

    # Rate Limiting
    await asyncio.sleep(CONFIG['RATE_LIMIT_DELAY'])

    logger.info(f"✅ Group created: {response.get('groupid')}")
    return response



async def add_member_to_group(group_id: int, member_id: str) -> Dict[str, Any]:
    """
    Add a member (user or bot) to a group
    
    Args:
        group_id: Telegram group ID
        member_id: Username or ID of member to add
    
    Returns:
        API response
    """
    logger.info(f"Adding {member_id} to group {group_id}")
    

    payload = {
        "group_id": group_id,
        "user_ids": [member_id]
    }

    response = await make_api_request("POST", "/add_chat_members", payload)

    await asyncio.sleep(CONFIG["RATE_LIMIT_DELAY"])
    
    logger.info(f"✅ Added {member_id} to group")
    return response


async def promote_to_admin(
    group_id: int,
    member_id: str,
    permissions: Dict[str, bool] = None
) -> Dict[str, Any]:
    
    """
    Promote a member to admin with specified permissions
    
    Args:
        group_id: Telegram group ID
        member_id: Username or ID of member
        permissions: Dictionary of admin permissions
    
    Returns:
        API response
    """

    logger.info(f"Promoting {member_id} to admin in group {group_id}")

    # Default permissions for a restaurant bot
    default_permissions = {
        "can_change_info": False,
        "can_post_messages": False,
        "can_edit_messages": False,
        "can_delete_messages": True,
        "can_restrict_members": False,
        "can_invite_users": True,
        "can_pin_messages": True,
        "can_promote_members": False
    }

    permissions = permissions or default_permissions

    payload = {
        "group_id": group_id,
        "user_id": member_id,
        **permissions
    }

    response = await make_api_request("POST", "/promote_chat_member", payload)
    
    await asyncio.sleep(CONFIG["RATE_LIMIT_DELAY"])
    
    logger.info(f"✅ {member_id} promoted to admin")
    return response


async def send_test_message(group_id: int, message: str) -> Dict[str, Any]:
    """
    Send a test message to verify setup
    
    Args:
        group_id: Telegram group ID
        message: Test message content
    
    Returns:
        API response
    """
    logger.info(f"Sending test message to group {group_id}")
    
    payload = {
        "chat_id": group_id,
        "text": message
    }
    
    response = await make_api_request("POST", "/send_message", payload)
    
    logger.info(f"✅ Test message sent")
    return response


async def leave_group(group_id: int) -> Dict[str, Any]:
    """
    Make admin account leave the group
    
    Args:
        group_id: Telegram group ID
    
    Returns:
        API response
    """
    logger.info(f"Admin leaving group {group_id}")
    
    payload = {"chat_id": group_id}
    response = await make_api_request("POST", "/leave_chat", payload)
    
    logger.info(f"✅ Admin left group {group_id}")
    return response