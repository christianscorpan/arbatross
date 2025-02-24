#!/bin/bash

# Exit on any error
set -e

# Vars
APP_DIR="/home/$(whoami)/price-compare"
APP_NAME="price-compare-app"
PORT=8000
GIT_REPO="https://github.com/christianscorpan/arbatross.git"  # Your repo

echo "Starting easy Docker deployment with Git..."

# Install deps with error checks
sudo apt update -y || { echo "Apt update failed"; exit 1; }
sudo apt install -y docker.io nginx git || { echo "Deps install failed"; exit 1; }
sudo systemctl start docker && sudo systemctl enable docker || { echo "Docker failed"; exit 1; }

# Force Git update or clone
if [ -d "$APP_DIR" ]; then
    echo "Forcing update in $APP_DIR..."
    cd "$APP_DIR"
    git fetch origin || { echo "Git fetch failed"; exit 1; }
    git reset --hard origin/main || { echo "Git reset failed"; exit 1; }
else
    echo "Cloning repo to $APP_DIR..."
    git clone "$GIT_REPO" "$APP_DIR" || { echo "Git clone failed"; exit 1; }
    cd "$APP_DIR"
fi

# Build and run Docker
echo "Building and running Docker..."
sudo docker build -t $APP_NAME . || { echo "Docker build failed"; exit 1; }
sudo docker stop $APP_NAME 2>/dev/null || true
sudo docker rm $APP_NAME 2>/dev/null || true
sudo docker run -d --name $APP_NAME -p $PORT:$PORT $APP_NAME || { echo "Docker run failed"; exit 1; }

# Get public IP (Lightsail-specific)
PUBLIC_IP=$(curl -4 icanhazip.com)
echo "Using public IP: $PUBLIC_IP for Nginx..."

# Set up Nginx with public IP and WebSocket timeout
echo "Configuring Nginx..."
sudo bash -c "cat > /etc/nginx/sites-available/$APP_NAME <<EOF
server {
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
        proxy_read_timeout 3600s;  # Prevent WebSocket timeouts
    }
}
EOF"

# Enable and restart Nginx
sudo ln -sf "/etc/nginx/sites-available/$APP_NAME" /etc/nginx/sites-enabled/ || { echo "Nginx symlink failed"; exit 1; }
sudo nginx -t && sudo systemctl restart nginx || { echo "Nginx restart failed"; exit 1; }

# Open firewall (Lightsail handles port 80, but ensure UFW aligns)
echo "Setting up firewall..."
sudo ufw allow 80/tcp || { echo "UFW 80 failed"; exit 1; }
sudo ufw allow 22/tcp || { echo "UFW 22 failed"; exit 1; }
sudo ufw --force enable || { echo "UFW enable failed"; exit 1; }

echo "Deployment done! Hit http://$PUBLIC_IP in your browser."
echo "Check logs with: sudo docker logs $APP_NAME or sudo tail -f /var/log/nginx/error.log"