#!/bin/bash

# Simple Coffee Making Script - Skeleton Template
# For junior devs learning to write their first scripts
# AGENT_IMPLEMENT: Fill in the script logic following the structure below

# AGENT_IMPLEMENT: Define variables for your task
CUPS=${1:-1}
# AGENT_IMPLEMENT: Add more variables as needed (e.g., COFFEE_TYPE="arabica")

echo "AGENT_IMPLEMENT: Announce what the script is doing"
echo ""

# AGENT_IMPLEMENT: Add basic checks with if/else
if [ "$CUPS" -lt 1 ]; then
  echo "AGENT_IMPLEMENT: Handle invalid input"
  CUPS=1
fi

# AGENT_IMPLEMENT: Check for prerequisites
echo "--- STEP 1: Check prerequisites ---"
if [ -f "/storage/resource_one" ]; then
  echo "✓ Resource one found"
else
  echo "✗ Resource one missing"
fi
# AGENT_IMPLEMENT: Add more prerequisite checks
echo ""

# AGENT_IMPLEMENT: Use a simple loop to perform repetitive tasks
echo "--- STEP 2: Prepare items ---"
for i in $(seq 1 "$CUPS"); do
  echo "AGENT_IMPLEMENT: Action for item $i..."
done
echo ""

# AGENT_IMPLEMENT: Add more steps following the same pattern
echo "--- STEP 3: Do something ---"
# AGENT_IMPLEMENT: Add your logic here
echo ""

# AGENT_IMPLEMENT: Final step
echo "--- STEP 4: Finish ---"
echo "AGENT_IMPLEMENT: Announce completion"
echo ""

echo "Done!"
