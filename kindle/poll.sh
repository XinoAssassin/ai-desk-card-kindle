#!/bin/sh
# Kindle Paperwhite 3 desk-card poll loop.
# Fetches a PNG from the Mac (via USB Ethernet) and displays it with eips.
# Run via: nohup sh /mnt/us/extensions/desk-card/poll.sh > /tmp/poll.log 2>&1 &

URL="http://192.168.15.201:9878/kindle/frame.png"
TARGET=/tmp/card.png
INTERVAL=120
EIPS=/usr/sbin/eips

# Note: we deliberately do NOT lipc-set-prop preventScreenSaver=1 — that
# property hijacks the power button on KPW3 5.14.x so the user can no
# longer manually sleep the device. After idle the screen goes to the
# system lockscreen image; the next poll cycle eips-paints our card over it.

echo "$(date) poll start  url=$URL  interval=${INTERVAL}s"

while true; do
  if wget -q -T 10 -O "$TARGET.tmp" "$URL"; then
    mv "$TARGET.tmp" "$TARGET"
    BYTES=$(wc -c < "$TARGET")
    EIPS_OUT=$("$EIPS" -f -g "$TARGET" 2>&1)
    EIPS_RC=$?
    echo "$(date) ok  bytes=$BYTES  eips_rc=$EIPS_RC  ${EIPS_OUT}"
  else
    rm -f "$TARGET.tmp"
    echo "$(date) fetch failed"
  fi
  sleep "$INTERVAL"
done
