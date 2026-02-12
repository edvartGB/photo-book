# Migration Guide: Mac → WSL (Windows)

## Overview
Migrate the Taro Popsicle photo app from macOS to WSL on Windows. Both computers are on the same network. Data directory is ~804MB.

## Quick Command Reference

**Get this file on new computer:**
```bash
git clone <repo-url> taro-popsicle
cd taro-popsicle
cat MIGRATION.md  # Read this guide
```

---

## PART 1: On WSL (New Computer)

### Step 1: Install Prerequisites
```bash
# Update system packages
sudo apt update && sudo apt upgrade -y

# Install Python, build tools, and HEIF support (for Mac HEIC photos)
sudo apt install -y \
    python3 python3-pip python3-venv \
    libheif-dev libheif1 \
    libjpeg-dev zlib1g-dev \
    git openssh-server rsync

# Start SSH service (needed for receiving files)
sudo service ssh start

# Get your WSL IP address - WRITE THIS DOWN
hostname -I
# Example output: 192.168.1.100
```

### Step 2: Clone the Repository
```bash
cd ~
git clone <your-repo-url> taro-popsicle
cd taro-popsicle
```

---

## PART 2: On Mac (Old Computer)

### Step 3: Transfer Data Directory Over Network

**Using rsync (recommended - shows progress, can resume):**

```bash
cd /Users/edvart/Programming/taro-popsicle

# Replace WSL_USER with your WSL username (e.g., edvart)
# Replace WSL_IP with the IP from Step 1 (e.g., 192.168.1.100)
rsync -avz --progress data/ WSL_USER@WSL_IP:~/taro-popsicle/data/
```

**Alternative - Using scp:**

```bash
cd /Users/edvart/Programming/taro-popsicle

# Create compressed archive
tar -czf data.tar.gz data/

# Transfer to WSL (replace WSL_USER and WSL_IP)
scp data.tar.gz WSL_USER@WSL_IP:~/taro-popsicle/
```

If using scp, extract on WSL:
```bash
cd ~/taro-popsicle
tar -xzf data.tar.gz
rm data.tar.gz
```

---

## PART 3: On WSL (New Computer)

### Step 4: Set Up Python Environment

```bash
cd ~/taro-popsicle

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt
```

### Step 5: Create .env File

```bash
# Copy example and edit
cp .env.example .env
nano .env
```

Update with your configuration:
```
SECRET_KEY=oaksjgbaopejgaosj
USERNAME=edvart
PASSWORD=pudding
USERNAME2=michi
PASSWORD2=hilbert
PORT=8081
```

Save and exit: `Ctrl+O`, `Enter`, `Ctrl+X`

### Step 6: Verify Data Transfer

```bash
# Check that all directories exist and have content
ls -lh data/
# Should show: display/, photos/, photobook.db, thumbnails/, videos/, web/

# Check database exists
ls -lh data/photobook.db

# Check photo count
ls data/photos/ | wc -l

# Fix permissions if needed
chmod -R 755 data/
chmod 644 data/photobook.db
```

### Step 7: Run the Application

```bash
# Activate virtual environment if not already active
source venv/bin/activate

# Run in development mode
python app.py
```

The app should start on `http://localhost:8081`

**Access from Windows browser:**
- Get WSL IP: `hostname -I`
- Open browser to: `http://WSL_IP:8081`
- Or try: `http://localhost:8081` (if WSL2 networking is configured)

---

## OPTIONAL: Production Setup

### Run with Gunicorn (Better Performance)
```bash
source venv/bin/activate
gunicorn app:app --bind 0.0.0.0:8081 --workers 4 --threads 2 --timeout 120
```

### Auto-start on WSL Boot (systemd service)

Create service file:
```bash
sudo nano /etc/systemd/system/taro-popsicle.service
```

Add (replace `YOUR_WSL_USERNAME` with your username):
```ini
[Unit]
Description=Taro Popsicle Photo App
After=network.target

[Service]
User=YOUR_WSL_USERNAME
WorkingDirectory=/home/YOUR_WSL_USERNAME/taro-popsicle
Environment="PATH=/home/YOUR_WSL_USERNAME/taro-popsicle/venv/bin"
ExecStart=/home/YOUR_WSL_USERNAME/taro-popsicle/venv/bin/gunicorn app:app --bind 0.0.0.0:8081 --workers 4 --threads 2 --timeout 120
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable taro-popsicle
sudo systemctl start taro-popsicle
sudo systemctl status taro-popsicle
```

---

## Troubleshooting

### Can't SSH to WSL from Mac
```bash
# On WSL, check SSH service is running
sudo service ssh status

# If not running, start it
sudo service ssh start

# Check firewall (Windows Defender)
# May need to allow SSH port 22 in Windows Firewall
```

### rsync: command not found (on Mac)
```bash
# rsync is pre-installed on macOS, but if missing:
brew install rsync
```

### HEIC images not loading on WSL
```bash
# Reinstall HEIF libraries
sudo apt install -y libde265-dev libx265-dev libheif-dev libheif1
source venv/bin/activate
pip install --no-cache-dir --force-reinstall pillow-heif
```

### Permission denied errors
```bash
cd ~/taro-popsicle
sudo chown -R $USER:$USER data/
chmod -R 755 data/
chmod 644 data/photobook.db
```

### Port already in use
```bash
# Check what's using the port
sudo lsof -i :8081

# Either kill the process or change PORT in .env
```

### Can't access from Windows browser
```bash
# Get WSL IP address
hostname -I

# Use that IP in browser: http://192.168.1.XXX:8081
# Or try: http://localhost:8081
```

---

## Quick Checklist

**On WSL:**
- [ ] Install system packages (Python, HEIF libs, SSH, rsync)
- [ ] Start SSH service
- [ ] Get WSL IP address
- [ ] Clone repository

**On Mac:**
- [ ] Transfer data/ directory via rsync or scp

**On WSL:**
- [ ] Create Python virtual environment
- [ ] Install Python packages
- [ ] Create .env file
- [ ] Verify data directory transferred correctly
- [ ] Run `python app.py`
- [ ] Access at `http://localhost:8081`

**Estimated time:** 20-30 minutes (depending on network speed for 804MB transfer)
