import json
import discord
from datetime import datetime, timedelta, timezone
import os

deletion_time_minutes = 1

# Log a message as sensitive by storing its ID and timestamp in a JSON file
async def write_as_sensitive(message):
    if not os.path.exists("sensitive_messages.json"):
        with open("sensitive_messages.json", "w") as f:
            json.dump([], f)

    with open("sensitive_messages.json", "r+") as file:
        try:
            data = json.load(file)
        except json.JSONDecodeError:
            data = []

        print(f"Message Logged for Deletion: {message.id}")
        data.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),  # UTC timestamp
            "message_id": str(message.id),
            "channel_id": str(message.channel.id)
        })

        file.seek(0)
        file.truncate()
        json.dump(data, file, indent=4)


# Check the JSON for messages older than x amount of time and remove them
def check_for_old_messages():
    if not os.path.exists("sensitive_messages.json"):
        return []

    with open("sensitive_messages.json", "r+") as file:
        try:
            data = json.load(file)
        except json.JSONDecodeError:
            data = []

        current_time = datetime.now(timezone.utc)
        expired = []
        still_valid = []

        for entry in data:
            try:
                msg_time = datetime.fromisoformat(entry["timestamp"])
            except ValueError:
                continue

            if (current_time - msg_time) > timedelta(minutes=deletion_time_minutes):
                expired.append(entry)      
            else:
                still_valid.append(entry) 
        file.seek(0)
        file.truncate()
        json.dump(still_valid, file, indent=4)

    return expired

# Delete a message by ID and channel, adding a reaction to the original message if it was a reply
async def delete_message(bot, message_id, channel_id):
    channel = bot.get_channel(int(channel_id))
    if channel is None:
        print(f"Bot cannot access channel {channel_id}")
        return
    try:
        msg = await channel.fetch_message(int(message_id))

        # If the message was a reply, add emoji to the original message
        if msg.reference and msg.reference.message_id:
            try:
                ref_msg = await channel.fetch_message(msg.reference.message_id)
                await ref_msg.add_reaction("🗑️")
                print(f"Added reaction to original message {ref_msg.id}")
            except discord.NotFound:
                print(f"Original referenced message not found for {message_id}")
            except discord.Forbidden:
                print(f"No permission to add reactions in {channel_id}")
            except discord.HTTPException as e:
                print(f"Failed to add reaction: {e}")

        # Finally delete the sensitive message
        await msg.delete()
        print(f"Deleted sensitive message {message_id}")

    except discord.NotFound:
        print(f"Message {message_id} already deleted.")
    except discord.Forbidden:
        print(f"Bot lacks permissions to delete message {message_id}.")
    except discord.HTTPException as e:
        print(f"Failed to delete message {message_id}: {e}")



    
    
    
        