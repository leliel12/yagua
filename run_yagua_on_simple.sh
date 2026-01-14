#!/bin/bash

set -e

WORK_DIR="simple_proj/_yagua_work_"

# Remove work directory if it exists
if [ -d "$WORK_DIR" ]; then
    echo "Removing existing work directory..."
    rm -rf "$WORK_DIR"
fi

# Initialize project
echo "Initializing project..."
yagua init simple_proj "$WORK_DIR" \
    --name "simple" \
    --description "A simple project with basic arithmetic operations" \
    --mutation-timeout 50.0

# Run the pipeline (collects tests, coverage, and mutations)
echo "Running pipeline..."
yagua run "$WORK_DIR" -r

# Show project status
echo "Showing project status..."
yagua status "$WORK_DIR"

# Show project report
echo "Showing project report..."
yagua report "$WORK_DIR"

echo "Done!"
