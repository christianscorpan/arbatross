#!/bin/bash

# Exit on any error
set -e

# Vars
APP_DIR="/home/$(whoami)/price-compare"
APP_NAME="price-compare-app"
PORT=8000
GIT_REPO="https://github.com/yourusername/price-compare.git"  # Swap with your repo URL

echo "Starting Docker deployment with Git..."

# Install deps
sudo apt update -y
sudo apt install -y docker.io nginx git
sudo systemctl start docker
sudo systemctl enable docker

# Clone or pull repo
if [ -d "$APP_DIR" ]; then
    echo "Updating existing repo in $APP_DIR..."
    cd "$APP_DIR"
    git pull origin main
else
    echo "Cloning repo to $APP_DIR..."
    git clone "$GIT_REPO" "$APP_DIR"
    cd "$APP_DIR"
fi

# Build Docker image
echo "Building Docker image..."
sudo docker build -t $APP_NAME .

# Stop and remove old container if exists
sudo docker stop $APP_NAME 2>/dev/null || true
sudo docker rm $APP_NAME 2>/dev/null || true

# Run new container
echo "Running Docker container..."
sudo docker run -d --name $APP_NAME -p $PORT:$PORT $APP_NAME

# Get public IP for Nginx
PUBLIC_IP=$(curl -4 icanhazip.com)
echo "Using public IP: $PUBLIC_IP for Nginx..."

# Set up Nginx
echo "Configuring Nginx..."
sudo bash -c "cat > /etc/nginx/sites-available/$APP_NAME <<EOF
server {
    listen 80;
    server_name $PUBLIC_IP;  # Use dynamic public IP

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
    }
}
EOF"

# Enable Nginx config
sudo ln -sf "/etc/nginx/sites-available/$APP_NAME" /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl restart nginx
echo "Nginx configured and restarted."

# Open firewall
echo "Setting up firewall..."
sudo ufw allow 80/tcp
sudo ufw allow 22/tcp
sudo ufw --force enable

echo "Deployment done! Hit http://$PUBLIC_IP in your browser."
echo "Check container logs with: sudo docker logs $APP_NAME"