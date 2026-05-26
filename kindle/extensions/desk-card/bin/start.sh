#!/bin/sh
# Start the desk-card poll loop. Idempotent — kills any existing poller
# (whether started manually or via upstart) before launching a fresh one.

EXT=/mnt/us/extensions/desk-card
PIDFILE=/tmp/desk-card.pid

# If upstart is managing it, ask upstart instead of fork-bombing
if [ -e /etc/upstart/kindle-desk-card.conf ]; then
  /sbin/start kindle-desk-card 2>/dev/null
  sleep 1
  /usr/sbin/eips 1 1 "Desk Card: started via upstart"
  exit 0
fi

# Manual mode (no upstart conf installed yet)
[ -f "$PIDFILE" ] && kill "$(cat "$PIDFILE")" 2>/dev/null
pkill -f "$EXT/poll.sh" 2>/dev/null
sleep 1

nohup sh "$EXT/poll.sh" > /tmp/poll.log 2>&1 &
echo $! > "$PIDFILE"
sleep 1
/usr/sbin/eips 1 1 "Desk Card: started (pid $(cat "$PIDFILE"))"
