#!/bin/bash
set -e  # Exit on error

# Configuration
PROJECT_PATH="${1:-/path/to/astroalign}"
WORK_DIR="${2:-astroalign_work}"
PROJECT_NAME="AstroAlign"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Yagua Data Collection for AstroAlign${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Validate project path
if [ ! -d "$PROJECT_PATH" ]; then
    echo -e "${RED}Error: Project path '$PROJECT_PATH' does not exist${NC}"
    echo "Usage: $0 <project_path> [work_dir]"
    echo "Example: $0 /home/user/astroalign astroalign_work"
    exit 1
fi

echo -e "${GREEN}[1/5] Creating project...${NC}"
yagua create-project "$PROJECT_PATH" "$WORK_DIR" --name "$PROJECT_NAME"
echo ""

echo -e "${GREEN}[2/5] Collecting tests...${NC}"
yagua collect-tests "$WORK_DIR"
echo ""

echo -e "${GREEN}[3/5] Collecting coverage data...${NC}"
yagua collect-coverage "$WORK_DIR"
echo ""

echo -e "${GREEN}[4/5] Collecting mutation data...${NC}"
echo -e "${BLUE}(This may take a while)${NC}"
yagua collect-mutations "$WORK_DIR"
echo ""

echo -e "${GREEN}[5/5] Showing collected information...${NC}"
yagua info "$WORK_DIR"
echo ""

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Data collection completed!${NC}"
echo -e "${GREEN}========================================${NC}"
echo -e "Work directory: ${BLUE}$WORK_DIR${NC}"
echo -e "Database: ${BLUE}$WORK_DIR/yagua.db${NC}"
echo ""
echo "To view detailed test information:"
echo "  yagua list-tests $WORK_DIR --long"
