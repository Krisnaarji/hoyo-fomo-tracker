# HoYo FOMO Tracker

A lightweight Raspberry Pi-based event tracker and anti-FOMO dashboard for HoYoverse games:

- Genshin Impact
- Honkai: Star Rail
- Zenless Zone Zero

The system tracks active events, categorizes them by urgency, and sends reminders to prevent last-minute event speedrunning.

## Goals

- Track HoYoverse events from official notices, wikis, or community summaries.
- Classify events into Heavy/Lore, Speedrun-able, or Daily Login.
- Run on low-power local hardware.
- Minimize disk writes to protect SD card lifespan.
- Provide API access for Discord and Android clients.

## Hardware

- Raspberry Pi 3B V1.2
- Raspberry Pi OS Lite 32-bit
- 1GB RAM
- 8GB microSD card

## Planned Stack

- Python 3
- FastAPI
- SQLite
- BeautifulSoup4
- DeepSeek API
- discord.py
- React Native + Expo
- Firebase Cloud Messaging

## Project Status

Initial backend setup in progress.

## Architecture

```text
Raspberry Pi 3B
├── FastAPI API
├── SQLite database
├── Scraper jobs
├── DeepSeek event classifier
├── Discord bot
└── Android app client```

Notes

This project is designed with low-resource and SD-card-friendly constraints in mind.
