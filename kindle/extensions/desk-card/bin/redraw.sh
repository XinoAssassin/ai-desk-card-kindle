#!/bin/sh
# Force an immediate redraw using the last cached frame (no fetch).
[ -f /tmp/card.png ] && /usr/sbin/eips -f -g /tmp/card.png
