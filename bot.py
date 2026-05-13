from email.mime import message
import discord
from discord.ext import commands
import os 
from dotenv import load_dotenv
import json
from datetime import datetime

# Load the .env file to get the Discord Token and OpenAI API Key
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
DM_User = int(os.getenv("DM_USER"))
output_dir = os.getenv("output_dir")

# Imported functions from Queue Manager and Scheduler to allow edits to queue and schedule
from queueManager import react_queue, get_queue,add_to_queue, remove_from_queue, save_queues, load_queues, clear_user_queue
from scheduler import daily_commands, purge_channel, get_incidents, write_suggested_values
from suggestionWritter import write_values
from ask_anythingLLM import ask_anythingllm
from LLM_Upload_Manager import update_doc, full_upload

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
        response = ask_anythingllm(question)
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
    write_values(suggestion)
    await ctx.reply("Suggestion has been recorded")

# Updates the suggestion list
@bot.command(name = "update")
async def update(ctx):
    write_suggested_values()
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
    `!queue` - Show the current queue.
    `!add @User` - Add a user to the queue.
    `!remove @User` - Remove a user from the queue.
    `!react @User` - React on behalf of a user.
    `!clear` - Clear all queues.

    __Channel Management:__
    `!purge` - Clear the Jabber-Shift-Chat channel.
    `!reload_times` - Reload bot task schedule.

    __Incident + Search Functions:__
    `!incidents` - Get active incidents (emails).
    `!search "question"` - Ask a question and get internal documentation answers.
    `!teach "text"` - Suggest content for the search.
    `!teach_update` - Update suggestion list (Only TLs can approve suggestions). 
    `!db_update` - Updates the Database Backend if changes to Search Files have been made.

    __Other:__
    `!create_json` - Create JSON files from formatted data if KBs are out of date
    `!help` - Display this help message.

    *You can also DM the bot with ITSD questions and it will reply with answers from the internal search engine.*
    """
    await ctx.send(help_text)
    
# Make it so that if anyone direct messages the bot it will respond with a message
@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    
    if message.channel.type == discord.ChannelType.private:
        async with message.channel.typing():
            try:
                response = ask_anythingllm(message.content)
                await message.channel.send(response)
            except Exception as e:
                await message.channel.send(f"Error: {e}")
    else:
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

# When the bot comes online all daily commands a run and the queue is loaded from the JSON File 
@bot.event
async def on_ready():
    await daily_commands(bot)
    load_queues()
    print("Bot Online")

# Runs the bot with the Discord Token
bot.run(TOKEN)