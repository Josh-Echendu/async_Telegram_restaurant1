from .operations import (
    establish_bot_contact, create_telegram_group, add_member_to_group,
    promote_to_admin, send_test_message, leave_group
)
from .config_file import logger, ADMIN_USER_ID
from datetime import datetime
from typing import Dict, Any


async def helpers_func(group_id, group, bot_username, owner_telegram_id, restaurant_name, owner_name, service_mode):
    try:
        if not group_id:
            logger.error(f"Invalid group_id: {group}")
            return False

        logger.info(f"🔧 Setting up group {group_id} for {restaurant_name}")

        # Add the bot to the group
        await add_member_to_group(group_id, bot_username)
        logger.info(f"✅ Bot {bot_username} added to group")

        # Add restaurant owner
        await add_member_to_group(group_id, owner_telegram_id)
        logger.info(f"✅ Owner {owner_telegram_id} added to group")

        # Promote YOURSELF (anonymous)
        await promote_to_admin(group_id, int(ADMIN_USER_ID), is_hidden=True)
        logger.info(f"✅ You promoted to admin (hidden)")

        # Promote BOT (visible)
        await promote_to_admin(group_id, bot_username, is_hidden=False)
        logger.info(f"✅ Bot promoted to admin")

        # Promote RESTAURANT OWNER (visible)
        await promote_to_admin(group_id, owner_telegram_id, is_hidden=False)
        logger.info(f"✅ Owner promoted to admin")

        # Send welcome message
        welcome_message = (
            f"🎉 Welcome to {restaurant_name} {service_mode} Order System!\n\n"
            f"📌 This group will receive all incoming {service_mode} orders.\n"
            f"🤖 Bot: {bot_username} will post all {service_mode} orders here.\n"
            f"👤 Owner: {owner_name} is also an admin.\n\n"
            f"✅ Setup completed on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        await send_test_message(group_id, welcome_message)
        logger.info(f"✅ Welcome message sent")

        return True

    except Exception as e:
        logger.error(f"❌ helpers_func failed for group {group_id}: {e}")
        return False

async def setup_restaurant_telegram(
    restaurant_name: str, 
    bot_username: str, 
    owner_telegram_id: str, 
    service_mode: str,
    owner_name: str = "Restaurant Owner",
) -> Dict[str, Any]:
    """
    Complete setup for a restaurant's Telegram group using Pyrogram
    """
    
    try:
        # Step 1: Establish contact with bot (required before adding to groups)
        await establish_bot_contact(bot_username)

        # Step 2: Create the group
        dine_in_group_name=None
        delivery_group_name=None
        group_description=None
        dine_in_group_id=None
        delivery_group_id=None

        if service_mode in ['dine_in', 'both']:
            dine_in_group_name = f"{restaurant_name} Dine-In - Orders"
            group_description = f"Dine-in Order Notifications for {restaurant_name}"
            
            dine_in_group = await create_telegram_group(dine_in_group_name, group_description)
            dine_in_group_id = dine_in_group.get('groupid')
            created = await helpers_func(
                group_id=dine_in_group_id, group=dine_in_group,
                bot_username=bot_username, owner_telegram_id=owner_telegram_id,
                restaurant_name=restaurant_name, owner_name=owner_name, service_mode='Dine-in'
            )
            if not created:
                raise Exception(f"Failed to create Dine-in Group '{dine_in_group_name}' for {restaurant_name}")

        if service_mode in ['delivery', 'both']:
            delivery_group_name = f"{restaurant_name} Delivery - Orders"
            group_description = f"Delivery Order Notifications for {restaurant_name}"
            
            delivery_group = await create_telegram_group(delivery_group_name, group_description)
            delivery_group_id = delivery_group.get('groupid')

            created = await helpers_func(
                group_id=delivery_group_id, group=delivery_group,
                bot_username=bot_username, owner_telegram_id=owner_telegram_id,
                restaurant_name=restaurant_name, owner_name=owner_name, service_mode='Delivery'
            )
            if not created:
                raise Exception(f"Failed to create Delivery Group '{delivery_group_name}' for {restaurant_name}")

        result = {
            "success": True,
            "restaurant_name": restaurant_name,
            "dine_in_group_id": dine_in_group_id,
            "delivery_group_id": delivery_group_id,
            "dine_in_group_name": dine_in_group_name,
            "delivery_group_name": delivery_group_name,
            "bot_username": bot_username,
            "owner_telegram_id": owner_telegram_id,
            "setup_completed_at": datetime.now().isoformat(),
            "message": f"✅ Successfully set up Telegram group for {restaurant_name}"
        }
        
        logger.info(f"✅ Dine-in Setup complete for {restaurant_name}: Group ID {dine_in_group_id}")
        logger.info(f"✅ delivery Setup complete for {restaurant_name}: Group ID {delivery_group_id}")
        return result
        
    except Exception as e:
        logger.error(f"❌ Setup failed for {restaurant_name}: {e}")
        
        if service_mode in ['dine_in', 'both']:
            # Clean up if group was created
            if 'dine_in_group_id' in locals() and dine_in_group_id: 
                try:
                    await leave_group(dine_in_group_id)
                    logger.info(f"Cleaned up group {dine_in_group_id}")
                except:
                    pass

        if service_mode in ['delivery', 'both']:
            # Clean up if group was created
            if 'delivery_group_id' in locals() and delivery_group_id: 
                try:
                    await leave_group(delivery_group_id)
                    logger.info(f"Cleaned up group {delivery_group_id}")
                except:
                    pass
        
        raise Exception(f"Telegram setup failed for {restaurant_name}: {str(e)}")