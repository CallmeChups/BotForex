# Generator script for bot_runner_multi.py
# Reads from bot_runner.py and builds the multi-trade variant

import os

src_path = 'D:/BotForex/src/bot_runner.py'
dst_path = 'D:/BotForex/src/bot_runner_multi.py'

with open(src_path, 'r', encoding='utf-8') as f:
    src_lines = f.readlines()

def extract_func(src_lines, start_line_1based):
    """Extract a function starting at start_line_1based until next top-level def/class."""
    start = start_line_1based - 1
    i = start + 1
    while i < len(src_lines):
        l = src_lines[i]
        if (l.startswith('def ') or l.startswith('class ')) and not l.startswith('    '):
            break
        i += 1
    return ''.join(src_lines[start:i])

# Extract shared functions
setup_logging_code = extract_func(src_lines, 29)
log_code = extract_func(src_lines, 129)
send_telegram_code = extract_func(src_lines, 151)
send_telegram_async_code = extract_func(src_lines, 173)
get_mt5_code = extract_func(src_lines, 180)
get_pip_code = extract_func(src_lines, 206)
get_tf_sec_code = extract_func(src_lines, 212)
get_point_code = extract_func(src_lines, 221)
get_candle_code = extract_func(src_lines, 253)

output = open(dst_path, 'w', encoding='utf-8')

def w(s):
    output.write(s)

# ===== HEADER =====
w('"""\n')
w('Bot Runner Multi - Multiple Master Candle Strategy Bot\n')
w('\n')
w('Monitors a time window and enters trades on each qualifying candle within the window.\n')
w('Multiple trades can be active simultaneously.\n')
w('\n')
w('Usage:\n')
w('    python src/bot_runner_multi.py --strategy multiple_master_candle --symbol XAUUSD --user admin \\n')
w('        --window_start 09:00 --window_end 11:00 --priority_direction auto\n')
w('"""\n')
w('\n')
w('import argparse\n')
w('import os\n')
w('import sys\n')
w('import time\n')
w('from datetime import datetime, timedelta\n')
w('from zoneinfo import ZoneInfo\n')
w('\n')
w('# Add parent directory to path\n')
w('sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))\n')
w('\n')
w('from dotenv import load_dotenv\n')
w('load_dotenv()\n')
w('\n')
w('TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")\n')
w('\n')
w('# Global log file handle\n')
w('_log_file = None\n')
w('\n')
w('\n')

# ===== SHARED FUNCTIONS (verbatim from bot_runner.py) =====
w(setup_logging_code)
w('\n')
w(log_code)
w('\n')
w(send_telegram_code)
w('\n')
w(send_telegram_async_code)
w('\n')
w(get_mt5_code)
w('\n')
w(get_pip_code)
w('\n')
w(get_tf_sec_code)
w('\n')
w(get_point_code)
w('\n')
w(get_candle_code)
w('\n')

output.close()
print('Header + shared functions written, lines:', open(dst_path).read().count('\n'))
