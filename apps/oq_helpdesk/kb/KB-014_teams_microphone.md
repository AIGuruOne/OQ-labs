---
kb_id: KB-014
title: Nobody can hear you in Teams
category: software
routing_queue: end_user_computing
systems: Teams, Windows
updated: 2026-09-29
---

# Nobody can hear you in Teams

## Symptom
In **Teams** the other side cannot hear you, while the microphone works in other applications.

## The usual cause
Teams holds its own device selection, separate from **Windows**. A headset that Windows is happy
with can still be the wrong device inside Teams.

## Steps
1. In Teams, open *Settings > Devices* and make a test call. Teams plays your voice back.
2. If the test call is silent, change the microphone in that same panel and test again. Work
   through every device listed before concluding it is broken.
3. Check the physical mute switch on the headset cable. This is a surprisingly common answer.
4. Sign out of Teams and back in. Device selection is cached and a stale cache survives a restart
   of the application but not a sign-out.

## Still silent
Raise a ticket to `end_user_computing`, and say whether the Teams *test call* was silent too. That
single fact separates a Teams problem from a hardware one and saves a day.
