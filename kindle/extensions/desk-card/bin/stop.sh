#!/bin/sh
EXT=/mnt/us/extensions/desk-card
PIDFILE=/tmp/desk-card.pid

# Stop both upstart-managed and manually-launched copies, in that order
if [ -e /etc/upstart/kindle-desk-card.conf ]; then
  /sbin/stop kindle-desk-card 2>/dev/null
fi

[ -f "$PIDFILE" ] && kill "$(cat "$PIDFILE")" 2>/dev/null
rm -f "$PIDFILE"
pkill -f "$EXT/poll.sh" 2>/dev/null

/usr/sbin/eips 1 1 "Desk Card: stopped"
