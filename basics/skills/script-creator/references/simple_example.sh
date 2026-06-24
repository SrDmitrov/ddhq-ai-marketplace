#!/bin/bash

# Simple Coffee Making Script
# This is what a junior dev writes on their first few scripts
# NO error handling, just straightforward commands
# Shows: variables, basic if/else, simple loops, echo for important steps

CUPS=${1:-1}  # Get number of cups from argument, default to 1
COFFEE_BEANS="arabica"
WATER_TEMP=95  # Celsius

echo "Making $CUPS cup(s) of coffee..."
echo ""

# Simple if to check input
if [ "$CUPS" -lt 1 ]; then
  echo "At least 1 cup needed!"
  CUPS=1
fi

# Announce the phase
echo "--- STEP 1: Check what we need ---"
if [ -f "/storage/coffee_beans" ]; then
  echo "✓ Coffee beans found"
else
  echo "✗ Coffee beans not available"
fi

if [ -f "/storage/water" ]; then
  echo "✓ Water available"
else
  echo "✗ Water not available"
fi
echo ""

# Simple loop to prepare cups
echo "--- STEP 2: Prepare cups ---"
for i in $(seq 1 "$CUPS"); do
  echo "Preparing cup $i..."
done
echo ""

# Another loop for the brewing process
echo "--- STEP 3: Grind and brew ---"
for i in $(seq 1 "$CUPS"); do
  echo "Grinding beans for cup $i..."
  sleep 1
  echo "Brewing cup $i at ${WATER_TEMP}°C..."
  sleep 2
done
echo ""

# Final step
echo "--- STEP 4: Serve ---"
echo "Coffee is ready! Serving $CUPS cup(s)..."
echo "Enjoy your $COFFEE_BEANS coffee!"
echo ""

echo "Done!"
