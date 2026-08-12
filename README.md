# ITSD Bot

ITSD Bot is a Discord bot built to support an IT service desk team. It manages the student support queue, checks ServiceNow incidents, answers questions using internal knowledge-base content, and handles routine announcements and maintenance tasks.

## Full documentation

Detailed setup, configuration, and usage guidance is available in the [project documentation](https://docs.google.com/document/d/1q_PKG2UIqPPKJaGQdANExJr001zb3RfzkOPNffXHDNA/edit?usp=sharing).

## Setup

From the `ITSD` directory, create a virtual environment and install the dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create a `.env` file with the Discord, ServiceNow, LLM backend, and image-model settings used by the application:

```env
DISCORD_TOKEN=
DM_USER=

LLM_BACKEND_URL=
LLM_BACKEND_API_KEY=
LLM_BACKEND_WORKSPACE=

instance=
SN_USERNAME=
CLIENT_ID=
CLIENT_SECRET=

API_BASE=
ITSD_DEV_MODEL_HAIKU=
ITSD_DEV_API_KEY=
```

This repository includes the Discord bot and its integrations, but not the LLM/RAG backend. Configure the `LLM_BACKEND_*` settings to connect to an available backend instance.

The Google Calendar scheduler requires `credentials.json`. The first run creates `token.json`; ServiceNow authentication creates `refresh.token`.

Run the bot with:

```bash
python3 bot.py
```

## Common commands

| Command | Purpose |
| --- | --- |
| `!queue` / `!q` | Show the current support queue. |
| `!join`, `!leave`, `!add`, `!remove` | Manage people in the queue. |
| `!search <question>` | Ask a question using the internal knowledge base. |
| `!incidents` | Check the number of new ServiceNow incidents. |
| `!docs_upload` | Refresh knowledge-base documents and upload them to the LLM backend. |
| `!teach <suggestion>` | Submit a knowledge-base suggestion for review. |
| `!events_help` | View instructions for calendar-based scheduling. |
| `!help` | View all commands. |
