# JournalTX Deployment Guide

Choose your deployment option:

## Option 1: Docker (FASTEST - 5 minutes)

### Prerequisites
- Docker installed
- dokploy running (if using dokploy)

### Deploy with Docker Compose

```bash
# 1. Make sure .env is configured
cat .env

# 2. Build and start
docker-compose up -d

# 3. Check logs
docker-compose logs -f

# 4. Stop
docker-compose down
```

### Deploy with dokploy

1. **Push your code to GitHub**
   ```bash
   git add .
   git commit -m "Add Docker deployment"
   git push origin main
   ```

2. **In dokploy dashboard:**
   - Create new project
   - Connect GitHub repository
   - Set build context: `/`
   - Set Dockerfile path: `Dockerfile`
   - Add environment variables from `.env`
   - Deploy!

3. **Add volume for data persistence:**
   - Volume: `/app/data`
   - Mount to: `./data` on host

### Update to latest version
```bash
git pull
docker-compose down
docker-compose build
docker-compose up -d
```

---

## Option 2: VPS Direct (FAST - 15 minutes)

### Prerequisites
- VPS with Ubuntu 22.04+ (1GB RAM minimum)
- SSH access

### Quick Setup

```bash
# 1. Connect to VPS
ssh root@your-vps-ip

# 2. Install dependencies
apt update && apt install -y python3.11 python3.11-venv git

# 3. Create user (recommended)
useradd -m -s /bin/bash journaltx
su - journaltx

# 4. Clone repo
cd ~
git clone <your-repo-url> journaltx-pybot
cd journaltx-pybot

# 5. Setup environment
cp .env.example .env
nano .env  # Add your credentials

# 6. Install
python3.11 -m venv venv
source venv/bin/activate
pip install -e .

# 7. Initialize database
python -c "from journaltx.core.db import init_db; from journaltx.core.config import Config; init_db(Config.from_env())"

# 8. Test
python scripts/listen.py

# 9. Create systemd service (auto-restart)
sudo nano /etc/systemd/system/journaltx.service
```

Add this to the service file:
```ini
[Unit]
Description=JournalTX Bot
After=network.target

[Service]
Type=simple
User=journaltx
WorkingDirectory=/home/journaltx/journaltx-pybot
Environment="PATH=/home/journaltx/journaltx-pybot/venv/bin"
ExecStart=/home/journaltx/journaltx-pybot/venv/bin/python scripts/listen.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
# 10. Enable and start
sudo systemctl daemon-reload
sudo systemctl enable journaltx
sudo systemctl start journaltx

# 11. Check status
sudo systemctl status journaltx

# 12. View logs
sudo journalctl -u journaltx -f
```

### Update bot on VPS
```bash
cd ~/journaltx-pybot
git pull
source venv/bin/activate
pip install -e .
sudo systemctl restart journaltx
```

---

## Quick Test (Either Option)

After deployment, send a test alert:

```bash
# On VPS:
cd ~/journaltx-pybot
source venv/bin/activate
python scripts/alert.py --type lp_add --pair TEST/SOL --sol 100

# In Docker:
docker-compose exec journaltx python scripts/alert.py --type lp_add --pair TEST/SOL --sol 100
```

---

## Monitoring

### Check if bot is running

**Docker:**
```bash
docker-compose ps
docker-compose logs --tail 50 -f
```

**VPS:**
```bash
sudo systemctl status journaltx
sudo journalctl -u journaltx --tail 50 -f
```

### Telegram test

```bash
python scripts/test_telegram.py
```

---

## Troubleshooting

### Bot not starting
1. Check `.env` file has correct values
2. Check QuickNode credentials
3. Check Telegram bot token
4. Verify database initialized: `ls -la data/`

### No alerts received
1. Check bot is running: `sudo systemctl status journaltx`
2. Check logs: `sudo journalctl -u journaltx -n 50`
3. Test Telegram: `python scripts/test_telegram.py`
4. Check thresholds in profile: `python scripts/profile.py current`

### Database errors
```bash
# Reinitialize database
rm data/journaltx.db
python -c "from journaltx.core.db import init_db; from journaltx.core.config import Config; init_db(Config.from_env())"
```

---

## Security

### VPS Security
```bash
# Firewall
ufw allow 22/tcp
ufw enable

# Disable password login (SSH keys only)
sudo nano /etc/ssh/sshd_config
# Set: PasswordAuthentication no
sudo systemctl restart sshd
```

### Environment Security
- Never commit `.env` to Git
- Rotate API keys monthly
- Use strong passwords
- Keep QuickNode credentials private

---

## Backup

### Database backup
```bash
# Manual backup
cp data/journaltx.db data/backup_$(date +%Y%m%d).db

# Automated backup (cron)
crontab -e
# Add: 0 2 * * * cp ~/journaltx-pybot/data/journaltx.db ~/backups/journaltx_$(date +\%Y\%m\%d).db
```

---

## Speed Comparison

| Method | Time to Deploy | Difficulty | Auto-restart |
|--------|---------------|------------|--------------|
| Docker (dokploy) | **5 min** | Easy | ✅ Yes |
| Docker (compose) | **10 min** | Easy | ✅ Yes |
| VPS Direct | **15 min** | Medium | ✅ Yes |

**Recommendation:** Use Docker if you have it set up. Otherwise, VPS is straightforward.
