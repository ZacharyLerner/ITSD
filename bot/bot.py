import discord
from api_key import TOKEN
from discord.ext import commands

# Imported functions from Queue Manager and Scheduler to allow edits to queue and schedule
from queueManager import react_queue, get_queue,add_to_queue, remove_from_queue, save_queues, load_queues, clear_user_queue
from scheduler import daily_commands

# Discord Intents to allow the bot to access message reactions, content, and user info
intents = discord.Intents.default()
intents.reactions = True  
intents.messages = True  
intents.message_content = True

# Global Variable that stores the message ID for the last bot Queue Message
last_bot_message = ""

# All Commands must have !
bot = commands.Bot(command_prefix="!", intents=intents)

# BOT COMMANDS 

# Prints out the Queue and updates the last bot message sent
# Ex. !queue will print who is on the ready and not ready queue
@bot.command(name = "queue")
async def print_queue(ctx):
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

# In the event that an invalid command is run it will print out possible correct commands
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send('Unknown command. Please use !add, !remove, !queue, !clear, !react')

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

bot.run(TOKEN)