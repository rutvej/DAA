#!/usr/bin/env bash
# ==============================================================================
# DAA Platform Unified Installation Script
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
echo -e "  Deduplicated Autonomous Agent"
echo -e "${RESET}"
echo -e "${BOLD}Starting DAA Platform installation...${RESET}"
echo "--------------------------------------------------------"

# OS Detection
OS_TYPE="$(uname -s)"
case "${OS_TYPE}" in
    Linux*)     OS="Linux";;
    Darwin*)    OS="Mac";;
    CYGWIN*|MINGW*|MSYS*) OS="Windows";;
    *)          OS="Unknown"
esac

echo -e "Detected Operating System: ${CYAN}${OS}${RESET}"

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

check_compose() {
    if command -v docker-compose &> /dev/null; then
        echo -e "${GREEN}✔${RESET} docker-compose is installed."
        return 0
    elif docker compose version &> /dev/null; then
        echo -e "${GREEN}✔${RESET} docker compose plugin is installed."
        return 0
    else
        echo -e "${RED}✖ Error: Docker Compose is required but not installed.${RESET}"
        return 1
    fi
}

MISSING_DEPS=0
check_cmd "docker" || MISSING_DEPS=1
check_compose || MISSING_DEPS=1
check_cmd "python3" || MISSING_DEPS=1
check_cmd "pip3" || MISSING_DEPS=1

if [ $MISSING_DEPS -ne 0 ]; then
    echo -e "\n${YELLOW}💡 Setup Tips for Missing Dependencies:${RESET}"
    if [ "$OS" = "Mac" ]; then
        echo "  - Install Homebrew (https://brew.sh) if not installed."
        echo "  - Install Python & Pip: brew install python"
        echo "  - Install Docker Desktop for Mac: brew install --cask docker"
    elif [ "$OS" = "Linux" ]; then
        echo "  - For Debian/Ubuntu:"
        echo "      sudo apt-get update"
        echo "      sudo apt-get install -y python3 python3-pip docker.io docker-compose"
        echo "  - For CentOS/RHEL/Fedora:"
        echo "      sudo dnf install -y python3 python3-pip docker docker-compose"
    elif [ "$OS" = "Windows" ]; then
        echo "  - Running DAA directly on native Windows Git Bash is not fully supported."
        echo "  - Please install Windows Subsystem for Linux (WSL) and Docker Desktop:"
        echo "      https://docs.microsoft.com/en-us/windows/wsl/install"
    else
        echo "  - Please install Docker, Docker Compose, Python 3, and Pip for your operating system."
    fi
    exit 1
fi

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
.venv/bin/pip install -q -r requirements.txt
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

if [ -t 0 ]; then
    read -p "Would you like to run the guided setup wizard now? [Y/n]: " run_wizard < /dev/tty
else
    run_wizard="n"
fi
run_wizard=${run_wizard:-Y}

if [[ "$run_wizard" =~ ^[Yy]$ ]]; then
    .venv/bin/python3 daa init
else
    echo -e "\nSetup skipped. You can initialize DAA later by running:"
    echo -e "  ${CYAN}./daa init${RESET}"
fi
