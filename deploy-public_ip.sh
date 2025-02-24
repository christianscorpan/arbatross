#!/bin/bash

# Exit on any error
set -e

# Vars
APP_DIR="/home/$(whoami)/price-compare"
APP_NAME="price-compare-app"
PORT=8000
GIT_REPO="https://github.com/christianscorpan/arbatross.git"

echo "Starting easy Docker deployment with Git..."

# Install deps
sudo apt update -y
sudo apt install -y docker.io nginx git
sudo systemctl start docker && sudo systemctl enable docker

# Git stuff
if [ -d "$APP_DIR" ]; then
    echo "Forcing update in $APP_DIR..."
    cd "$APP_DIR"
    git fetch origin
    git reset --hard origin/main
else
    echo "Cloning repo to $APP_DIR..."
    git clone "$GIT_REPO" "$APP_DIR"
    cd "$APP_DIR"
fi

# Docker stuff
echo "Building and running Docker..."
sudo docker build -t $APP_NAME .
sudo docker stop $APP_NAME 2>/dev/null || true
sudo docker rm $APP_NAME 2>/dev/null || true
sudo docker run -d --name $APP_NAME -p $PORT:$PORT $APP_NAME

# Get public IP
PUBLIC_IP=$(curl -4 icanhazip.com)
echo "Using public IP: $PUBLIC_IP for Nginx..."

# Define Nginx config with proper escaping
NGINX_CONFIG="server {
    listen 80;
    server_name $PUBLIC_IP;

    location / {
        proxy_pass http://localhost:$PORT;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    }

    location /ws {
        proxy_pass http://localhost:$PORT;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection \"upgrade\";
        proxy_set_header Host \$host;
        proxy_read_timeout 3600;
    }
}"

# Debug: Print the config
echo "Debug: Nginx config to be written:"
echo "$NGINX_CONFIG"
echo "Debug: Line 7 specifically:"
echo "$NGINX_CONFIG" | sed -n '7p'

# Write Nginx config
echo "Configuring Nginx..."
echo "$NGINX_CONFIG" | sudo tee /etc/nginx/sites-available/$APP_NAME > /dev/null

# Enable and restart Nginx
sudo ln -sf "/etc/nginx/sites-available/$APP_NAME" /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl restart nginx

# Firewall
echo "Setting up firewall..."
sudo ufw allow 80/tcp
sudo ufw allow 22/tcp
sudo ufw --force enable

echo "Deployment done! Hit http://$PUBLIC_IP in your browser."