---
name: booking-lookup-window
description: Check whether a voice assistant's lookup tool went silent inside a time window. Use when call exports show bookings failing while call volume looks normal. Not for single-call debugging.
license: MIT
metadata:
  schema_version: "1"
  record_type: diagnostic
---

# booking-lookup-window

Count lookup-tool attempts inside a UTC window of a call export. Zero attempts with normal
call volume points at a disabled tool, not at callers.

## Procedure
1. Export the calls for the day as JSON (one object per call with `start_utc` and `tool_calls`).
2. Run `python3 scripts/check_window.py <export.json> <HH:MM> <HH:MM>`.
3. `OK` with a count above zero means the tool was reachable; `SILENT` means no attempts.

## Known counterexamples
- Calls routed to a different assistant also show zero attempts; check routing first.
