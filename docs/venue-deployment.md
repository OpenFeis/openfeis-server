# 🏟️ Venue Deployment Guide

This guide explains how to run Open Feis at a competition venue **without internet connectivity**. This is the core "local-first" feature that ensures your feis runs smoothly even when WiFi fails.

## Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    VENUE NETWORK                             │
│                                                              │
│    ┌──────────────┐      Local WiFi      ┌──────────────┐   │
│    │   Organizer  │◄─────Router─────────►│  Judge iPad  │   │
│    │   Laptop     │        │              │   (Safari)   │   │
│    │  (Server)    │        │              └──────────────┘   │
│    │              │        │                                 │
│    │ ┌──────────┐ │        │              ┌──────────────┐   │
│    │ │ OpenFeis │ │        └─────────────►│  Judge iPad  │   │
│    │ │  Docker  │ │                       │   (Safari)   │   │
│    │ └──────────┘ │                       └──────────────┘   │
│    │              │                                          │
│    │ ┌──────────┐ │                       ┌──────────────┐   │
│    │ │ SQLite   │ │        ┌─────────────►│  Tabulator   │   │
│    │ │   DB     │ │        │              │    Screen    │   │
│    │ └──────────┘ │        │              └──────────────┘   │
│    └──────────────┘        │                                 │
│                            │              ┌──────────────┐   │
│                            └─────────────►│  Results     │   │
│                                           │   Display    │   │
│                                           └──────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## Requirements

### Hardware
- **Server Laptop**: Any modern laptop with Docker installed
  - Recommended: MacBook, Windows laptop, or Linux machine
  - Minimum: 4GB RAM, 10GB free disk space
  
- **Local WiFi Router**: Any consumer-grade WiFi router
  - Does NOT need internet connectivity
  - 5GHz preferred for speed/reliability
  - Venue-supplied WiFi works too if available

- **Judge Devices**: iPads, tablets, or phones
  - Modern browser (Safari, Chrome)
  - Connected to the same WiFi network

### Software
- Docker and Docker Compose installed on the server laptop
- Open Feis repository cloned

## Pre-Event Setup (At Home/Office)

### 1. Install Docker

**Mac:**
```bash
brew install --cask docker
# Or download from https://docker.com/products/docker-desktop
```

**Windows:**
Download and install Docker Desktop from https://docker.com/products/docker-desktop

**Linux (Debian/Ubuntu):**
```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
# Log out and back in
```

### 2. Clone and Build

```bash
# Clone the repository
git clone https://github.com/OpenFeis/openfeis-server.git
cd openfeis-server

# Build the Docker image (do this at home with internet!)
docker compose -f docker-compose.local.yml build
```

### 3. Prepare Your Data

Before the event, set up your feis data:

1. Start the server: `docker compose -f docker-compose.local.yml up`
2. Open http://localhost:8000 in your browser
3. Log in as admin (`admin@openfeis.org` / `admin123`)
4. Create your feis and generate the syllabus
5. Import registrations or let dancers register online
6. Export/backup the database
7. Stop the server: `Ctrl+C` or `docker compose -f docker-compose.local.yml down`

The database is stored in `./data/openfeis.db` - copy this file to bring your data to the venue.

## Venue Day Setup

### 1. Network Setup

1. **Set up the WiFi router**
   - Power on the router (no internet cable needed)
   - Configure SSID: `OpenFeis-Network` (or similar)
   - Set a WPA2 password and share with judges
   - Disable any "internet detection" features that might cause issues

2. **Connect the server laptop**
   - Connect to the WiFi network you created
   - Note the laptop's IP address:
   
   **Mac/Linux:**
   ```bash
   # Look for the IP under your WiFi interface (usually en0 or wlan0)
   ifconfig | grep "inet "
   # Usually something like 192.168.1.100 or 10.0.0.100
   ```
   
   **Windows:**
   ```cmd
   ipconfig
   # Look for "IPv4 Address" under your WiFi adapter
   ```

### 2. Start Open Feis

```bash
cd openfeis-server
docker compose -f docker-compose.local.yml up
```

Wait for the message:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### 3. Connect Judge Devices

On each judge's iPad/tablet:

1. Connect to the venue WiFi network
2. Open Safari/Chrome
3. Navigate to: `http://<server-ip>:8000`
   - Example: `http://192.168.1.100:8000`
4. Log in with their judge credentials
5. **Add to Home Screen** (iOS: Share → Add to Home Screen)

### 4. Set Up Results Displays

For stage-side results:

1. Connect display device to venue WiFi
2. Navigate to `http://<server-ip>:8000`
3. Go to Tabulator Dashboard
4. Select the competition to display
5. Enable auto-refresh (results update every 5 seconds)

## During the Competition

### Judge Workflow

1. Judges open Judge Pad on their device
2. Select the competition they're judging
3. Enter scores for each dancer
4. Scores are saved locally AND sent to server instantly
5. If WiFi drops momentarily, scores save locally and sync when reconnected

### Tabulator Workflow

1. Open Tabulator Dashboard
2. Select feis and competition
3. Results calculate automatically as scores come in
4. Irish Points are calculated per CLRG rules
5. Recall status shows top 50% (with tie extension)

### Backup During Event

Run this periodically (every hour or between age groups):

```bash
# Create timestamped backup
cp data/openfeis.db "data/backup-$(date +%H%M).db"
```

## Troubleshooting

### "Can't connect to server"

1. Verify laptop is connected to venue WiFi
2. Check laptop's IP address hasn't changed
3. Ensure Docker container is running: `docker compose -f docker-compose.local.yml ps`
4. Try accessing http://localhost:8000 on the server laptop itself

### "Score didn't save"

1. Check device WiFi connection
2. Look for "⚠ Offline" indicator in Judge Pad
3. Scores save locally automatically - they'll sync when reconnected
4. Judge can continue scoring - nothing is lost

### "Results aren't updating"

1. Verify auto-refresh is enabled in Tabulator
2. Check server is running
3. Manually click "Refresh" button
4. Verify scores are actually being submitted (check Judge Pad)

### "Device keeps disconnecting"

1. Move closer to WiFi router
2. Reduce interference (move router away from metal/electronics)
3. Consider using 5GHz band instead of 2.4GHz
4. Check router isn't overloaded (typical limit: 30-50 devices)

## Post-Event

### 1. Create Final Backup

```bash
cp data/openfeis.db "data/final-backup-$(date +%Y%m%d).db"
```

### 2. Export Results (Optional)

The Tabulator Dashboard can be used to view and screenshot final results.

### 3. Sync to Cloud (When Internet Available)

Once you have internet connectivity:

1. Navigate to Admin → Cloud Sync
2. Review pending data
3. Click "Sync to Cloud"
4. Results become available on the public site

## Security Notes

- The local server has no HTTPS - this is fine for a private network
- Don't expose the local server to the internet
- Change the default admin password before the event
- Create individual accounts for each judge

## Hardware Recommendations

### Budget Setup (~$100)
- Any laptop with Docker
- TP-Link travel router (TL-WR902AC, ~$40)

### Professional Setup (~$500)
- Mac Mini or Intel NUC as dedicated server
- Ubiquiti UniFi AP for reliable WiFi
- UPS battery backup for power outages

### Enterprise Setup
- Redundant servers
- Mesh WiFi system
- Dedicated IT support on-site

## FAQ

**Q: What if the server laptop dies mid-competition?**
A: Judges' scores are saved locally on their devices. Start a new server, and when judges reconnect, their local scores will sync.

**Q: Can multiple judges score the same competition?**
A: Yes! Each judge has their own score card. The system tracks scores by judge ID.

**Q: How many devices can connect?**
A: Depends on your WiFi router. Consumer routers handle 30-50 devices easily. For large feiseanna (100+ judges), consider enterprise equipment.

**Q: Can parents view results on their phones?**
A: Yes, anyone connected to the venue WiFi can view the public tabulator. No login required to view results.

---

## Quick Reference Card

Print this and tape it to the server laptop:

```
╔════════════════════════════════════════════════════╗
║              OPEN FEIS - VENUE SERVER               ║
╠════════════════════════════════════════════════════╣
║                                                     ║
║  START:   docker compose -f docker-compose.local.yml up  ║
║  STOP:    Ctrl+C                                    ║
║                                                     ║
║  SERVER IP: ____________________                    ║
║  WIFI NAME: ____________________                    ║
║  WIFI PASS: ____________________                    ║
║                                                     ║
║  JUDGE URL: http://[IP]:8000                        ║
║  ADMIN LOGIN: admin@openfeis.org / ________         ║
║                                                     ║
║  BACKUP: cp data/openfeis.db data/backup.db         ║
║                                                     ║
╚════════════════════════════════════════════════════╝
```

