#!/bin/bash

set -e

WORK_DIR="simple_proj/_yagua_work_"

# Remove work directory if it exists
if [ -d "$WORK_DIR" ]; then
    echo "Removing existing work directory..."
    rm -rf "$WORK_DIR"
fi

# Create project
echo "Creating project..."
yagua create-project simple_proj "$WORK_DIR" \
    --name "simple" \
    --description "A simple project with basic arithmetic operations"

# Collect tests
echo "Collecting tests..."
yagua collect-tests "$WORK_DIR"

# Collect coverage
echo "Collecting coverage..."
yagua collect-coverage "$WORK_DIR"

# Collect mutations
echo "Collecting mutations..."
yagua collect-mutations "$WORK_DIR"

# List tests
echo "Listing tests..."
yagua list-tests "$WORK_DIR" --long

# Show info
echo "Showing project info..."
yagua info "$WORK_DIR"

echo "Done!"
