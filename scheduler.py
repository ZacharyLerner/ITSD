import os
import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from suggestionWritter import check_values
import json

import discord
from discord.ext import tasks
import requests

from dotenv import load_dotenv
load_dotenv()

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from info.servicenow import get_access_token, incident_query

# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

SAMPLE_SPREADSHEET_ID = "1jhAGP9f5k5g5kjfDCwiJiLWZLg0xuJb18dF1t34PXR8"
SAMPLE_RANGE_NAME = "Times"

def test(bot):
    print_val = incident_query(get_access_token())
    return print_val
    

def get_values():
    """
    Shows basic usage of the Sheets API.
    Prints values from a sample spreadsheet.
    """
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                "credentials.json", SCOPES
            )
            creds = flow.run_local_server(port=0)
        with open("token.json", "w") as token:
            token.write(creds.to_json())

    try:
        service = build("sheets", "v4", credentials=creds)
        sheet = service.spreadsheets()
        result = sheet.values().get(
            spreadsheetId=SAMPLE_SPREADSHEET_ID,
            range=SAMPLE_RANGE_NAME
        ).execute()
        values = result.get("values", [])
        if not values:
            print("No data found.")
            return
        return values
    except HttpError as err:
        print(err)
        return None
    
def write_suggested_values():
  values = check_values()
  
  suggestions = []
  for value in values:
      suggestions.append(value[2])

  print(suggestions)
  current_values = []
  # get current values from additions.json
  with open('info/formattedFiles/additions.json', 'r', encoding='utf-8') as f:
    current_values = json.load(f)

  current_values.extend(suggestions)

  # Write the extracted suggestions to a JSON file in the formattedFiles directory
  output_dir = 'info/formattedFiles'
  with open(os.path.join(output_dir, 'additions.json'), 'w', encoding='utf-8') as its_file:
    json.dump(current_values, its_file, indent=4, ensure_ascii=False)


async def purge_channel(bot):
    """
    Deletes all messages in the #jabber-shift-chat channel,
    then calls daily_commands(bot) to reload schedules.
    """
    guild = bot.guilds[0]  # Adjust if the bot is in multiple servers
    channel = discord.utils.get(guild.text_channels, name="jabber-shift-chat")
    await channel.purge(limit=1000)
    await channel.send("The Jabber-Shift-Chat channel has been cleared.")

    # Rebuild the daily commands schedule with fresh data
    await daily_commands(bot)


async def printer_check(bot):
    """Sends a message in #printer-checks to remind about checking printers."""
    guild = bot.guilds[0]
    channel = discord.utils.get(guild.text_channels, name="printer-checks")
    await channel.send("Please check the printers")


async def schedule_printer_check(bot, scheduler, days, times, enabled):
    """Schedules printer checks for the given days/times if enabled."""
    days = days.split(",")
    times = times.split(",")
    times = [float(time) for time in times]

    if enabled == "FALSE":
        print("Printer Checks Not Scheduled")
    else:
        for day in days:
            for t in times:
                minutes = 0
                if t % 1 != 0:
                    minutes = int((t % 1) * 60)
                hour = int(t)
                scheduler.add_job(
                    printer_check,
                    'cron',
                    day_of_week=day,
                    hour=hour,
                    minute=minutes,
                    misfire_grace_time=60,
                    args=[bot]
                )
        print("Printer Checks Scheduled")


async def get_incidents(bot):
    inc_num = incident_query(get_access_token())
    guild = bot.guilds[0]
    channel = discord.utils.get(guild.text_channels, name="jabber-shift-chat")
    await channel.send(f"We have {inc_num} new emails")


async def schedule_get_incidents(bot, scheduler, days, times, enabled):
    """Schedules incident-check jobs for the given days/times if enabled."""
    days = days.split(",")
    times = times.split(",")
    times = [float(time) for time in times]

    if enabled == "FALSE":
        print("Incidents Not Scheduled")
    else:
        for day in days:
            for t in times:
                minutes = 0
                if t % 1 != 0:
                    minutes = int((t % 1) * 60)
                hour = int(t)
                scheduler.add_job(
                    get_incidents,
                    'cron',
                    day_of_week=day,
                    hour=hour,
                    minute=minutes,
                    misfire_grace_time=60,
                    args=[bot]
                )
        print("Incidents Scheduled")


async def refresh_page(bot):
    """Hit the /refresh endpoint to keep it alive or force a refresh."""
    requests.get("http://127.0.0.1:5000/refresh")


async def schedule_refresh(bot, scheduler):
    """Schedules a refresh of the page every 30 minutes."""
    print("Refresh Scheduled")
    scheduler.add_job(refresh_page, 'interval', minutes=30, misfire_grace_time=60, args=[bot])


async def schedule_daily_purge(bot, scheduler):
    """Schedules a daily purge of the #jabber-shift-chat channel at 12:01 AM."""
    print("Purge Scheduled")
    scheduler.add_job(purge_channel, 'cron', hour=0, minute=1, misfire_grace_time=60, args=[bot])


async def daily_commands(bot):
    """
    This function:
    - Grabs or creates the single scheduler stored on the bot.
    - Removes all old jobs (so the schedule is 'reset').
    - Reads the Google Sheet for new times and schedules them.
    - Schedules the daily purge & 30-min refresh.
    """
    # Check if we already have a scheduler on the bot
    scheduler = getattr(bot, "scheduler", None)

    # If no scheduler exists yet, create one
    if scheduler is None:
        scheduler = AsyncIOScheduler(event_loop=bot.loop, timezone="America/New_York")
        bot.scheduler = scheduler
    else:
        # If there is one, remove all existing jobs
        if scheduler.running:
            scheduler.remove_all_jobs()

    # Fetch times from Google
    values = get_values()
    if values:
        times = values[1:]  # Skip header row if present
    else:
        times = []

    # Schedule each command from the sheet
    for row in times:
        enabled, command_name, days, times_str = row[0], row[1], row[2], row[3]
        if command_name == "printer_checks":
            await schedule_printer_check(bot, scheduler, days, times_str, enabled)
        elif command_name in ["email_check_weekly", "email_check_friday", "email_check_weekend"]:
            await schedule_get_incidents(bot, scheduler, days, times_str, enabled)
        else:
            print("Invalid command from time sheet:", command_name)

    # Also schedule daily purge & 30-min refresh
    await schedule_daily_purge(bot, scheduler)
    await schedule_refresh(bot, scheduler)
    write_suggested_values()

    # If the scheduler wasn't started yet, start it
    if not scheduler.running:
        scheduler.start()

    # Debug log: print all scheduled jobs
    scheduler.print_jobs()
    print("Scheduled Commands")
