---
name: personal-calendar
description: >
  Use when a question needs Bryan's personal schedule: flights, trips, family
  events, appointments, anything outside work. Reads his iCloud calendars on
  this Mac. His Google Calendar (Agile6) is work only and never holds personal
  plans.
---

# Personal calendar

Bryan's personal life is in **iCloud Calendar**, read through macOS EventKit
on his Mac. The calendars are `Bryan` (his own: flights, trips,
appointments), `Family` and `Traci`.

**Don't use `gws calendar` or any Google Calendar for personal questions.**
The Google account `bryan.thompson@agile6.com` is his work calendar. It may
show placeholders such as "OOO - Flying", but those leave out the flight
numbers, times and places (Bryan, 2026-11-20, after an agent searched Google
for his flights).

## Read events

    swift ~/.agents/skills/personal-calendar/scripts/events.swift START END [QUERY]

- `START` and `END` are ISO 8601 with an offset, e.g. `2026-11-24T00:00:00-08:00`.
- `QUERY` is optional. It matches the title, location or notes without regard
  to case (e.g. `flight`, `UA`, `SFO`).
- The script reads only the iCloud calendars and prints Pacific times. It
  takes about 10 to 20 seconds to compile on first run.

Airline imports appear as `Flight  UA702 RDM to SFO` on the `Bryan` calendar,
with the confirmation number in the notes. The calendar's times are when the
event is scheduled, not live status. For delays, check the airline or FlightAware.

If EventKit says access was denied, the terminal app has no Calendar
permission. Tell Bryan to grant it in System Settings › Privacy & Security ›
Calendars. Never fall back to Google Calendar.
