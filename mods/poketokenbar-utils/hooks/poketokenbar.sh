#!/bin/sh
# PokeTokenBar agent hook: sh poketokenbar.sh <working|waiting|done|idle>
# Labels the agent with the project folder name, percent-encoded (perl ships with macOS).
# Source: https://github.com/chattymin/PokeTokenBar#agent-activity
pgrep -xq PokeTokenBar || exit 0
label=$(printf %s "${CLAUDE_PROJECT_DIR##*/}" | perl -pe 's/([^A-Za-z0-9._~-])/sprintf("%%%02X", ord $1)/ge')
open -g "poketokenbar://agent?state=$1&label=$label" >/dev/null 2>&1
exit 0
