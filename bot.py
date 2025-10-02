from email.mime import message
import discord
from discord.ext import commands
import os 
from dotenv import load_dotenv
import json

# Load the .env file to get the Discord Token and OpenAI API Key
load_dotenv()
OPEN_API_API = os.getenv("OPEN_AI_API")
TOKEN = os.getenv("DISCORD_TOKEN")
DM_User = int(os.getenv("DM_USER"))

# Imported functions from Queue Manager and Scheduler to allow edits to queue and schedule
from queueManager import react_queue, get_queue,add_to_queue, remove_from_queue, save_queues, load_queues, clear_user_queue
from scheduler import daily_commands, purge_channel, get_incidents, write_suggested_values
from info.search import create_indexes, search_in_indexes
from info.ai_reader import ask_openai
from suggestionWritter import write_values
from info.document_creator import create_json_files
from security import write_as_sensitive

# Discord Intents to allow the bot to access message reactions, content, and user info
intents = discord.Intents.default()
intents.reactions = True  
intents.messages = True  
intents.message_content = True

# Global Variable that stores the message ID for the last bot Queue Message
last_bot_message = ""
indexes = {}

# All Commands must have !
bot = commands.Bot(command_prefix="!", intents=intents,help_command=None)

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
        results = search_in_indexes(indexes, question)
        response = ask_openai(question, results, OPEN_API_API)
    await ctx.reply(response)

    # dm ScuffedLad the question and response
    user = await bot.fetch_user(DM_User)
    info_message = (f"User: {ctx.author.display_name} || Time: {ctx.message.created_at}\n"
                    f"Question: {question}\n"
                    f"Response: {response}\n"
                    f"-----------------------------------\n")

# Reloads the times for the bot to run the daily commands
# Ex. !reload_times will reload the times for the bot to run the daily commands
@bot.command(name = "reload_times")
async def reload_times(ctx):
    await daily_commands(bot)
    await ctx.reply("Reloaded bot times")

# Adds a suggestion to the suggestion list
# Ex. !search_add "Android 14 devices now work" will add the suggestion to the list
@bot.command(name = "teach")
async def suggest(ctx, *, suggestion):
    write_values(suggestion)
    await ctx.reply("Suggestion has been recorded")

# Updates the suggestion list
# Ex. !search_update will update the suggestion list
@bot.command(name = "update")
async def update(ctx):
    write_suggested_values()
    await ctx.reply("Suggestion list has been updated")

@bot.command(name = "create_json")
async def create_json(ctx):
    create_json_files()
    await ctx.reply("JSON files have been created")
    global indexes 
    indexes= create_indexes("info/formattedFiles")

@bot.command(name="sen", aliases=["SEN"])
async def sen_check(ctx):
    if ctx.message.author == bot.user:
        return
    await write_as_sensitive(ctx.message)
    await ctx.message.add_reaction("🗑️")
    
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
    `!update` - Update suggestion list (Only TLs can approve suggestions). 

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
    # query the search engine
    if message.channel.type == discord.ChannelType.private:
        # type while searching
        async with message.channel.typing():
            results = search_in_indexes(indexes, message.content)
            response = ask_openai(message.content, results, OPEN_API_API)
        await message.channel.send(response)

        """
        #dm ScuffedLad the question and response
        user = await bot.fetch_user(511332467077283850)
        info_message = (f"User: {message.author.display_name} || Time: {message.created_at}\n"
                        f"Question: {message.content}\n"
                        f"Response: {response}\n"
                        f"-----------------------------------\n")
        
        await user.send(info_message)
        """
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
    if reaction.message == last_bot_message:
        react_queue(user.display_name)
        await last_bot_message.edit(content = get_queue())
        await last_bot_message.remove_reaction(reaction.emoji, user)
    save_queues()


# When the bot comes online all daily commands a run and the queue is loaded from the JSON File 
@bot.event
async def on_ready():
    await daily_commands(bot)
    load_queues()
    print("Bot Online")
    
    # Creates the list of indexes for the search engine to use
    global indexes 
    indexes= create_indexes("info/formattedFiles")

# Runs the bot with the Discord Token
bot.run(TOKEN)