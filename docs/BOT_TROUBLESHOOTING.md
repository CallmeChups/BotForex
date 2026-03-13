# Bot Troubleshooting Guide

## Bot Won't Start or Stops Immediately

### Quick Diagnosis

Run this script to check what's wrong:

```bash
python check_bot_startup.py
```

This will:
1. List all users
2. Check MT5 credentials for your user
3. Test MT5 connection
4. Show exactly what error is preventing bot startup

### Common Issues

#### 1. MT5 Credentials Not Configured

**Symptom:** Bot starts but stops immediately. Log shows:
```
MT5 credentials not configured for user: <username>
```

**Solution:**
1. Go to Settings page
2. Configure MT5 account (login, password, server)
3. Try starting bot again

#### 2. MT5 Login Failed

**Symptom:** Bot starts but stops immediately. Log shows:
```
MT5 login failed: <error>
```

**Solution:**
- Check your MT5 account is active
- Verify login/password/server are correct
- Make sure MT5 terminal is closed (only one connection allowed)

#### 3. No Error Messages, Bot Just Disappears

**Symptom:** Bot appears in running_bots.json but process dies immediately

**Solution:**
1. Check bot log file: `logs/bot_<pid>.log`
2. Look for error at the end of the file
3. Common causes:
   - MT5 not installed (`pip install MetaTrader5`)
   - Invalid strategy ID
   - Missing required parameters

### How to View Logs

#### Method 1: Using view_logs.py script

```bash
python view_logs.py
```

This script lets you:
- List all bot logs
- View specific log file
- Follow log in real-time (like `tail -f`)

#### Method 2: Direct file access

Bot logs are saved in `logs/` directory:
- Format: `bot_<pid>.log`
- Example: `logs/bot_12345.log`

View with any text editor or:
```bash
# Windows PowerShell
Get-Content logs\bot_12345.log -Tail 50

# View and follow
Get-Content logs\bot_12345.log -Wait -Tail 50
```

#### Method 3: Check from UI

1. Go to "Bots" page
2. Look at "Running Bots" tab
3. Each bot shows its log file path
4. Open that file with a text editor

### Where to Find Errors

Bot logs show:
- Startup validation
- MT5 connection status
- Entry time checks
- Order placement attempts
- Position monitoring
- Exit signals
- Errors and warnings

Example log:
```
[2026-01-31 14:10:00] [INFO] Starting bot: master_candle | XAUUSD | user=john
[2026-01-31 14:10:00] [INFO] Test mode: YES
[2026-01-31 14:10:01] [ERROR] MT5 credentials not configured for user: john
```

### Emergency Stop

Stop all your bots:
1. Go to "Bots" page
2. Click "Stop All My Bots"

Or manually kill processes:
```bash
# Windows
taskkill /F /PID <pid>

# Check running Python processes
tasklist | findstr python
```

### Still Having Issues?

1. Check `running_bots.json` - is bot listed?
2. Check Windows Task Manager - is Python process running with that PID?
3. Check bot log file - what was last message?
4. Run diagnostic: `python check_bot_startup.py`
5. Check Telegram - bot sends notifications on start/errors

### Log File Examples

**Successful start:**
```
[2026-01-31 14:10:00] [INFO] Starting bot: master_candle | XAUUSD | user=john
[2026-01-31 14:10:00] [INFO] Test mode: YES
[2026-01-31 14:10:01] [INFO] Strategy loaded: Master Candle
[2026-01-31 14:10:01] [INFO] === BOT MAIN LOOP STARTED ===
[2026-01-31 14:10:01] [INFO] Waiting for entry time: 14:15
```

**Failed start (credentials):**
```
[2026-01-31 14:10:00] [INFO] Starting bot: master_candle | XAUUSD | user=john
[2026-01-31 14:10:00] [INFO] Test mode: YES
[2026-01-31 14:10:01] [INFO] Strategy loaded: Master Candle
[2026-01-31 14:10:01] [ERROR] MT5 credentials not configured for user: john
```

**Failed start (MT5 login):**
```
[2026-01-31 14:10:00] [INFO] Starting bot: master_candle | XAUUSD | user=john
[2026-01-31 14:10:00] [INFO] Test mode: YES
[2026-01-31 14:10:01] [INFO] Strategy loaded: Master Candle
[2026-01-31 14:10:02] [ERROR] MT5 login failed: (1, 'Invalid credentials')
```
