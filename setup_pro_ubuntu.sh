#!/usr/bin/env bash
set -e

echo "== Updating system =="
sudo apt update
sudo apt upgrade -y

echo "== Installing core developer tools =="
sudo apt install -y \
  git curl wget ca-certificates gnupg lsb-release software-properties-common \
  build-essential make cmake pkg-config \
  unzip zip tar xz-utils \
  htop btop tree jq ripgrep fd-find \
  nano vim

echo "== Installing Python production stack =="
sudo apt install -y \
  python3 python3-pip python3-venv python3-dev \
  pipx

echo "== Installing audio/voice dependencies =="
sudo apt install -y \
  portaudio19-dev python3-pyaudio \
  ffmpeg sox alsa-utils pulseaudio-utils \
  libasound2-dev libsndfile1

echo "== Installing web/API/database tools =="
sudo apt install -y \
  sqlite3 libsqlite3-dev \
  redis-server \
  nginx \
  openssl

echo "== Installing browser/UI/graphics support =="
sudo apt install -y \
  mesa-utils mesa-vulkan-drivers \
  libgl1 libglib2.0-0 libsm6 libxext6 libxrender1 \
  fonts-dejavu fonts-noto-color-emoji

echo "== Installing security and networking tools =="
sudo apt install -y \
  ufw fail2ban \
  net-tools dnsutils iputils-ping traceroute nmap \
  openssh-client openssh-server

echo "== Installing container tools =="
sudo apt install -y \
  docker.io docker-compose-v2

echo "== Enabling services =="
sudo systemctl enable --now docker
sudo systemctl enable --now redis-server
sudo systemctl enable --now ssh

echo "== Adding user to docker group =="
sudo usermod -aG docker "$USER"

echo "== Installing Python CLI tools with pipx =="
pipx ensurepath
pipx install black || true
pipx install ruff || true
pipx install mypy || true
pipx install poetry || true
pipx install httpie || true

echo "== Configuring npm global path =="
mkdir -p "$HOME/.npm-global"
npm config set prefix "$HOME/.npm-global"

if ! grep -q '.npm-global/bin' "$HOME/.bashrc"; then
  echo 'export PATH=$HOME/.npm-global/bin:$PATH' >> "$HOME/.bashrc"
fi

echo "== Creating professional project folders =="
mkdir -p "$HOME/Projects" "$HOME/Clients" "$HOME/Backups" "$HOME/.local/bin"

echo "== Done =="
echo "IMPORTANT: restart terminal or run: source ~/.bashrc"
echo "IMPORTANT: logout/login once for Docker group permission."
