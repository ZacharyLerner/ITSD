import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import discord
from discord.ext import tasks

# Deletes all messages in a specific chat
async def purge_channel(bot):
    guild = bot.guilds[0]  # Adjust this if your bot is in multiple servers
    channel = discord.utils.get(guild.text_channels, name="jabber-shift-chat")
    await channel.purge(limit=1000)
    await channel.send("The Jabber-Shift-Chat channel has been cleared.")

# Gives a list of commands to be run daily
def daily_commands(bot):
    scheduler = AsyncIOScheduler(event_loop=bot.loop, timezone='America/New_York')

    # Daily commands 
    scheduler.add_job(purge_channel, 'cron', hour=1, minute=1, misfire_grace_time=60, args=[bot])
    
    scheduler.start()