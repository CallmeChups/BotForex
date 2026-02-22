"""
View bot logs in real-time
"""
import os
import json
import sys
import time

BOTS_FILE = "data/running_bots.json"

def load_bots():
    """Load running bots"""
    if os.path.exists(BOTS_FILE):
        try:
            with open(BOTS_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            return []
    return []

def list_log_files():
    """List all available log files"""
    logs_dir = "logs"
    if not os.path.exists(logs_dir):
        print("No logs directory found")
        return []

    log_files = [f for f in os.listdir(logs_dir) if f.startswith('bot_') and f.endswith('.log')]
    return sorted(log_files, key=lambda x: os.path.getmtime(os.path.join(logs_dir, x)), reverse=True)

def tail_file(file_path, lines=50, follow=False):
    """Tail a file (like tail -f)"""
    try:
        with open(file_path, 'r') as f:
            # Read all lines
            all_lines = f.readlines()

            # Print last N lines
            for line in all_lines[-lines:]:
                print(line, end='')

            if follow:
                # Follow mode (like tail -f)
                print("\n=== Following log (Ctrl+C to stop) ===\n")
                try:
                    while True:
                        line = f.readline()
                        if line:
                            print(line, end='')
                        else:
                            time.sleep(0.1)
                except KeyboardInterrupt:
                    print("\n=== Stopped following ===")
    except FileNotFoundError:
        print(f"Error: Log file not found: {file_path}")
    except Exception as e:
        print(f"Error reading log: {e}")

def main():
    print("=== Bot Log Viewer ===\n")

    # Load running bots
    bots = load_bots()

    if bots:
        print(f"Running bots ({len(bots)}):")
        for idx, bot in enumerate(bots, 1):
            log_file = bot.get('log_file', 'N/A')
            print(f"{idx}. PID {bot['pid']} - {bot['symbol']} - {log_file}")
        print()

    # List all log files
    log_files = list_log_files()

    if not log_files:
        print("No log files found in logs/ directory")
        return

    print(f"Available log files ({len(log_files)}):")
    for idx, log_file in enumerate(log_files, 1):
        file_path = os.path.join("logs", log_file)
        size = os.path.getsize(file_path)
        mtime = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(os.path.getmtime(file_path)))
        print(f"{idx}. {log_file} ({size} bytes, modified: {mtime})")

    print("\nOptions:")
    print("  [number] - View log file")
    print("  [number]f - Follow log file (tail -f)")
    print("  all - View all logs concatenated")
    print("  q - Quit")

    while True:
        choice = input("\nEnter choice: ").strip().lower()

        if choice == 'q':
            break
        elif choice == 'all':
            print("\n=== All Logs ===\n")
            for log_file in log_files:
                file_path = os.path.join("logs", log_file)
                print(f"\n=== {log_file} ===\n")
                tail_file(file_path, lines=100, follow=False)
        elif choice.endswith('f'):
            # Follow mode
            try:
                idx = int(choice[:-1])
                if 1 <= idx <= len(log_files):
                    file_path = os.path.join("logs", log_files[idx-1])
                    print(f"\n=== {log_files[idx-1]} ===\n")
                    tail_file(file_path, lines=50, follow=True)
                else:
                    print("Invalid choice")
            except ValueError:
                print("Invalid choice")
        else:
            # View mode
            try:
                idx = int(choice)
                if 1 <= idx <= len(log_files):
                    file_path = os.path.join("logs", log_files[idx-1])
                    print(f"\n=== {log_files[idx-1]} ===\n")
                    tail_file(file_path, lines=100, follow=False)
                else:
                    print("Invalid choice")
            except ValueError:
                print("Invalid choice")

if __name__ == "__main__":
    main()
