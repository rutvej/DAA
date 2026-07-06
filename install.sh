#!/usr/bin/env bash
# ==============================================================================
# DAA v2.0 Platform Unified Installation Script
# ==============================================================================
# Setup your entire SRE workspace, virtual environment, and DAA CLI in one command.
# Run: curl -fsSL http://localhost/install.sh | bash (or run locally: ./install.sh)
# ==============================================================================
set -e

# Visual formatting
BOLD="\033[1m"
GREEN="\033[92m"
YELLOW="\033[93m"
RED="\033[91m"
CYAN="\033[96m"
RESET="\033[0m"

echo -e "${CYAN}"
echo "    ██████╗  ██████╗  ██████╗ "
echo "    ██╔══██╗██╔═══██╗██╔═══██╗"
echo "    ██║  ██║███████║███████║"
echo "    ██║  ██║██╔══██║██╔══██║"
echo "    ██████╔╝██║  ██║██║  ██║"
echo "    ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝"
echo -e "  Deduplicated Autonomous Agent — v2.0"
echo -e "${RESET}"
echo -e "${BOLD}Starting DAA Platform installation...${RESET}"
echo "--------------------------------------------------------"

# 1. Check prerequisites
echo -e "\n${BOLD}Step 1: Checking System Dependencies...${RESET}"

check_cmd() {
    if ! command -v "$1" &> /dev/null; then
        echo -e "${RED}✖ Error: $1 is required but not installed.${RESET}"
        return 1
    fi
    echo -e "${GREEN}✔${RESET} $1 is installed."
    return 0
}

check_cmd "docker" || exit 1
check_cmd "docker-compose" || exit 1
check_cmd "python3" || exit 1
check_cmd "pip3" || exit 1

# 2. Virtual Environment Setup
echo -e "\n${BOLD}Step 2: Configuring Python Virtual Environment...${RESET}"
if [ ! -d ".venv" ]; then
    echo "  Creating virtual environment in .venv..."
    python3 -m venv .venv
    echo -e "${GREEN}✔${RESET} Virtual environment created."
else
    echo -e "${GREEN}✔${RESET} Virtual environment (.venv) already exists."
fi

echo "  Installing dependencies..."
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r app/python-agent/requirements.txt
.venv/bin/pip install -q requests pyjwt cryptography passlib bcrypt sqlalchemy psycopg2-binary
echo -e "${GREEN}✔${RESET} Package dependencies installed."

# 3. CLI Installation & Executable Rights
echo -e "\n${BOLD}Step 3: Installing DAA SRE CLI...${RESET}"
chmod +x daa
echo -e "${GREEN}✔${RESET} Executable permissions granted for './daa' CLI."

# Check if we should globally link
echo -e "  To run 'daa' globally from any directory, execute:"
echo -e "  ${CYAN}sudo ln -sf \$(pwd)/daa /usr/local/bin/daa${RESET}"

# 4. Prompt Setup Wizard
echo "--------------------------------------------------------"
echo -e "${GREEN}🎉 DAA Platform installation was successful!${RESET}"
echo "--------------------------------------------------------"

read -p "Would you like to run the guided setup wizard now? [Y/n]: " run_wizard
run_wizard=${run_wizard:-Y}

if [[ "$run_wizard" =~ ^[Yy]$ ]]; then
    python3 daa init
else
    echo -e "\nSetup skipped. You can initialize DAA later by running:"
    echo -e "  ${CYAN}./daa init${RESET}"
fi
