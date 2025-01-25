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

# sends a message in the #printer-checks channel to remind us to check printers
async def printer_check(bot,time):
    guild = bot.guilds[0]
    channel = discord.utils.get(guild.text_channels, name="printer-checks")
    if time == "1":
        await channel.send("Please check the printers")
    else:
        await channel.send("Please check the printers if they have not been checked recently")

async def schedule_printer_check(bot, scheduler):
    days_of_week = ['mon', 'tue', 'wed', 'thu', 'fri']
    print("Printer Checks Scheduled")
    # Printer checks set for 8:00 am, 12:00 pm, and 4:30 pm
    for day in days_of_week:
        scheduler.add_job(printer_check, 'cron', day_of_week=day, hour=8, minute=0, misfire_grace_time=60, args=[bot, "1"])
        scheduler.add_job(printer_check, 'cron', day_of_week=day, hour=12, minute=0, misfire_grace_time=60, args=[bot, "2"])
        scheduler.add_job(printer_check, 'cron', day_of_week=day, hour=4, minute=30, misfire_grace_time=60, args=[bot, "2"])

async def schedule_daily_purge(bot, scheduler):
    # Purge set for 12:01 am
    print("Purge Scheduled")
    scheduler.add_job(purge_channel, 'cron', hour=12, minute=1, misfire_grace_time=60, args=[bot])

# Gives a list of commands to be run daily
async def daily_commands(bot):
    scheduler = AsyncIOScheduler(event_loop=bot.loop, timezone='America/New_York')
    await schedule_daily_purge(bot, scheduler)
    await schedule_printer_check(bot, scheduler)
    scheduler.start()
    print("Scheduled Commands")