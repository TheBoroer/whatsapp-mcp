from dataclasses import asdict
from typing import List, Dict, Any, Optional
from mcp import types
from mcp.server.fastmcp import FastMCP, Context
from pydantic import BaseModel, Field
from whatsapp import (
    search_contacts as whatsapp_search_contacts,
    list_messages as whatsapp_list_messages,
    list_chats as whatsapp_list_chats,
    get_chat as whatsapp_get_chat,
    get_direct_chat_by_contact as whatsapp_get_direct_chat_by_contact,
    get_contact_chats as whatsapp_get_contact_chats,
    get_last_interaction as whatsapp_get_last_interaction,
    get_message_context as whatsapp_get_message_context,
    send_message as whatsapp_send_message,
    send_file as whatsapp_send_file,
    send_audio_message as whatsapp_audio_voice_message,
    download_media as whatsapp_download_media
)

# Initialize FastMCP server
mcp = FastMCP("whatsapp")

# Recipients the user approved for the rest of this session. Each MCP client
# session starts its own server process, so this resets every session.
_session_approved_recipients: set[str] = set()

# Cap how much of a long message the confirmation dialog shows
_PREVIEW_LIMIT = 1000


class SendApproval(BaseModel):
    remember: bool = Field(
        default=False,
        title="Don't ask again for this recipient this session",
    )


def _normalize_recipient(recipient: str) -> str:
    """Phone numbers and JIDs for the same person map to the same key."""
    return recipient if "@" in recipient else f"{recipient}@s.whatsapp.net"


async def _confirm_send(ctx: Context, recipient: str, what: str, body: Optional[str] = None) -> Optional[str]:
    """Ask the user to approve a send via an MCP elicitation dialog.

    Returns None when the send may proceed, otherwise the reason it was refused.
    Fails closed: if the client can't show the dialog, nothing is sent.
    """
    jid = _normalize_recipient(recipient)
    if jid in _session_approved_recipients:
        return None

    can_elicit = ctx.session.check_client_capability(
        types.ClientCapabilities(elicitation=types.ElicitationCapability())
    )
    if not can_elicit:
        return (
            "Not sent: sending requires the user's approval, and this MCP client "
            "can't show a confirmation dialog."
        )

    chat = whatsapp_get_chat(jid, include_last_message=False)
    who = f"{chat.name} ({jid})" if chat and chat.name else jid
    try:
        prompt = f"Send WhatsApp {what} to {who}?" + (f"\n\n{body}" if body else "")
        result = await ctx.elicit(message=prompt, schema=SendApproval)
    except Exception as e:
        return f"Not sent: the confirmation dialog failed ({e})."

    if result.action != "accept":
        return "Not sent: the user did not approve this send. Don't retry unless the user asks."

    if result.data.remember:
        _session_approved_recipients.add(jid)
    return None

# FastMCP validates tool results against the return annotation, so the
# dataclasses from whatsapp.py are converted to plain dicts before returning.

@mcp.tool()
def search_contacts(query: str) -> List[Dict[str, Any]]:
    """Search WhatsApp contacts by name or phone number.
    
    Args:
        query: Search term to match against contact names or phone numbers
    """
    contacts = whatsapp_search_contacts(query)
    return [asdict(contact) for contact in contacts]

@mcp.tool()
def list_messages(
    after: Optional[str] = None,
    before: Optional[str] = None,
    sender_phone_number: Optional[str] = None,
    chat_jid: Optional[str] = None,
    query: Optional[str] = None,
    limit: int = 20,
    page: int = 0,
    include_context: bool = True,
    context_before: int = 1,
    context_after: int = 1
) -> str:
    """Get WhatsApp messages matching specified criteria with optional context.
    
    Args:
        after: Optional ISO-8601 formatted string to only return messages after this date
        before: Optional ISO-8601 formatted string to only return messages before this date
        sender_phone_number: Optional phone number to filter messages by sender
        chat_jid: Optional chat JID to filter messages by chat
        query: Optional search term to filter messages by content
        limit: Maximum number of messages to return (default 20)
        page: Page number for pagination (default 0)
        include_context: Whether to include messages before and after matches (default True)
        context_before: Number of messages to include before each match (default 1)
        context_after: Number of messages to include after each match (default 1)
    """
    messages = whatsapp_list_messages(
        after=after,
        before=before,
        sender_phone_number=sender_phone_number,
        chat_jid=chat_jid,
        query=query,
        limit=limit,
        page=page,
        include_context=include_context,
        context_before=context_before,
        context_after=context_after
    )
    # Empty string on a database error
    return messages or "No messages to display."

@mcp.tool()
def list_chats(
    query: Optional[str] = None,
    limit: int = 20,
    page: int = 0,
    include_last_message: bool = True,
    sort_by: str = "last_active"
) -> List[Dict[str, Any]]:
    """Get WhatsApp chats matching specified criteria.
    
    Args:
        query: Optional search term to filter chats by name or JID
        limit: Maximum number of chats to return (default 20)
        page: Page number for pagination (default 0)
        include_last_message: Whether to include the last message in each chat (default True)
        sort_by: Field to sort results by, either "last_active" or "name" (default "last_active")
    """
    chats = whatsapp_list_chats(
        query=query,
        limit=limit,
        page=page,
        include_last_message=include_last_message,
        sort_by=sort_by
    )
    return [asdict(chat) for chat in chats]

@mcp.tool()
def get_chat(chat_jid: str, include_last_message: bool = True) -> Optional[Dict[str, Any]]:
    """Get WhatsApp chat metadata by JID.

    Args:
        chat_jid: The JID of the chat to retrieve
        include_last_message: Whether to include the last message (default True)
    """
    chat = whatsapp_get_chat(chat_jid, include_last_message)
    return asdict(chat) if chat else None

@mcp.tool()
def get_direct_chat_by_contact(sender_phone_number: str) -> Optional[Dict[str, Any]]:
    """Get WhatsApp chat metadata by sender phone number.

    Args:
        sender_phone_number: The phone number to search for
    """
    chat = whatsapp_get_direct_chat_by_contact(sender_phone_number)
    return asdict(chat) if chat else None

@mcp.tool()
def get_contact_chats(jid: str, limit: int = 20, page: int = 0) -> List[Dict[str, Any]]:
    """Get all WhatsApp chats involving the contact.
    
    Args:
        jid: The contact's JID to search for
        limit: Maximum number of chats to return (default 20)
        page: Page number for pagination (default 0)
    """
    chats = whatsapp_get_contact_chats(jid, limit, page)
    return [asdict(chat) for chat in chats]

@mcp.tool()
def get_last_interaction(jid: str) -> Optional[str]:
    """Get most recent WhatsApp message involving the contact.
    
    Args:
        jid: The JID of the contact to search for
    """
    message = whatsapp_get_last_interaction(jid)
    return message

@mcp.tool()
def get_message_context(
    message_id: str,
    before: int = 5,
    after: int = 5
) -> Dict[str, Any]:
    """Get context around a specific WhatsApp message.
    
    Args:
        message_id: The ID of the message to get context for
        before: Number of messages to include before the target message (default 5)
        after: Number of messages to include after the target message (default 5)
    """
    context = whatsapp_get_message_context(message_id, before, after)
    return asdict(context)

@mcp.tool()
async def send_message(
    recipient: str,
    message: str,
    ctx: Context
) -> Dict[str, Any]:
    """Send a WhatsApp message to a person or group. For group chats use the JID.
    The user is asked to approve each send in a dialog.

    Args:
        recipient: The recipient - either a phone number with country code but no + or other symbols,
                 or a JID (e.g., "123456789@s.whatsapp.net" or a group JID like "123456789@g.us")
        message: The message text to send
    
    Returns:
        A dictionary containing success status and a status message
    """
    # Validate input
    if not recipient:
        return {
            "success": False,
            "message": "Recipient must be provided"
        }

    preview = message if len(message) <= _PREVIEW_LIMIT else message[:_PREVIEW_LIMIT] + "... (truncated)"
    refusal = await _confirm_send(ctx, recipient, "message", f'"{preview}"')
    if refusal:
        return {"success": False, "message": refusal}

    # Call the whatsapp_send_message function with the unified recipient parameter
    success, status_message = whatsapp_send_message(recipient, message)
    return {
        "success": success,
        "message": status_message
    }

@mcp.tool()
async def send_file(recipient: str, media_path: str, ctx: Context) -> Dict[str, Any]:
    """Send a file such as a picture, raw audio, video or document via WhatsApp to the specified recipient. For group messages use the JID.
    The user is asked to approve each send in a dialog.

    Args:
        recipient: The recipient - either a phone number with country code but no + or other symbols,
                 or a JID (e.g., "123456789@s.whatsapp.net" or a group JID like "123456789@g.us")
        media_path: The absolute path to the media file to send (image, video, document)
    
    Returns:
        A dictionary containing success status and a status message
    """
    refusal = await _confirm_send(ctx, recipient, f"file {media_path}")
    if refusal:
        return {"success": False, "message": refusal}

    # Call the whatsapp_send_file function
    success, status_message = whatsapp_send_file(recipient, media_path)
    return {
        "success": success,
        "message": status_message
    }

@mcp.tool()
async def send_audio_message(recipient: str, media_path: str, ctx: Context) -> Dict[str, Any]:
    """Send any audio file as a WhatsApp audio message to the specified recipient. For group messages use the JID. If it errors due to ffmpeg not being installed, use send_file instead.
    The user is asked to approve each send in a dialog.

    Args:
        recipient: The recipient - either a phone number with country code but no + or other symbols,
                 or a JID (e.g., "123456789@s.whatsapp.net" or a group JID like "123456789@g.us")
        media_path: The absolute path to the audio file to send (will be converted to Opus .ogg if it's not a .ogg file)
    
    Returns:
        A dictionary containing success status and a status message
    """
    refusal = await _confirm_send(ctx, recipient, f"voice message from {media_path}")
    if refusal:
        return {"success": False, "message": refusal}

    success, status_message = whatsapp_audio_voice_message(recipient, media_path)
    return {
        "success": success,
        "message": status_message
    }

@mcp.tool()
def download_media(message_id: str, chat_jid: str) -> Dict[str, Any]:
    """Download media from a WhatsApp message and get the local file path.
    
    Args:
        message_id: The ID of the message containing the media
        chat_jid: The JID of the chat containing the message
    
    Returns:
        A dictionary containing success status, a status message, and the file path if successful
    """
    file_path = whatsapp_download_media(message_id, chat_jid)
    
    if file_path:
        return {
            "success": True,
            "message": "Media downloaded successfully",
            "file_path": file_path
        }
    else:
        return {
            "success": False,
            "message": "Failed to download media"
        }

if __name__ == "__main__":
    # Initialize and run the server
    mcp.run(transport='stdio')