import discord
from discord.ext import commands

import asyncio
import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import json
import pytz  
import logging 

from api_key import TOKEN

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set up the bot
intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True
bot = commands.Bot(command_prefix='!', intents=intents)

consultant_queue = []
not_ready_queue = []
queue_message = None  # Variable to store the reference to the queue message

# Add the user based on the person's display name
@bot.command(name='add')
async def add_user(ctx, member: discord.Member):
    user_name = member.display_name
    if user_name not in consultant_queue:
        consultant_queue.append(user_name)
        await ctx.send(f'{user_name} has been added to the queue', mention_author=False)
    else:
        await ctx.send(f'{user_name} already in the queue', mention_author=False)

# Remove a user from the queue
@bot.command(name='remove')
async def remove_user(ctx, member: discord.Member):
    user_name = member.display_name
    if user_name in consultant_queue:
        consultant_queue.remove(user_name)
        await ctx.send(f'{user_name} has been removed from the queue', mention_author=False)
    elif user_name in not_ready_queue:
        not_ready_queue.remove(user_name)
        await ctx.send(f'{user_name} has been removed from the queue', mention_author=False)
    else:
        await ctx.send(f'{user_name} is not in the queue', mention_author=False)

# Print the queue
@bot.command(name='queue')
async def print_queue(ctx):
    global queue_message  # Reference the global variable

    if len(consultant_queue) == 0 and len(not_ready_queue) == 0:
        await ctx.send('Queue is empty')
        return
    queue_message_content = generate_queue_message()
    queue_message = await ctx.send(queue_message_content, mention_author=False)

# Put a user in the not ready queue
@bot.command(name='offqueue')
async def off_queue(ctx, member: discord.Member):
    user_name = member.display_name
    if user_name in consultant_queue:
        consultant_queue.remove(user_name)
        not_ready_queue.append(user_name)
        await ctx.send(f'{user_name} has been moved to the not ready queue', mention_author=False)
    else:
        await ctx.send(f'{user_name} is not in the queue', mention_author=False)

# Remove a user from the not ready queue
@bot.command(name='onqueue')
async def on_queue(ctx, member: discord.Member):
    user_name = member.display_name
    if user_name in not_ready_queue:
        not_ready_queue.remove(user_name)
        consultant_queue.append(user_name)
        await ctx.send(f'{user_name} has been moved to the ready queue', mention_author=False)
    else:
        await ctx.send(f'{user_name} is not in the not ready queue', mention_author=False)

# Handle reaction addition to the queue message only
@bot.event
async def on_reaction_add(reaction, user):
    global queue_message  # Reference the global variable

    # Ensure queue_message is defined and has an ID
    if queue_message is not None and hasattr(queue_message, "id"):
        # Check if the reaction is on the queue message and not added by the bot
        if reaction.message.id == queue_message.id and not user.bot:
            user_name = user.display_name

            # Toggle user between consultant_queue and not_ready_queue
            if user_name in consultant_queue:
                consultant_queue.remove(user_name)
                not_ready_queue.append(user_name)
            elif user_name in not_ready_queue:
                not_ready_queue.remove(user_name)
                consultant_queue.append(user_name)

            # Update the queue message content
            queue_message_content = generate_queue_message()

            # Edit the queue message with updated content
            await queue_message.edit(content=queue_message_content)

            # Remove the user's reaction
            await reaction.remove(user)
    save_queues()

# Skips the first person in the queue and moves them to the back
@bot.command(name='skip')
async def skip_user(ctx):
    if consultant_queue:
        skipped_user = consultant_queue.pop(0)
        consultant_queue.append(skipped_user)
        await ctx.send(f'{skipped_user} has been skipped', mention_author=False)
    else:
        await ctx.send('No users to skip in the queue.', mention_author=False)

# Clears the queue
@bot.command(name='clear')
async def clear_queue(ctx):
    consultant_queue.clear()
    not_ready_queue.clear()
    await ctx.send('Queue has been cleared')

# Generates the queue message content
def generate_queue_message():
    # Construct the queue message content
    queue_message_content = "**Queue: \n**"
    if consultant_queue:
        queue_message_content += " -> ".join(consultant_queue) + "\n"
    else:
        queue_message_content += "No users in queue.\n"

    queue_message_content += '\n**With User: \n**'
    if not_ready_queue:
        queue_message_content += ' '.join([f'{i+1}. {user}' for i, user in enumerate(not_ready_queue)])
    else:
        queue_message_content += "No users currently not ready."

    queue_message_content += '\n*Please react before and after taking a user*'
    return queue_message_content

# Handle unknown command
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send('Unknown command. Please use !add, !remove, !queue, !skip, !clear, !offqueue, !onqueue')

# Manually purge the channel
@bot.command(name='purge')
async def purge_channel_command(ctx):
    await purge_channel()

# Purge the channel
async def purge_channel():
    logger.info("Running scheduled channel purge...")
    guild = bot.guilds[0]  # Adjust this if your bot is in multiple servers
    channel = discord.utils.get(guild.text_channels, name="jabber-shift-chat")

    if channel:
        try:
            await channel.purge(limit=1000)
            await channel.send("The Jabber-Shift-Chat channel has been cleared.")
            logger.info("Channel purged successfully.")
        except Exception as e:
            logger.error(f"Failed to purge the channel: {e}")
    else:
        logger.error("Channel not found")

# Start the scheduler to run the purge at a specific time every day
def start_scheduler():
    scheduler = AsyncIOScheduler(event_loop=bot.loop, timezone='America/New_York')
    # Schedule the purge for every day at 7:45 AM Eastern Time
    scheduler.add_job(purge_channel, 'cron', hour = 0, minute=1, misfire_grace_time=60)
    scheduler.start()
    logger.info("Scheduler started.")

# Load queues from a file
def load_queues():
    global consultant_queue, not_ready_queue
    try:
        with open("queues.json", "r") as file:
            data = json.load(file)
            consultant_queue = data.get("consultant_queue", [])
            not_ready_queue = data.get("not_ready_queue", [])
    except FileNotFoundError:
        # If the file doesn't exist, just use empty lists
        consultant_queue = []
        not_ready_queue = []

# Save queues to a file
def save_queues():
    data = {
        "consultant_queue": consultant_queue,
        "not_ready_queue": not_ready_queue
    }
    with open("queues.json", "w") as file:
        json.dump(data, file)

@bot.event
async def on_command(ctx):
    save_queues()

# When the bot is ready, start the scheduler
@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')
    load_queues()
    start_scheduler()

# Start the bot
bot.run(TOKEN)