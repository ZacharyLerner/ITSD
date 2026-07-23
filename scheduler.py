import os
import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from zoneinfo import ZoneInfo
from servicenow import reuploadAll
import discord

from dotenv import load_dotenv
load_dotenv()

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from servicenow import get_access_token, incident_query

# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]

CALENDAR_ID = "oldhelpdesk@etal.uri.edu"
TIMEZONE = "America/New_York"

DAY_MAP = {
    0: "mon",
    1: "tue",
    2: "wed",
    3: "thu",
    4: "fri",
    5: "sat",
    6: "sun",
}

VALID_COMMANDS = {
    "email_check",
    "reupload_docs"
}

DEFAULT_CHANNEL = "jabber-shift-chat"

def get_values():
    """Reads upcoming Calendar events and converts them to scheduler entries."""
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
        service = build("calendar", "v3", credentials=creds)

        now = datetime.datetime.now(datetime.timezone.utc)
        end = now + datetime.timedelta(days=4)

        result = service.events().list(
            calendarId=CALENDAR_ID,
            timeMin=now.isoformat(),
            timeMax=end.isoformat(),
            singleEvents=True,
            orderBy="startTime",
        ).execute()

        events = result.get("items", [])
        if not events:
            print("No data found.")
            return []

        entries = []
        seen_commands = set()
        for event in events:
            command_name = event.get("summary", "").strip()

            start = event.get("start", {})
            start_text = start.get("dateTime")
            if not start_text:
                continue

            event_time = datetime.datetime.fromisoformat(start_text.replace("Z", "+00:00"))
            event_time = event_time.astimezone(ZoneInfo(TIMEZONE))

            day = DAY_MAP[event_time.weekday()]
            hour = event_time.hour
            minute = event_time.minute

            if command_name not in VALID_COMMANDS:
                message = event.get("description", "").strip()
                channel_name = event.get("location", "").strip().lstrip("#") or DEFAULT_CHANNEL
                if not message:
                    continue

                command_key = ("custom_message", day, hour, minute, message, channel_name)
                if command_key in seen_commands:
                    continue

                seen_commands.add(command_key)
                entries.append({
                    "command_name": "custom_message",
                    "day": day,
                    "hour": hour,
                    "minute": minute,
                    "message": message,
                    "channel_name": channel_name,
                })
                continue

            command_key = (command_name, day, hour, minute)
            if command_key in seen_commands:
                continue

            seen_commands.add(command_key)
            entries.append({
                "command_name": command_name,
                "day": day,
                "hour": hour,
                "minute": minute,
            })

        return entries
    except HttpError as err:
        print(err)
        return None
    

async def delete_vem():
    if os.path.exists("data/vem.json"):
        os.remove("data/vem.json")

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

async def get_incidents(bot):
    inc_num = incident_query(get_access_token())
    guild = bot.guilds[0]
    channel = discord.utils.get(guild.text_channels, name="jabber-shift-chat")
    if inc_num == 0:
        await channel.send(f"https://cdn.discordapp.com/attachments/1451255048553234534/1522303059865374811/IMG_9304-ezgif.com-added-text1.gif?ex=6a47fab4&is=6a46a934&hm=8dfe196e97ce2ae18f5e90df9193c97fa1a08ccfa5db54ec283a319d127af90c&")
    else:
        await channel.send(f"We have {inc_num} new emails")

async def send_custom_message(bot, message, channel_name = DEFAULT_CHANNEL):
    guild = bot.guilds[0]
    channel_name = channel_name.strip().lstrip("#") or DEFAULT_CHANNEL
    channel = discord.utils.get(guild.text_channels, name=channel_name)
    if channel is None:
        channel = discord.utils.get(guild.text_channels, name=DEFAULT_CHANNEL)
    await channel.send(message)

async def schedule_get_incidents(bot, scheduler, day, hour, minute):
    """Schedules an incident-check job for one Calendar event."""
    scheduler.add_job(
        get_incidents,
        'cron',
        day_of_week=day,
        hour=hour,
        minute=minute,
        misfire_grace_time=60,
        args=[bot]
    )
    print("Incident Scheduled")

async def schedule_reupload_docs(scheduler, day, hour, minute):
    """Schedules a document reupload job"""
    scheduler.add_job(
        reuploadAll,
        'cron',
        day_of_week=day,
        hour=hour,
        minute=minute,
        misfire_grace_time=60
    )
    print("docs reuploaded")


async def schedule_custom_message(bot, scheduler, day, hour, minute, message, channel_name):
    """Schedules a custom Calendar-description message."""
    scheduler.add_job(
        send_custom_message,
        'cron',
        day_of_week=day,
        hour=hour,
        minute=minute,
        misfire_grace_time=60,
        args=[bot, message, channel_name]
    )

async def schedule_daily_purge(bot, scheduler):
    """Schedules a daily purge of the #jabber-shift-chat channel at 12:01 AM."""
    print("Purge Scheduled")
    scheduler.add_job(purge_channel, 'cron', hour=0, minute=1, misfire_grace_time=60, args=[bot])
    scheduler.add_job(delete_vem, 'cron', hour=0, minute=1, misfire_grace_time=60)

async def daily_commands(bot):
    """
    This function:
    - Grabs or creates the single scheduler stored on the bot.
    - Removes all old jobs (so the schedule is 'reset').
    - Reads Google Calendar for new times and schedules them.
    - Schedules the daily purge.
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

    # Fetch scheduled entries from Google Calendar
    entries = get_values() or []

    # Schedule each command from the calendar
    for entry in entries:
        command_name = entry["command_name"]
        if command_name == 'email_check':
            await schedule_get_incidents(
                bot,
                scheduler,
                entry["day"],
                entry["hour"],
                entry["minute"],
            )
        elif command_name == 'reupload_docs':
            await schedule_reupload_docs(
                scheduler,
                entry["day"],
                entry["hour"],
                entry["minute"],
            )
            print("Reupload Scheduled")
        elif command_name == "custom_message":
            await schedule_custom_message(
                bot,
                scheduler,
                entry["day"],
                entry["hour"],
                entry["minute"],
                entry["message"],
                entry["channel_name"],
            )
        else:
            print("Invalid command from calendar:", command_name)

    await schedule_daily_purge(bot, scheduler)
    
    # If the scheduler wasn't started yet, start it
    if not scheduler.running:
        scheduler.start()

    # Debug log: print all scheduled jobs
    scheduler.print_jobs()
    print("Scheduled Commands")
