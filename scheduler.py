import os.path

import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import discord
from discord.ext import tasks
import requests

import os 
from dotenv import load_dotenv
load_dotenv()

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

# The ID and range of a sample spreadsheet.
SAMPLE_SPREADSHEET_ID = "1jhAGP9f5k5g5kjfDCwiJiLWZLg0xuJb18dF1t34PXR8"
SAMPLE_RANGE_NAME = "Times"


def get_values():
  """Shows basic usage of the Sheets API.
  Prints values from a sample spreadsheet.
  """
  creds = None
  # The file token.json stores the user's access and refresh tokens, and is
  # created automatically when the authorization flow completes for the first
  # time.
  if os.path.exists("token.json"):
    creds = Credentials.from_authorized_user_file("token.json", SCOPES)
  # If there are no (valid) credentials available, let the user log in.
  if not creds or not creds.valid:
    if creds and creds.expired and creds.refresh_token:
      creds.refresh(Request())
    else:
      flow = InstalledAppFlow.from_client_secrets_file(
          "credentials.json", SCOPES
      )
      creds = flow.run_local_server(port=0)
    # Save the credentials for the next run
    with open("token.json", "w") as token:
      token.write(creds.to_json())

  try:
    service = build("sheets", "v4", credentials=creds)

    # Call the Sheets API
    sheet = service.spreadsheets()
    result = (
        sheet.values()
        .get(spreadsheetId=SAMPLE_SPREADSHEET_ID, range=SAMPLE_RANGE_NAME)
        .execute()
    )
    values = result.get("values", [])

    if not values:
      print("No data found.")
      return
    return values

  except HttpError as err:
    print(err)
    return None

# from the .env load the 

# Deletes all messages in a specific chat
async def purge_channel(bot):
    guild = bot.guilds[0]  # Adjust this if your bot is in multiple servers
    channel = discord.utils.get(guild.text_channels, name="jabber-shift-chat")
    await channel.purge(limit=1000)
    await channel.send("The Jabber-Shift-Chat channel has been cleared.")

    await daily_commands(bot)

# sends a message in the #printer-checks channel to remind us to check printers
async def printer_check(bot):
    guild = bot.guilds[0]
    channel = discord.utils.get(guild.text_channels, name="printer-checks")
    await channel.send("Please check the printers")

# Schedule printer checks for Monday through Friday
async def schedule_printer_check(bot, scheduler, days, times, enabled):
    days = days.split(",")
    times = times.split(",")

    times = [float(time) for time in times]
    
    if enabled == "FALSE":
      print("Printer Checks Not Scheduled")

    else:
      for day in days:
        for time in times:
          minutes = 0
          if float(time) % 1 != 0:
            minutes = int((float(time) % 1) * 60)
          time = int(time)
          scheduler.add_job(printer_check, 'cron', day_of_week=day, hour=time, minute=minutes, misfire_grace_time=60, args=[bot])
      print("Printer Checks Scheduled")
  

# Schedule incidents to be checked at specific times
async def schedule_get_incidents(bot, scheduler, days, times, enabled):
    days = days.split(",")
    times = times.split(",")
    
    times = [float(time) for time in times]
    if enabled == "FALSE":
      print("Incidents Not Scheduled")
    else:
      for day in days:
        for time in times:
          minutes = 0
          if float(time) % 1 != 0:
            minutes = int((float(time) % 1) * 60)
          time = int(time)
          scheduler.add_job(get_incidents, 'cron', day_of_week=day, hour=time, minute=minutes, misfire_grace_time=60, args=[bot])
      print("Incidents Scheduled")

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
    scheduler.add_job(purge_channel, 'cron', hour=0, minute=1, misfire_grace_time=60, args=[bot])


# Gives a list of commands to be run daily
async def daily_commands(bot):
    
    scheduler = AsyncIOScheduler(event_loop=bot.loop, timezone='America/New_York')

    # clear scheduler
    if scheduler.running:
        scheduler.shutdown(wait=False)
    scheduler.remove_all_jobs()

    values = get_values()

    if values:
        times = values[1:]
    else:
        times = []

    for time in times:
        if time[1] == "printer_checks":
          await schedule_printer_check(bot, scheduler, time[2], time[3], time[0])
        elif time[1] == "email_check_weekly" or time[1] == "email_check_friday" or time[1] == "email_check_weekend":
          await schedule_get_incidents(bot, scheduler, time[2], time[3], time[0])
        else:
          print("Invalid command from time sheet")
    
    await schedule_daily_purge(bot, scheduler)
    await schedule_refresh(bot, scheduler)
    scheduler.start()
    # print all scheduled commands
    scheduler.print_jobs()
    print("Scheduled Commands")
