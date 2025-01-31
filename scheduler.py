import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import discord
from discord.ext import tasks
import requests

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

# Schedule printer checks for Monday through Friday
async def schedule_printer_check(bot, scheduler):
    days_of_week = ['mon', 'tue', 'wed', 'thu', 'fri']
    print("Printer Checks Scheduled")
    # Printer checks set for 8:00 am, 12:00 pm, and 4:30 pm
    for day in days_of_week:
        scheduler.add_job(printer_check, 'cron', day_of_week=day, hour=8, minute=0, misfire_grace_time=60, args=[bot, "1"])
        scheduler.add_job(printer_check, 'cron', day_of_week=day, hour=12, minute=0, misfire_grace_time=60, args=[bot, "2"])
        scheduler.add_job(printer_check, 'cron', day_of_week=day, hour=4, minute=30, misfire_grace_time=60, args=[bot, "2"])

# Schedule incidents to be checked at specific times
async def schedule_get_incidents(bot, scheduler):
    print("Incidents Scheduled")
    days_of_week = ['mon', 'tue', 'wed', 'thu',]
    weekend = ['sat', 'sun']

    # Check incidents at 8, 10, 12 , 14, 16, and 18
    for day in days_of_week:
        scheduler.add_job(get_incidents, 'cron', day_of_week=day, hour=8, minute=0, misfire_grace_time=60, args=[bot])
        scheduler.add_job(get_incidents, 'cron', day_of_week=day, hour=10, minute=0, misfire_grace_time=60, args=[bot])
        scheduler.add_job(get_incidents, 'cron', day_of_week=day, hour=12, minute=0, misfire_grace_time=60, args=[bot])
        scheduler.add_job(get_incidents, 'cron', day_of_week=day, hour=14, minute=0, misfire_grace_time=60, args=[bot])
        scheduler.add_job(get_incidents, 'cron', day_of_week=day, hour=16, minute=0, misfire_grace_time=60, args=[bot])
        scheduler.add_job(get_incidents, 'cron', day_of_week=day, hour=18, minute=0, misfire_grace_time=60, args=[bot])

    #on fridays only 8, 10, 12, 14, 16
    scheduler.add_job(get_incidents, 'cron', day_of_week='fri', hour=8, minute=0, misfire_grace_time=60, args=[bot])
    scheduler.add_job(get_incidents, 'cron', day_of_week='fri', hour=10, minute=0, misfire_grace_time=60, args=[bot])
    scheduler.add_job(get_incidents, 'cron', day_of_week='fri', hour=12, minute=0, misfire_grace_time=60, args=[bot])
    scheduler.add_job(get_incidents, 'cron', day_of_week='fri', hour=14, minute=0, misfire_grace_time=60, args=[bot])
    scheduler.add_job(get_incidents, 'cron', day_of_week='fri', hour=16, minute=0, misfire_grace_time=60, args=[bot])

    # on weekends only 10, 12, 14
    scheduler.add_job(get_incidents, 'cron', day_of_week='sat', hour=10, minute=0, misfire_grace_time=60, args=[bot])
    scheduler.add_job(get_incidents, 'cron', day_of_week='sat', hour=12, minute=0, misfire_grace_time=60, args=[bot])
    scheduler.add_job(get_incidents, 'cron', day_of_week='sat', hour=14, minute=0, misfire_grace_time=60, args=[bot])

# Schedule a refresh of the page every 30 minutes
async def schedule_refresh(bot, scheduler):
    # refresh every 30 min
    print("Refresh Scheduled")
    scheduler.add_job(refresh_page, 'interval', minutes=30, misfire_grace_time=60, args=[bot])

# Refresh the page
async def refresh_page(bot):
    # Call the refresh endpoint
    requests.get("http://127.0.0.1:5000/refresh")

# Get the number of incidents
async def get_incidents(bot):
    guild = bot.guilds[0]  # Adjust this if your bot is in multiple servers
    channel = discord.utils.get(guild.text_channels, name="jabber-shift-chat")
    # Get number of incidents
    incidents_resp = requests.get("http://127.0.0.1:5000/incidents")
    if incidents_resp.status_code == 200:
        data = incidents_resp.json()
        incident_count = data.get("incident_count")
        await channel.send(f"We have {incident_count} new emails")
    else:
        print("Incident check failed:", incidents_resp.text)

# Schedule a daily purge of the channel
async def schedule_daily_purge(bot, scheduler):
    # Purge set for 12:01 am
    print("Purge Scheduled")
    scheduler.add_job(purge_channel, 'cron', hour=10, minute=8, misfire_grace_time=60, args=[bot])


# Gives a list of commands to be run daily
async def daily_commands(bot):
    health_resp = requests.get("http://127.0.0.1:5000/health")
    if health_resp.status_code == 200:
        print("Health check:", health_resp.json())
    else:
        print("Health check failed:", health_resp.text)

    scheduler = AsyncIOScheduler(event_loop=bot.loop, timezone='America/New_York')
    await schedule_daily_purge(bot, scheduler)
    await schedule_printer_check(bot, scheduler)
    await schedule_get_incidents(bot, scheduler)
    await schedule_refresh(bot, scheduler)
    scheduler.start()
    print("Scheduled Commands")

