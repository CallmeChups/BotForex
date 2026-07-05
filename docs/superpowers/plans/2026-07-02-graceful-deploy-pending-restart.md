# Graceful Deploy with Pending Restart Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow CI/CD to deploy code without interrupting bots that have active/pending trades — idle bots restart immediately, busy bots get a flag file and self-restart when they become idle.

**Architecture:** CI/CD writes a flag file `logs/pending_restart/<pid>.flag` for any bot with active/pending orders instead of killing it. `bot_runner.py` checks for its own flag file at the end of each tick loop iteration; when idle (no active_trades, no pending_orders), it exits cleanly. `bot_manager.py` restart loop detects the exit and relaunches with the same parameters (already exists via the `__main__` restart loop in bot_runner).

**Tech Stack:** Python stdlib (os, pathlib), PowerShell (CI/CD), JSON (bot state file)

## Global Constraints

- Windows-first: all paths use `os.path` / `pathlib.Path`, flag dir is `logs/pending_restart/`
- Flag filename format: `<pid>.flag` (e.g. `12345.flag`)
- Bot state file: `data/bot_state.json` — written by bot_runner each tick, read by CI/CD deploy step
- No new dependencies — stdlib only
- `bot_runner.py` restart loop (in `__main__`) already handles restarting after clean exit — do not duplicate
- YAGNI: no UI changes needed, no database changes

---

### Task 1: bot_runner writes bot_state.json each tick

**Files:**
- Modify: `src/bot_runner.py` (tick loop, after `last_candle_time = candle_time`)

**Interfaces:**
- Produces: `data/bot_state.json` — JSON array, each entry:
  ```json
  {"pid": 12345, "symbol": "XAUUSDm", "strategy": "feg_ema21", "active": 2, "pending": 1}
  ```
- Consumed by: Task 2 (CI/CD reads this to decide restart-now vs flag)

- [ ] **Step 1: Add state writer helper in bot_runner.py**

  Find the section after `last_candle_time = candle_time` (around line 740) and add a call to a new helper. Add this helper function near the top of the `run_feg_bot` function body (before the `try:` loop), or as a module-level function:

  ```python
  def _write_bot_state(pid: int, symbol: str, strategy: str, active: int, pending: int):
      """Write this bot's runtime state to data/bot_state.json for CI/CD graceful deploy."""
      import fcntl as _fcntl  # noqa — not available on Windows, use try/except
      state_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "bot_state.json")
      state_path = os.path.normpath(state_path)
      os.makedirs(os.path.dirname(state_path), exist_ok=True)
      entry = {"pid": pid, "symbol": symbol, "strategy": strategy, "active": active, "pending": pending}
      # Load existing, replace this pid's entry, write back
      try:
          with open(state_path, "r", encoding="utf-8") as f:
              all_states = json.load(f)
      except Exception:
          all_states = []
      all_states = [s for s in all_states if s.get("pid") != pid]
      all_states.append(entry)
      # Write atomically via temp file
      tmp = state_path + ".tmp"
      with open(tmp, "w", encoding="utf-8") as f:
          json.dump(all_states, f)
      os.replace(tmp, state_path)
  ```

  Note: `json` is already imported in `bot_runner.py`? Check — if not, add `import json` at the top.

- [ ] **Step 2: Call _write_bot_state each tick**

  After `last_candle_time = candle_time` (end of `if is_new_candle:` block, ~line 740), add:

  ```python
  _write_bot_state(os.getpid(), args.symbol, args.strategy,
                   len(active_trades), len(pending_orders))
  ```

  Also add `import json` near top of file if not already present.

- [ ] **Step 3: Verify manually**

  Run bot locally for one tick interval, check `data/bot_state.json` exists and contains correct entry:
  ```powershell
  Get-Content data\bot_state.json
  # Expected: [{"pid": XXXXX, "symbol": "...", "strategy": "...", "active": 0, "pending": 0}]
  ```

- [ ] **Step 4: Commit**

  ```powershell
  git add src/bot_runner.py
  git commit -m "feat: bot_runner writes bot_state.json each tick for graceful deploy"
  ```

---

### Task 2: bot_runner checks flag file and exits when idle

**Files:**
- Modify: `src/bot_runner.py` (end of tick loop, after `_write_bot_state` call)

**Interfaces:**
- Consumes: flag file at `logs/pending_restart/<pid>.flag` — written by CI/CD (Task 3)
- Produces: clean `sys.exit(0)` when flag present + idle → triggers `__main__` restart loop

- [ ] **Step 1: Add flag-check helper**

  Add this function near `_write_bot_state`:

  ```python
  def _check_pending_restart(pid: int) -> bool:
      """Return True if a pending_restart flag file exists for this PID."""
      flag_path = os.path.join("logs", "pending_restart", f"{pid}.flag")
      return os.path.exists(flag_path)

  def _clear_pending_restart(pid: int):
      """Remove the pending_restart flag file."""
      flag_path = os.path.join("logs", "pending_restart", f"{pid}.flag")
      try:
          os.remove(flag_path)
      except FileNotFoundError:
          pass
  ```

- [ ] **Step 2: Check flag at end of each tick**

  After the `_write_bot_state(...)` call, add:

  ```python
  # Graceful restart: if flagged and idle, exit cleanly so __main__ restarts with new code
  if _check_pending_restart(os.getpid()) and not active_trades and not pending_orders:
      log("Pending restart flag detected and bot is idle — restarting with new code")
      _clear_pending_restart(os.getpid())
      close_session(_session_id)
      sys.exit(0)
  ```

- [ ] **Step 3: Verify flag behavior manually**

  Start bot, wait one tick, create flag file manually:
  ```powershell
  # Get bot PID from data/running_bots.json
  $pid = (Get-Content data\running_bots.json | ConvertFrom-Json)[0].pid
  New-Item -ItemType Directory -Force logs\pending_restart | Out-Null
  New-Item -ItemType File "logs\pending_restart\$pid.flag" | Out-Null
  ```
  Wait for next tick — bot should log "Pending restart flag detected" and exit (then restart loop relaunches it).

- [ ] **Step 4: Commit**

  ```powershell
  git add src/bot_runner.py
  git commit -m "feat: bot_runner self-restarts when idle and pending_restart flag present"
  ```

---

### Task 3: CI/CD deploy step — smart restart per bot

**Files:**
- Modify: `.github/workflows/deploy.yml` — replace "Restart API Server" and "Restart Streamlit" steps; add new "Smart restart bots" step

**Interfaces:**
- Consumes: `data/bot_state.json` (from Task 1) — read via PowerShell on server
- Consumes: `data/running_bots.json` — existing file, has pid per bot
- Produces: flag files at `logs/pending_restart/<pid>.flag` for busy bots; kills+restarts idle bots

- [ ] **Step 1: Add "Smart restart bots" step in deploy.yml**

  Add this new step **before** the existing "Restart Streamlit" step (keep API server restart as-is):

  ```yaml
      - name: Smart restart bots
        if: ${{ github.event.inputs.restart_streamlit == 'true' }}
        run: |
          ssh -i ~/.ssh/deploy_key -o StrictHostKeyChecking=no \
            hyperion@100.110.182.114 \
            "powershell -NonInteractive -Command \"\
              Set-Location D:\\BotForex; \
              \$flagDir = 'D:\\BotForex\\logs\\pending_restart'; \
              New-Item -ItemType Directory -Force \$flagDir | Out-Null; \
              \$stateFile = 'D:\\BotForex\\data\\bot_state.json'; \
              if (Test-Path \$stateFile) { \
                \$states = Get-Content \$stateFile | ConvertFrom-Json; \
              } else { \
                \$states = @(); \
              }; \
              \$botsFile = 'D:\\BotForex\\data\\running_bots.json'; \
              if (Test-Path \$botsFile) { \
                \$bots = Get-Content \$botsFile | ConvertFrom-Json; \
              } else { \
                \$bots = @(); \
              }; \
              foreach (\$bot in \$bots) { \
                \$pid = \$bot.pid; \
                \$state = \$states | Where-Object { \$_.pid -eq \$pid } | Select-Object -First 1; \
                \$busy = \$state -and (\$state.active -gt 0 -or \$state.pending -gt 0); \
                if (\$busy) { \
                  Write-Host \"Bot PID \$pid is busy (active=\$(\$state.active) pending=\$(\$state.pending)) — flagging for deferred restart\"; \
                  New-Item -ItemType File -Force \"\$flagDir\\\$pid.flag\" | Out-Null; \
                } else { \
                  Write-Host \"Bot PID \$pid is idle — restarting now\"; \
                  try { Stop-Process -Id \$pid -Force -ErrorAction SilentlyContinue } catch {}; \
                  Start-Sleep -Seconds 1; \
                } \
              }; \
              Write-Host 'Smart bot restart complete' \
            \""
  ```

- [ ] **Step 2: Verify in deploy.yml YAML is valid**

  Check indentation — the new step must align with other `- name:` entries under `steps:`. Run:
  ```bash
  # On local machine (requires yamllint or python-yaml):
  python -c "import yaml; yaml.safe_load(open('.github/workflows/deploy.yml'))" && echo OK
  ```

- [ ] **Step 3: Test via manual workflow dispatch**

  Trigger CI/CD with a bot running (no active trades). Check:
  - GitHub Actions logs show "Bot PID XXXXX is idle — restarting now"
  - Bot relaunches (new PID appears in `data/running_bots.json`)

- [ ] **Step 4: Commit**

  ```powershell
  git add .github/workflows/deploy.yml
  git commit -m "feat: CI/CD smart restart — flag busy bots, kill idle bots immediately"
  ```

---

### Task 4: Cleanup — remove stale state entries on bot stop

**Files:**
- Modify: `src/bot_manager.py` — `stop_bot()` function
- Modify: `src/bot_runner.py` — KeyboardInterrupt and Exception handlers

**Interfaces:**
- Consumes: `data/bot_state.json` written by Task 1
- Produces: stale entries removed when bot stops so CI/CD doesn't read old state

- [ ] **Step 1: Add state cleanup helper in bot_manager.py**

  Add after the `save_bots` function (around line 46):

  ```python
  def _remove_bot_state(pid: int):
      """Remove pid entry from data/bot_state.json when bot stops."""
      state_path = os.path.join("data", "bot_state.json")
      if not os.path.exists(state_path):
          return
      try:
          with open(state_path, "r", encoding="utf-8") as f:
              states = json.load(f)
          states = [s for s in states if s.get("pid") != pid]
          tmp = state_path + ".tmp"
          with open(tmp, "w", encoding="utf-8") as f:
              json.dump(states, f)
          os.replace(tmp, state_path)
      except Exception:
          pass
  ```

  Add `import json` at top of `bot_manager.py` if not present (check — it already is).

- [ ] **Step 2: Call _remove_bot_state in stop_bot()**

  In `stop_bot()`, just before `return True, f"Bot stopped (PID {pid})"` (around line 294):

  ```python
  _remove_bot_state(pid)
  ```

  Also add it in the early-return branch when process not running (around line 261):

  ```python
  _remove_bot_state(pid)
  return True, f"Process {pid} not running (removed from list)"
  ```

- [ ] **Step 3: Clean up state on bot_runner exit**

  In `bot_runner.py`, in the `KeyboardInterrupt` handler:

  ```python
  except KeyboardInterrupt:
      log("FEG Bot stopped by user")
      _write_bot_state(os.getpid(), args.symbol, args.strategy, 0, 0)  # clear state
      close_session(_session_id)
      send_telegram("FEG Bot Stopped (manual)")
  ```

  And in the `Exception` handler, before `raise`:

  ```python
  _write_bot_state(os.getpid(), args.symbol, args.strategy, 0, 0)  # clear state on crash
  ```

- [ ] **Step 4: Verify cleanup**

  Start bot, wait one tick (state file has entry), stop bot via UI, check:
  ```powershell
  Get-Content data\bot_state.json
  # Expected: [] or no entry for that pid
  ```

- [ ] **Step 5: Commit**

  ```powershell
  git add src/bot_manager.py src/bot_runner.py
  git commit -m "fix: remove stale bot_state.json entry on bot stop/crash"
  ```
