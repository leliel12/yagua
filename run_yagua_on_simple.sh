#!/bin/bash

set -e

DB_PATH="simple_proj/simple.db"

# Remove database if it exists
if [ -f "$DB_PATH" ]; then
    echo "Removing existing database..."
    rm "$DB_PATH"
fi

# Create project
echo "Creating project..."
yagua create-project simple_proj "$DB_PATH" --name "simple" --description "A simple project with basic arithmetic operations"

# Collect tests
echo "Collecting tests..."
yagua collect-tests "$DB_PATH"

# Collect coverage
echo "Collecting coverage..."
yagua collect-coverage "$DB_PATH"

# List tests
echo "Listing tests..."
yagua list-tests "$DB_PATH" --long

# Show info
echo "Showing project info..."
yagua info "$DB_PATH"

# Remove database
echo "Removing database..."
rm "$DB_PATH"

echo "Done!"
