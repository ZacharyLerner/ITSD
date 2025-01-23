import discord
from api_key import TOKEN
from discord.ext import commands

from queueManager import react_queue, get_queue,add_to_queue, remove_from_queue, save_queues, load_queues, clear_user_queue
from scheduler import daily_commands

intents = discord.Intents.default()
intents.reactions = True  
intents.messages = True  
intents.message_content = True

last_bot_message = ""

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.command(name = "queue")
async def print_queue(ctx):
    global last_bot_message 
    last_bot_message = await ctx.send(get_queue())
    
@bot.command(name = "add")
async def add_user(ctx, member: discord.Member):
    await ctx.send(add_to_queue(member.display_name))

@bot.command(name = "remove")
async def remove_user(ctx, member: discord.Member):
    await ctx.send(remove_from_queue(member.display_name))

@bot.command(name = "react")
async def remove_user(ctx, member: discord.Member):
    global last_bot_message
    react_queue(member.display_name)
    last_bot_message = await ctx.send(get_queue())

@bot.command(name = "clear")
async def clear_queue(ctx):
    await ctx.send(clear_user_queue())

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send('Unknown command. Please use !add, !remove, !queue, !clear, !react')

@bot.event
async def on_command_completion(ctx):
    save_queues()

@bot.event
async def on_reaction_add(reaction, user):
    global last_bot_message
    if reaction.message == last_bot_message:
        react_queue(user.display_name)
        await last_bot_message.edit(content = get_queue())
        await last_bot_message.remove_reaction(reaction.emoji, user)
    save_queues()

@bot.event
async def on_ready():
    daily_commands(bot)
    load_queues()
    print("Bot Online")

bot.run(TOKEN)