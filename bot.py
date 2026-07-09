from email.mime import message
import asyncio
import discord
from discord import reaction
from discord.ext import commands
import os 
from dotenv import load_dotenv
import json
from datetime import datetime, timedelta
from servicenow import reuploadAll, ticketInfo
from collections import deque

# Load the .env file to get the Discord Token and OpenAI API Key
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
DM_User = int(os.getenv("DM_USER"))
output_dir = os.getenv("output_dir")

# Imported functions from Queue Manager and Scheduler to allow edits to queue and schedule
from queueManager import react_queue, get_queue,add_to_queue, remove_from_queue, save_queues, load_queues, clear_user_queue, back_to_start
from scheduler import daily_commands, purge_channel, get_incidents, write_newsletter_scheduled
from ask_anythingLLM import ask_anythingllm
from LLM_Upload_Manager import update_doc, full_upload
from newsletterManager import check_jabber_message, check_ticket_message, write_professional_chat, write_newsletter_managed

# Discord Intents to allow the bot to access message reactions, content, and user info
intents = discord.Intents.default()
intents.reactions = True  
intents.messages = True  
intents.message_content = True

# Global Variable that stores the message ID for the last bot Queue Message
last_bot_message = ""
indexes = {}

# Folder to store testing data such as feedback or AI documents 
DATA_FOLDER = "data"

# All Commands must have !
bot = commands.Bot(command_prefix="!", intents=intents,help_command=None)

import os

# Folder to store message ID's of already recorded suggestions to prevent duplicates
def track_suggestions(message):
    os.makedirs(DATA_FOLDER, exist_ok=True)
    filepath = os.path.join(DATA_FOLDER, "track_suggestions.json")

    if os.path.exists(filepath):
        with open(filepath, "r") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                f.seek(0)
                data = [json.loads(line) for line in f if line.strip()]
    else:
        data = []

    if message.id not in data:
        data.append(message.id)

    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)

# Loads the message ID's of already recorded suggestions
def load_suggestions():
    filepath = os.path.join(DATA_FOLDER, "track_suggestions.json")
    if not os.path.exists(filepath):
        return []
    with open(filepath, "r") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            f.seek(0)
            data = [json.loads(line) for line in f if line.strip()]
    return data

# Checks if a suggestion has already been recorded based on its message ID to prevent duplicates
def suggestion_recorded(message_id):
    return message_id in load_suggestions()

def log_feedback(user, message, file):
    clean_content = message.content[:-175].strip()
    entry = {
        "timestamp": str(datetime.now()),
        "message_id": message.id,
        "message": clean_content
    }

    os.makedirs(DATA_FOLDER, exist_ok=True)
    filepath = os.path.join(DATA_FOLDER, file)

    if os.path.exists(filepath):
        with open(filepath, "r") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                f.seek(0)
                data = [json.loads(line) for line in f if line.strip()]
    else:
        data = []

    data.append(entry)

    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)

async def write_values(suggestion):
    guild = bot.guilds[0]
    channel = discord.utils.get(guild.text_channels, name="additions")
    await channel.send("\n**Suggestion (React with 👍 to approve or 👎 to deny):\n** \n" + suggestion)

def get_image_description(message_id):
    IMAGE_CONTEXT_FILE = "image_contexts.json"
    filepath = os.path.join(DATA_FOLDER, IMAGE_CONTEXT_FILE)

    if not os.path.exists(filepath):
        return None

    with open(filepath, "r") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            return None

    return data.get(str(message_id))


# BOT COMMANDS 

# Prints out the Queue and updates the last bot message sent
# Ex. !queue will print who is on the ready and not ready queue
@bot.command(name = "queue")
async def print_queue(ctx):
    global last_bot_message 
    last_bot_message = await ctx.send(get_queue())

@bot.command(name = "q")
async def print_queue_second(ctx):
    global last_bot_message 
    last_bot_message = await ctx.send(get_queue())

# Adds a User to the Queue with their Nickname/Display_Name
# Ex. !add @ExampleUser will print a message confirming a person has been added to the Queue
@bot.command(name = "add")
async def add_user(ctx, member: discord.Member):
    await ctx.send(add_to_queue(member.display_name))

# Removes a user from the Queue
# Ex. !remove @ExampleUser will print a message confirming a person has been removed to the Queue
@bot.command(name = "remove")
async def remove_user(ctx, member: discord.Member):
    await ctx.send(remove_from_queue(member.display_name))

# Adds a User to the Queue with their Display_Name
# Ex. !join will print a message confirming a person has been added to the Queue
@bot.command(name = "join")
async def add_user(ctx):
    await ctx.send(add_to_queue(ctx.author.display_name))

@bot.command(name = "back")
async def back_user(ctx):
    back_response = back_to_start(ctx.author.display_name)
    if back_response != None:
        await ctx.send(back_response)
    else:
        global last_bot_message 
        last_bot_message = await ctx.send(get_queue())

# Removes a user from the Queue
# Ex. !leave will print a message confirming a person has been removed to the Queue
@bot.command(name = "leave")
async def remove_user(ctx):
    await ctx.send(remove_from_queue(ctx.author.display_name))

# "Reacts" on the behalf of a specific user. 
# Ex. !react @@ExampleUser will move them to the other queue, just as reacting to the message would, and will reprint the queue
@bot.command(name = "react")
async def remove_user(ctx, member: discord.Member):
    global last_bot_message
    react_queue(member.display_name)
    last_bot_message = await ctx.send(get_queue())

# Clears the Queue of all users in the ready and not ready queues
# Ex. !clear will print a message confirming the queue is cleared and the queue should appear as empty if prompted
@bot.command(name = "clear")
async def clear_queue(ctx):
    await ctx.send(clear_user_queue())

# Purges the Jabber-Shift-Chat channel of all messages
# Ex. !purge will clear the Jabber-Shift-Chat channel of all messages
@bot.command(name = "purge")
async def purge(ctx):
    await purge_channel(bot)

# Gets the incidents from the ServiceNow API and prints them out
# Ex. !incidents will print out the incidents from the ServiceNow API
@bot.command(name = "incidents")
async def incidents(ctx):
    await get_incidents(bot)

# Searches the internal recourses for the question and returns the response
# Ex. !search "How do I reset my password?" will return the response from the search engine
@bot.command(name = "search")
async def ask_question(ctx, *, question):
    global indexes
    async with ctx.typing():
        
        message = ctx.message
        image_attachments = [
            attachment
            for attachment in message.attachments
            if (
                 attachment.content_type
                  and attachment.content_type.startswith("image/")
            )
            or attachment.filename.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp"))
        ]

        if "INC" in question:
            inc_index = question.find("INC")
            ticket = question[inc_index:inc_index + 10].strip() 
            ticket = ticketInfo(ticket)
            response = await asyncio.to_thread(ask_anythingllm, question, ticket=ticket, image_urls=image_attachments, message_id=message.id)
        else:
            response = await asyncio.to_thread(ask_anythingllm, question, image_urls=image_attachments, message_id=message.id)
    response += "\n\n\n*This response was generated with AI Assistance. Please confirm all information with internal resources or with a TL or FTS. \nPlease react with 👍 or 👎 to rate this response!*"
    await ctx.reply(response)
# Reloads the times for the bot to run the daily commands
# Ex. !reload_times will reload the times for the bot to run the daily commands
@bot.command(name = "reload_times")
async def reload_times(ctx):
    await daily_commands(bot)
    await ctx.reply("Reloaded bot times")

# Adds a suggestion to the suggestion list
# Ex. !teach "Android 14 devices now work" will add the suggestion to the list
@bot.command(name = "teach")
async def suggest(ctx, *, suggestion):
    await write_values(suggestion)
    await ctx.reply("Suggestion has been recorded")

@bot.command(name= "events_help")
async def events_help(ctx):
    help_text = """
    **Scheduling Events with the ITSD Bot**
    Visit the following google calendar to view / schedule events: https://calendar.google.com/calendar/u/0/r?cid=b2xkaGVscGRlc2tAZXRhbC51cmkuZWR1
    
    __If you are making a custom event:__
    The event description will be the text sent out (ex. "Check printers")
    The event location will be the channel the message is sent in (ex. jabber-shift-chat) (leave blank for jabber-shift-chat)
    The date and time is when the event will be scheduled (ex. every Monday at 9:30am)
    
    __If you are scheduling a pre made event that requires custom logic:__
    All you need is the event name and the scheduled time.
    The event name must be exactly the same as the pre made event name.

    **Available pre made events names for Scheduling**

    `email_check` - Schedules a daily check for new emails/incidents and posts the number of new emails in the #jabber-shift-chat channel.

    `reupload_docs` - Schedules a weekly reupload of all documents to the LLM backend to ensure the most up to date information is being used. This is especially important if there have been recent changes to KB articles or other internal documentation.
    """
    await ctx.send(help_text)

@bot.command(name = "docs_upload")
async def docs_upload(ctx):
    try:
        await ctx.reply("Uploading documents... This may take a few minutes.")
        result = await asyncio.to_thread(reuploadAll)
        await ctx.reply("Documents have been uploaded")
    except Exception as e:
        if str(e) != "Expecting value: line 1 column 1 (char 0)" and e != "object dict can't be used in 'await' expression":
            await ctx.reply(f"Upload failed: {e}")

@bot.command(name= "newsletter")
async def write_newsletter(ctx):
    try:
        message = write_newsletter_managed()
        await write_newsletter_scheduled(bot, message)
    except Exception as e:
        await ctx.reply(f"Newsletter generation failed: {e}")

# Updates the suggestion list
@bot.command(name = "update")
async def update(ctx):
    try:
        update_doc("LLM_Files/additions.json")
        await ctx.reply("Teach file has been updated")
    except Exception as e:
        await ctx.reply(f"Upload failed: {e}")

@bot.command(name = 'help')
async def custom_help(ctx):
    help_text = """
    **Available Commands**

    __General Queue Commands:__
    `!queue` or `!q` - Show the current queue.
    `!add @User` - Add a user to the queue.
    `!remove @User` - Remove a user from the queue.
    `!join` - Add yourself to the queue.
    `!leave` - Remove yourself from the queue.
    `!react @User` - React on behalf of a user.
    `!clear` - Clear all queues.

    __Channel Management:__
    `!purge` - Clear the Jabber-Shift-Chat channel.
    `!reload_times` - Reload bot task schedule.

    __Incident + Search Functions:__
    `!incidents` - Get active incidents (emails).
    `!search "question"` - Ask a question and get internal documentation answers.
    `!teach "text"` - Suggest content for the search.
    `!newsletter` - Generate and post the weekly newsletter.
    `!docs_upload` - Reupload all documents to the LLM backend immediately (instead of waiting for the scheduled weekly upload).
    `!db_update` - Updates the Database Backend if changes to Search Files have been made.

    __Other:__
    `!help` - Display this help message.
    `!events_help` - Get information on scheduling events.

    *You can also DM the bot with ITSD questions and it will reply with answers from the internal search engine.*
    """
    await ctx.send(help_text)
    

# Make it so that if anyone direct messages the bot it will respond with a message
@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    
    if message.reference and message.reference.message_id:
        replied_message = message.reference.resolved

        if replied_message is None:
            replied_message = await message.channel.fetch_message(
                message.reference.message_id
            )

        if replied_message.author == bot.user and "AI Assistance" in replied_message.content:

            stack = deque()
            current_message = replied_message
            while current_message:
                stack.append(current_message)
                if current_message.reference and current_message.reference.message_id:
                    reference = current_message.reference
                    next_message = reference.resolved

                    if next_message is None:
                        next_message = await message.channel.fetch_message(reference.message_id)

                    current_message = next_message
                else:
                    current_message = None

            context = "Previous conversation history to keep in mind: {"

            while len(stack) > 1:
                current_message = stack.pop()
                user_content = current_message.content
                if get_image_description(current_message.id) != None:
                    user_content += "\n" + "Message Image Content Description: " + str(get_image_description(current_message.id))
                bot_content = stack.pop().content
                footer_start = bot_content.find("*This response was generated with AI Assistance.")
                if footer_start != -1:
                    bot_content = bot_content[:footer_start]
                context += "\n User: " + user_content.strip() + "\n Bot: " + bot_content.strip()

            context += "}\n User current response / question: " + message.content
            async with message.channel.typing():
                try:
                    image_attachments = [
                        attachment
                        for attachment in message.attachments
                        if (
                            attachment.content_type
                            and attachment.content_type.startswith("image/")
                        )
                        or attachment.filename.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp"))
                    ]
                    if "INC" in context:
                        inc_index = context.find("INC")
                        ticket = context[inc_index:inc_index + 10].strip() 
                        ticket = ticketInfo(ticket)
                        response = await asyncio.to_thread(ask_anythingllm, context, ticket=ticket, image_urls = image_attachments, message_id=message.id) + "\n\n\n*This response was generated with AI Assistance. Please confirm all information with internal resources or with a TL or FTS. \nPlease react with 👍 or 👎 to rate this response!*"
                    else:
                        response = await asyncio.to_thread(ask_anythingllm, context, image_urls = image_attachments, message_id=message.id) + "\n\n\n*This response was generated with AI Assistance. Please confirm all information with internal resources or with a TL or FTS. \nPlease react with 👍 or 👎 to rate this response!*"
                    if "This response was generated with AI Assistance." not in response:
                        response += "\n\n\n*This response was generated with AI Assistance. Please confirm all information with internal resources or with a TL or FTS. \nPlease react with 👍 or 👎 to rate this response!*"
                    await message.reply(response)
                except Exception as e:
                    await message.channel.send(f"Error: {e}")
            return

    # DMs → AnythingLLM
    if message.channel.type == discord.ChannelType.private:
        async with message.channel.typing():
            question = message.content
            try:
                image_attachments = [
                    attachment
                    for attachment in message.attachments
                    if (
                        attachment.content_type
                        and attachment.content_type.startswith("image/")
                    )
                    or attachment.filename.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp"))
                ]
                if "INC" in question:
                    inc_index = question.find("INC")
                    ticket = question[inc_index:inc_index + 10].strip() 
                    ticket = ticketInfo(ticket)
                    response = await asyncio.to_thread(ask_anythingllm, question, ticket=ticket, image_urls = image_attachments, message_id=message.id)
                    response += "\n\n\n*This response was generated with AI Assistance. Please confirm all information with internal resources or with a TL or FTS. \nPlease react with 👍 or 👎 to rate this response!*"
                else:
                    response = await asyncio.to_thread(ask_anythingllm, question, image_urls = image_attachments, message_id=message.id)
                    response += "\n\n\n*This response was generated with AI Assistance. Please confirm all information with internal resources or with a TL or FTS. \nPlease react with 👍 or 👎 to rate this response!*"
                await message.reply(response)
            except Exception as e:
                await message.channel.send(f"Error: {e}")
        return
    
    elif message.channel.name == "jabber-shift-chat":
        try:
            check_jabber_message(message.content)
        except Exception as e:
            print(f"Jabber Classifier error: {e}")

    elif message.channel.name == "service-now-ticket-help":
        try:
            check_ticket_message(message.content)
        except Exception as e:
            print(f"Ticket Classifier error: {e}")

    elif message.channel.name == "professional-chat":
        try:
            write_professional_chat(message.content)
        except Exception as e:
            print(f"Ticket Classifier error: {e}")
    
    elif message.channel.name == "vem-chat":
        filepath = "data/vem.json"
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                vem = json.load(f)
        else:
            vem = []
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(vem, f, indent=4, ensure_ascii=False)

        new_time = message.created_at
        if message.content not in [item["message"] for item in vem]:
            vem.append({
            "message": message.content.strip(),
            "time": new_time.isoformat()
            })

            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(vem, f, indent=4, ensure_ascii=False)

        else:
            for item in vem:
                if item["message"] == message.content:
                    old_time = datetime.fromisoformat(item["time"])
                    time_difference = new_time - old_time

                    if time_difference < timedelta(minutes=20):
                        await message.reply("This ticket was mentioned less than 20 minutes ago. Please make sure it isn't currently being worked on by someone else.")

                    item["time"] = new_time.isoformat()

                    with open(filepath, "w", encoding="utf-8") as f:
                        json.dump(vem, f, indent=4, ensure_ascii=False)

                    break
    await bot.process_commands(message)
    


# In the event that an invalid command is run it will print out possible correct commands
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send('Unknown command. Check the list of commands with !help.')

# After every command is run the queue will be saved to a JSON File
@bot.event
async def on_command_completion(ctx):
    save_queues()

# Moves the User to the respective queue when they react with any emoji to the Queue Message and edits the queue message to reflect the change
# Ex. Reacting with a thumbs up will move a person from the Ready to Not Ready Position
@bot.event
async def on_reaction_add(reaction, user):
    global last_bot_message
    
    # checks for reactions to messages for the zoom que 
    if reaction.message == last_bot_message:
        react_queue(user.display_name)
        await last_bot_message.edit(content = get_queue())
        await last_bot_message.remove_reaction(reaction.emoji, user)
        save_queues()

    # checks for feedback reactions for bot responses 
    elif reaction.message.channel.name == "bot-commands":
        if reaction.message.author == bot.user:
            if str(reaction.emoji) == "👍":
                log_feedback(user, reaction.message, "positive_feedback.json")
            elif str(reaction.emoji) == "👎":
                log_feedback(user, reaction.message, "negative_feedback.json")

    elif reaction.message.channel.name == "additions":
        guild = bot.guilds[0]
        channel = discord.utils.get(guild.text_channels, name="additions")
        if reaction.message.author == bot.user:
            if str(reaction.emoji) == "👍" and not suggestion_recorded(reaction.message.id):
                filepath = "LLM_Files/additions.json"
                if os.path.exists(filepath):
                    with open(filepath, "r", encoding="utf-8") as f:
                        additions = json.load(f)
                else:
                    additions = []
                additions.append(reaction.message.content[57:].strip())
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(additions, f, indent=4, ensure_ascii=False)
                try:
                    track_suggestions(reaction.message)
                    update_doc("LLM_Files/additions.json")
                    await channel.send("Teach file has been updated")
                except Exception as e:
                    await channel.send(f"Upload failed: {e}")
            elif str(reaction.emoji) == "👎" and not suggestion_recorded(reaction.message.id):
                await reaction.message.delete()

# When the bot comes online all daily commands a run and the queue is loaded from the JSON File 
@bot.event
async def on_ready():
    await daily_commands(bot)
    load_queues()
    print("Bot Online")

# Runs the bot with the Discord Token
bot.run(TOKEN)

