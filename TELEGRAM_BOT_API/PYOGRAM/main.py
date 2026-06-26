from .operations import (
    establish_bot_contact, create_telegram_group, add_member_to_group,
    promote_to_admin, send_test_message, leave_group
)
from .config_file import logger
from datetime import datetime
from typing import Dict, Any


async def setup_restaurant_telegram(
    restaurant_name: str, 
    bot_username: str, 
    owner_telegram_id: str, 
    owner_name: str = "Restaurant Owner"
) -> Dict[str, Any]:
    """
    Complete setup for a restaurant's Telegram group using Pyrogram
    """
    
    try:
        # Step 1: Establish contact with bot (required before adding to groups)
        await establish_bot_contact(bot_username)

        # Step 2: Create the group
        group_name = f"{restaurant_name} - Orders"
        group_description = f"Order Notifications for {restaurant_name}"

        group = await create_telegram_group(group_name, group_description)
        group_id = group.get('groupid')

        if not group_id:
            raise ValueError(f"Failed to get group ID from response: {group}")
        
        # Step 3: Add the bot to the group
        await add_member_to_group(group_id, bot_username)
        
        # Step 4: Promote bot to admin
        await promote_to_admin(group_id, bot_username)

        # Step 5: Add restaurant owner
        await add_member_to_group(group_id, owner_telegram_id)

        # Step 6: Promote owner to admin
        owner_permissions = {
            "can_send_messages": True,
            "can_delete_messages": True,
            "can_manage_chat": True,
            "can_invite_users": True,
            "can_restrict_members": True,
            "can_pin_messages": True,
            "can_promote_members": False
        }

        await promote_to_admin(group_id, owner_telegram_id, owner_permissions)
        
        # Step 7: Send welcome message
        welcome_message = (
            f"🎉 Welcome to {restaurant_name} Order System!\n\n"
            f"📌 This group will receive all incoming orders.\n"
            f"🤖 Bot: {bot_username} will post all orders here.\n"
            f"👤 Owner: {owner_name} is also an admin.\n\n"
            f"✅ Setup completed on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        await send_test_message(group_id, welcome_message)

        # Step 8: Admin leaves the group
        await leave_group(group_id)

        result = {
            "success": True,
            "restaurant_name": restaurant_name,
            "group_id": group_id,
            "group_name": group_name,
            "bot_username": bot_username,
            "owner_telegram_id": owner_telegram_id,
            "setup_completed_at": datetime.now().isoformat(),
            "message": f"✅ Successfully set up Telegram group for {restaurant_name}"
        }
        
        logger.info(f"✅ Setup complete for {restaurant_name}: Group ID {group_id}")
        return result
        
    except Exception as e:
        logger.error(f"❌ Setup failed for {restaurant_name}: {e}")
        
        # if 'group_id' in locals(): checks if the variable group_id exists in the current scope. 
        # Try to clean up if group was created
        if 'group_id' in locals() and group_id: 
            try:
                await leave_group(group_id)
                logger.info(f"Cleaned up group {group_id}")
            except:
                pass
        
        raise Exception(f"Telegram setup failed for {restaurant_name}: {str(e)}")