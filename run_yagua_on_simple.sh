#!/bin/bash

set -e

DB_PATH="simple_proj/simple.db"
WORK_PATH="simple_proj/_work_path_"

# # Remove database if it exists
# if [ -f "$DB_PATH" ]; then
#     echo "Removing existing database..."
#     rm "$DB_PATH"
# fi

# # Remove work path if it exists
# if [ -d "$WORK_PATH" ]; then
#     echo "Removing existing work path..."
#     rm -rf "$WORK_PATH"
# fi

# # Create project
# echo "Creating project..."
# yagua create-project simple_proj "$DB_PATH" \
#     --name "simple" \
#     --description "A simple project with basic arithmetic operations" \
#     --work-path "$WORK_PATH"

# # Collect tests
# echo "Collecting tests..."
# yagua collect-tests "$DB_PATH"

# # Collect coverage
# echo "Collecting coverage..."
# yagua collect-coverage "$DB_PATH"

# Collect mutations
echo "Collecting mutations..."
yagua collect-mutations "$DB_PATH"

# List tests
echo "Listing tests..."
yagua list-tests "$DB_PATH" --long

# Show info
echo "Showing project info..."
yagua info "$DB_PATH"

echo "Done!"
