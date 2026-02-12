# Migration Guide: Mac → WSL (Windows)

## Overview
This guide helps you migrate the Taro Popsicle photo management app from macOS to WSL on Windows. Your data directory is ~804MB.

## Step 1: Install Prerequisites on WSL

```bash
# Update system packages
sudo apt update && sudo apt upgrade -y

# Install Python 3 and pip
sudo apt install python3 python3-pip python3-venv -y

# Install HEIF/HEIC support libraries (critical for Mac photos)
sudo apt install libheif-dev libheif1 -y

# Install image processing libraries for Pillow
sudo apt install libjpeg-dev zlib1g-dev -y

# Install git if not already installed
sudo apt install git -y
```

## Step 2: Transfer Files to WSL

### Option A: Using Git (Recommended for code only)
```bash
# On WSL, clone the repository
cd ~
git clone <your-repo-url> taro-popsicle
cd taro-popsicle
```

**Important:** Git ignores the `data/` directory, so you'll need to transfer it separately (see Step 3).

### Option B: Using rsync over network
```bash
# On Mac, install rsync if needed (usually pre-installed)
# Get your WSL IP address first. On WSL run:
hostname -I

# On Mac, sync the entire project (replace WSL_USER and WSL_IP)
rsync -avz --progress /Users/edvart/Programming/taro-popsicle/ WSL_USER@WSL_IP:~/taro-popsicle/
```

### Option C: Using Windows filesystem bridge
```bash
# On WSL, you can access Windows drives at /mnt/c/, /mnt/d/, etc.
# First, copy the project to a Windows location (e.g., C:\Users\YourName\taro-popsicle)
# Then from WSL:
cp -r /mnt/c/Users/YourName/taro-popsicle ~/taro-popsicle
```

## Step 3: Transfer Data Directory (~804MB)

The `data/` directory contains:
- `data/photos/` - Original uploaded photos
- `data/thumbnails/` - Generated thumbnails
- `data/display/` - Web-optimized display versions
- `data/web/` - Additional web assets (seems like display copies)
- `data/videos/` - Live Photo videos
- `data/photobook.db` - SQLite database with all metadata

### Transfer methods (choose one):

**Option 1: Copy via Windows filesystem** (Easiest)
```bash
# After copying project to Windows, from WSL:
cd ~/taro-popsicle
cp -r /mnt/c/Users/YourName/taro-popsicle-backup/data ./
```

**Option 2: Use scp over network**
```bash
# On Mac, create a tarball
cd /Users/edvart/Programming/taro-popsicle
tar -czf data.tar.gz data/

# Transfer to WSL (get WSL IP with `hostname -I` on WSL)
scp data.tar.gz WSL_USER@WSL_IP:~/taro-popsicle/

# On WSL, extract
cd ~/taro-popsicle
tar -xzf data.tar.gz
rm data.tar.gz
```

**Option 3: Use cloud storage** (Google Drive, Dropbox, etc.)
```bash
# Upload data/ folder from Mac to cloud
# Download on Windows, then copy to WSL
```

## Step 4: Set Up Python Environment

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

## Step 5: Configure Environment Variables

```bash
# Create .env file
nano .env
```

Add your configuration (update values as needed):
```
SECRET_KEY=oaksjgbaopejgaosj
USERNAME=edvart
PASSWORD=pudding
USERNAME2=michi
PASSWORD2=hilbert
PORT=8081
```

Save and exit (Ctrl+O, Enter, Ctrl+X in nano).

## Step 6: Verify Data Directories

```bash
# Check that all directories exist and have content
ls -lh data/
# Should show: display/, photos/, photobook.db, thumbnails/, videos/, web/

# Check database exists
ls -lh data/photobook.db

# Check photo count
ls data/photos/ | wc -l
```

## Step 7: Test the Application

```bash
# Activate virtual environment if not already active
source venv/bin/activate

# Run in development mode
python app.py
```

The app should start on `http://localhost:8081` (or your configured PORT).

## Step 8: Production Deployment (Optional)

### Using Gunicorn (recommended)
```bash
# Activate virtual environment
source venv/bin/activate

# Run with gunicorn
gunicorn app:app --bind 0.0.0.0:8081 --workers 4 --threads 2 --timeout 120
```

### Create systemd service for auto-start
```bash
sudo nano /etc/systemd/system/taro-popsicle.service
```

Add:
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

## Troubleshooting

### HEIC images not loading
```bash
# Install additional HEIF libraries
sudo apt install libde265-dev libx265-dev -y
pip install --no-cache-dir pillow-heif
```

### Permission issues with data directory
```bash
# Fix ownership
cd ~/taro-popsicle
sudo chown -R $USER:$USER data/
chmod -R 755 data/
```

### Port already in use
```bash
# Check what's using the port
sudo lsof -i :8081

# Kill the process or change PORT in .env
```

### Database locked errors
```bash
# Check file permissions
ls -l data/photobook.db

# Should be readable/writable by your user
chmod 644 data/photobook.db
```

## WSL-Specific Notes

1. **File Paths**: WSL uses Linux-style paths (`/home/user/`) not Windows paths (`C:\Users\`)
2. **Performance**: Keep project files in WSL filesystem (`~/`) rather than Windows filesystem (`/mnt/c/`) for better I/O performance
3. **Networking**: WSL can access Windows network, but Windows may need special config to access WSL services
4. **Accessing from Windows**: If you want to access the app from Windows browser:
   - Get WSL IP: `hostname -I`
   - Access at `http://WSL_IP:8081`
   - Or use `localhost:8081` if WSL2 networking is configured

## Quick Migration Checklist

- [ ] Install prerequisites on WSL (Python, HEIF libraries)
- [ ] Transfer code to WSL (git clone or file copy)
- [ ] Transfer data/ directory (~804MB)
- [ ] Create Python virtual environment
- [ ] Install Python dependencies
- [ ] Create .env file with credentials
- [ ] Verify all data directories exist
- [ ] Test run with `python app.py`
- [ ] Optional: Set up gunicorn for production
- [ ] Optional: Create systemd service for auto-start

## Estimated Time
- Prerequisites installation: 5-10 minutes
- File transfer (depends on method): 10-30 minutes
- Python setup: 5 minutes
- Testing: 5 minutes
- **Total: 25-50 minutes**
