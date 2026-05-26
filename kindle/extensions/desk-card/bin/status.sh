#!/bin/sh
EXT=/mnt/us/extensions/desk-card

if pgrep -f "$EXT/poll.sh" > /dev/null 2>&1; then
  # Grab the latest log line for a brief status hint
  LAST=$(tail -1 /tmp/poll.log 2>/dev/null | cut -c1-60)
  /usr/sbin/eips 1 1 "Desk Card: running"
  /usr/sbin/eips 1 2 "$LAST"
else
  /usr/sbin/eips 1 1 "Desk Card: NOT running"
fi
