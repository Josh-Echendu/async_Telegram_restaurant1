from .config_file import app, RATE_LIMIT_DELAY, logger
from pyrogram.enums import ChatType, ChatMemberStatus
from pyrogram.errors import FloodWait, RPCError
import asyncio
from pyrogram.types import ChatAdministratorRights


async def establish_bot_contact(bot_username: str):
    """
    Establish mutual contact by sending /start to the bot
    """
    logger.info(f"Establishing contact with {bot_username}")
    
    async with app:
        try:
            await app.send_message(bot_username, "/start")
            await asyncio.sleep(RATE_LIMIT_DELAY)
            logger.info(f"✅ Contact established with {bot_username}")
        except Exception as e:
            logger.error(f"❌ Failed to establish contact: {e}")
            raise


async def create_telegram_group(group_name: str, description: str = ""):
    """
    Create a new Telegram supergroup
    """
    logger.info(f"Creating group: {group_name}")
    
    async with app:
        try:
            group = await app.create_supergroup(group_name, description)
            await asyncio.sleep(RATE_LIMIT_DELAY)
            logger.info(f"✅ Group created: {group.id}, GROUP_data:{group}")
            return {"groupid": group.id, "title": group.title}
        except Exception as e:
            logger.error(f"❌ Failed to create group: {e}")
            raise


async def add_member_to_group(group_id: int, member_id: str):
    """
    Add a member (user or bot) to a group
    """
    logger.info(f"Adding {member_id} to group {group_id}")
    
    async with app:
        try:
            await app.add_chat_members(group_id, member_id)
            await asyncio.sleep(RATE_LIMIT_DELAY)
            logger.info(f"✅ Added {member_id} to group")
        except Exception as e:
            logger.error(f"❌ Failed to add member: {e}")
            raise


async def promote_to_admin(group_id: int, member_id: int | str, is_hidden: bool = False):
    logger.info(f"Promoting {member_id} to admin in group {group_id}")
    logger.info(type(member_id))
    logger.info(repr(member_id))

    async with app:
        try:
            rights = ChatAdministratorRights(
                is_anonymous=is_hidden, 
                can_manage_chat=False,
                can_delete_messages=False,
                can_manage_video_chats=False,
                can_restrict_members=False,
                can_promote_members=False,
                can_change_info=False,
                can_invite_users=True,
                can_post_stories=False,
                can_edit_stories=False,
                can_delete_stories=False,
                can_pin_messages=True,
                can_manage_topics=False,
            )

            await app.promote_chat_member(
                chat_id=group_id,
                user_id=member_id,
                privileges=rights,
            )

            await asyncio.sleep(RATE_LIMIT_DELAY)
            logger.info(f"✅ {member_id} promoted to admin")

        except Exception as e:
            logger.exception(f"❌ Failed to promote {member_id}: {e}")
            raise


async def send_test_message(group_id: int, message: str):
    """
    Send a test message to verify setup
    """
    logger.info(f"Sending test message to group {group_id}")
    
    async with app:
        try:
            await app.send_message(group_id, message)
            logger.info(f"✅ Test message sent")
        except Exception as e:
            logger.error(f"❌ Failed to send message: {e}")
            raise


async def leave_group(group_id: int):
    """
    Make admin account leave the group
    """
    logger.info(f"Admin leaving group {group_id}")
    
    async with app:
        try:
            await app.leave_chat(group_id)
            logger.info(f"✅ Admin left group {group_id}")
        except Exception as e:
            logger.error(f"❌ Failed to leave group: {e}")
            raise