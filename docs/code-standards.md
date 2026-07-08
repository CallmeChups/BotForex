# MT5 Forex Trading Bot - Tiêu Chuẩn Code & Cấu Trúc Codebase

**Cập Nhật Lần Cuối**: 2026-07-08
**Phiên Bản**: 0.3.1
**Áp Dụng Cho**: Tất cả Python code trong project

## Cấu Trúc Thư Mục

```
BotForex/
├── src/                    # Core source code
│   ├── __init__.py        # Package marker (tạo nếu chưa có)
│   ├── calculation.py      # Technical indicators
│   ├── telegram.py         # Telegram notifications
│   └── utils.py            # Utility functions
├── test/                   # Test & reference scripts
│   ├── test.py            # MT5 connection test
│   └── ref.py             # Reference strategy implementation
├── config/                 # Configuration files
│   └── config.yaml        # Main config (YAML format)
├── logs/                   # Log output directory
├── data/                   # Data storage directory
├── docs/                   # Project documentation
├── main.py                # Entry point for bot
├── app.py                 # Streamlit dashboard entry
├── requirements.txt       # Python dependencies
├── README.md              # Main project README
├── CLAUDE.md              # Claude Code guidelines
└── .env.example           # Environment variables template
```

## Quy Ước Đặt Tên

### Python Files
- **Format**: snake_case với mô tả rõ ràng
- **Ví dụ**: `calculation.py`, `telegram.py`, `main.py`
- **Quy Tắc**: Tên file phải mô tả chức năng chính

### Python Functions
- **Format**: snake_case, lowercase
- **Ví dụ**: `calculate_macd()`, `send_message()`, `check_cross_2_list_updated()`
- **Quy Tắc**: Bắt đầu bằng động từ nếu là hành động

### Python Classes
- **Format**: PascalCase
- **Ví dụ**: `MACDCalculator`, `TelegramNotifier`, `MT5Connection`
- **Quy Tắc**: Mô tả entity/object, chưa implement lớp nên bỏ qua bây giờ

### Python Variables
- **Format**: snake_case, lowercase
- **Ví dụ**: `entry_price`, `stoch_values`, `signal_detected`
- **Quy Tắc**: Descriptive names, tránh single-letter variables (exception: loop counters)

### Constants
- **Format**: UPPER_SNAKE_CASE
- **Ví dụ**: `MACD_FAST_PERIOD = 12`, `MAX_RETRIES = 5`
- **Quy Tắc**: Định nghĩa ở đầu file hoặc module config

### Data Files
- **Metadata/Results**: `trade_log.csv`, `signals.json`
- **Config**: `config.yaml`, `.env`
- **Logs**: `bot.log`, `trade_2026-01-17.log`

## Quản Lý Kích Thước File

**Giới Hạn**: 500 dòng Python/file (ngoại trừ auto-generated)

**Khi Vượt Quá**:
1. Tách utility functions thành module riêng
2. Chia strategy logic thành multiple classes
3. Đưa config values vào config.yaml
4. Tách test code thành test/ directory

**Ngoại Lệ**:
- Jupyter notebooks (không có giới hạn)
- Generated config files (đánh dấu `# AUTO-GENERATED`)
- Model files (stored as pickles, not code)

## Quy Tắc Định Dạng Code

### Indentation & Whitespace
- **Indentation**: 4 spaces (Python standard)
- **Line Length**: Max 100 characters (nếu vượt, phải có lý do)
- **Blank Lines**: 2 dòng giữa functions/classes, 1 dòng trong functions
- **Trailing Whitespace**: Không cho phép

### Imports
```python
# Standard library first
import os
import sys
from datetime import datetime, timedelta

# Third-party packages
import numpy as np
import pandas as pd
from zoneinfo import ZoneInfo

# Project modules
from src.calculation import calculate_macd, calculate_stoch
from src.telegram import send_message
from src.utils import non_zero_range
```

### Comments & Documentation

**File Header** (recommended):
```python
"""
Module: calculation.py
Purpose: Technical indicators calculation (MACD, Stochastic, MA, EMA)
Author: BotForex Team
Version: 0.1.0
"""
```

**Function Documentation**:
```python
def calculate_macd(df, period_fast=12, period_slow=26, signal=9,
                   column='close', adjust=False):
    """
    Calculate MACD indicator.

    Args:
        df (pd.DataFrame): Price dataframe with OHLC columns
        period_fast (int): Fast EMA period (default 12)
        period_slow (int): Slow EMA period (default 26)
        signal (int): Signal line EMA period (default 9)
        column (str): Column to calculate on (default 'close')
        adjust (bool): Adjust EMA calculation (default False)

    Returns:
        tuple: (macd_line list, signal_line list)

    Raises:
        ValueError: If period_fast >= period_slow or invalid column

    Example:
        >>> df = pd.DataFrame({'close': [100, 101, 102, ...]})
        >>> macd, signal = calculate_macd(df)
    """
```

**Inline Comments**:
```python
# Explain WHY, not WHAT
# Example: WHY (good)
# Multiply by 100 to convert stochastic from 0-1 range to 0-100
k_value = (close - low) / (high - low) * 100

# Example: WHAT (bad - unnecessary)
# Multiply the difference by 100
k_value = (close - low) / (high - low) * 100
```

**TODO & Workarounds**:
```python
# TODO(2026-01-17): Optimize MACD calculation for large datasets
# WORKAROUND: MT5 sometimes returns empty data, retry 3 times
for attempt in range(3):
    try:
        data = mt5.copy_rates_range(...)
        if len(data) > 0:
            break
    except:
        time.sleep(1)
```

## Error Handling

**Luôn Sử Dụng Try-Catch**:
```python
import logging

logger = logging.getLogger(__name__)

try:
    # Main logic
    result = mt5.order_send(request)
    if result is None:
        logger.error("MT5 order failed: returned None")
        raise RuntimeError("MT5 order_send failed")
except MT5Error as e:
    logger.error(f"MT5 connection error: {str(e)}")
    # Handle MT5-specific errors
    notify_user(f"MT5 Error: {e}")
except Exception as e:
    logger.critical(f"Unexpected error: {type(e).__name__}: {str(e)}")
    # Generic fallback
    notify_user(f"Critical Error: {e}")
```

**Custom Exceptions** (nếu cần):
```python
class MT5ConnectionError(Exception):
    """Raised when MT5 connection fails"""
    pass

class InvalidStrategyConfiguration(Exception):
    """Raised when strategy config is invalid"""
    pass

class TelegramNotificationError(Exception):
    """Raised when Telegram message fails"""
    pass
```

## Streamlit Widget Standards (v0.3.1)

### Width Parameter (Replaces Deprecated `use_container_width`)

**Deprecated (old code)**:
```python
st.button("Click", use_container_width=True)
st.dataframe(df, use_container_width=False)
```

**New standard (v0.3.1+)**:
```python
st.button("Click", width='stretch')  # Full width
st.dataframe(df, width='content')    # Content-based width
```

Apply to:
- `st.button()`, `st.form_submit_button()`
- `st.dataframe()`
- `plotly.streamlit.plotly_chart()`
- Any widget accepting width parameter

### Layout Helpers (v0.3.1)

**`_section_header(title, color)` — Colored section divider**:
```python
def _section_header(title, color):
    """Render HTML colored section header."""
    colors = {
        "indigo": "#4F46E5",
        "emerald": "#10B981", 
        "amber": "#F59E0B",
        "red": "#EF4444"
    }
    st.html(f'<h3 style="color: {colors[color]}; border-bottom: 2px solid {colors[color]}; padding-bottom: 8px">{title}</h3>')

# Usage
_section_header("General Settings", "indigo")
```

**`_vdivider()` — Vertical CSS divider**:
```python
def _vdivider():
    """Render vertical divider for column split."""
    st.html('<div style="width: 100%; height: 100%; border-left: 2px solid #ccc"></div>')

# Usage in 2-column layout
left, div_col, right = st.columns([0.58, 0.02, 0.40])
with div_col:
    _vdivider()
```

### Page Layout Pattern (v0.3.1)

2-column form layout standard:
```python
left, div_col, right = st.columns([0.58, 0.02, 0.40])

with left:
    _section_header("General", "indigo")
    # ... general inputs
    _section_header("Entry", "emerald")
    # ... entry inputs (FEG Margins + Wick Filter)

with div_col:
    _vdivider()

with right:
    _section_header("Order Settings & Risk", "amber")
    # ... order settings
    _section_header("Exit", "red")
    # ... exit inputs
```

**Color scheme**:
- Indigo: General parameters
- Emerald: Entry conditions
- Amber: Order settings & risk sizing
- Red: Exit conditions

## Testing Standards

### Test File Organization
- **Unit Tests**: `tests/` directory (pytest)
- **Integration Tests**: `tests/` with integration markers
- **Strategy Tests**: `tests/test_*_strategy.py`

### Test Naming Convention
```python
def test_calculate_macd_returns_two_lists():
    """Test MACD calculation returns tuple of two lists"""
    # Arrange
    sample_data = create_sample_ohlc_data(periods=50)

    # Act
    macd_line, signal_line = calculate_macd(sample_data)

    # Assert
    assert isinstance(macd_line, list)
    assert isinstance(signal_line, list)
    assert len(macd_line) == len(signal_line)

def test_check_cross_detects_upward_crossover():
    """Test crossover detection for upward movement"""
    # Arrange
    line_1 = [1, 2, 3, 4, 5]  # Goes above line_2
    line_2 = [5, 4, 3, 2, 1]  # Comes below line_1

    # Act
    result = check_cross_2_list_updated(line_1, line_2, period=5)

    # Assert
    assert result['up'] == True
    assert result['down'] == False
```

### Test Coverage Requirements
- **Critical Paths**: > 80% coverage
- **Data Validation**: Test with real sample data
- **Error Cases**: Test missing/malformed data
- **Edge Cases**: Test boundary conditions

## Git Standards

### Commit Messages (Conventional Commits)

**Format**:
```
type(scope): description

Optional body with more details.
Lines wrapped at 72 characters.

Optional footer:
Fixes #123
```

**Types**:
- `feat`: New feature (e.g., new indicator calculation)
- `fix`: Bug fix (e.g., MT5 connection issue)
- `docs`: Documentation update
- `refactor`: Code refactoring without functionality change
- `perf`: Performance improvement
- `test`: Test addition/modification
- `ci`: CI/CD changes
- `chore`: Dependency updates, etc

**Examples**:
```
feat(indicators): add ATR calculation function

Implement ATR (Average True Range) calculation for SL/TP sizing.
Uses 14-period default, configurable via parameter.

Fixes #15

---

fix(telegram): retry logic for failed message sends

Add exponential backoff for Telegram API rate limits.
Max retries increased from 3 to 5, sleep 5 seconds between.

---

docs(readme): update setup instructions for Windows

Clarify MT5 terminal requirements and Python 3.10+ setup.
Add troubleshooting section for common issues.
```

### Branch Naming
- `main`: Production/stable code
- `dev`: Development branch
- `feature/`: New features (e.g., `feature/atr-calculation`)
- `fix/`: Bug fixes (e.g., `fix/mt5-connection`)
- `docs/`: Documentation (e.g., `docs/api-reference`)

### Pre-Commit Checklist
- ✅ Code follows style guidelines
- ✅ No hardcoded credentials (use env vars)
- ✅ No print() for production (use logging)
- ✅ Tests pass locally
- ✅ Docstrings updated
- ✅ Files under 500 lines (or justified exception)
- ✅ No debug code left behind

## Security Standards

### Credential Management
```python
# ✅ GOOD: Environment variables
import os
from dotenv import load_dotenv

load_dotenv('.env')
MT5_LOGIN = os.getenv('MT5_LOGIN')
MT5_PASSWORD = os.getenv('MT5_PASSWORD')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')

# ❌ BAD: Hardcoded credentials
MT5_LOGIN = "123456"
MT5_PASSWORD = "password"
TELEGRAM_TOKEN = "token123"
```

### Input Validation
```python
def send_message(msg, chat_id):
    """Validate inputs before processing"""
    # Type check
    if not isinstance(msg, str):
        raise TypeError("msg must be string")
    if not isinstance(chat_id, (str, int, list)):
        raise TypeError("chat_id must be string, int, or list")

    # Empty check
    if not msg or not msg.strip():
        raise ValueError("msg cannot be empty")

    # Length check
    if len(msg) > 4096:  # Telegram limit
        raise ValueError("msg exceeds Telegram 4096 char limit")

    # Proceed with processing
    ...
```

### Sensitive Data Handling
- **Never**: Hardcode API keys, passwords, account numbers
- **Never**: Log passwords, tokens, or sensitive values
- **Never**: Commit .env files with real credentials
- **Use**: Environment variables for all secrets
- **Store**: .env file in `.gitignore`, provide `.env.example`

## Data Processing Standards

### Config File (YAML)
```yaml
# config.yaml
mt5:
  login: ${MT5_LOGIN}          # From environment
  password: ${MT5_PASSWORD}
  server: "Exness-MT5Trial14"

telegram:
  token: ${TELEGRAM_TOKEN}
  dev_chat_id: 123456789
  user_chat_id: 987654321

strategy:
  symbol: "BTCUSDm"
  lot: 0.1
  max_retries: 5

timeframes:
  long: H4
  mid: M30
  short: M5

indicators:
  macd:
    fast: 12
    slow: 26
    signal: 9
  stochastic_1:
    k_length: 7
    k_smooth: 5
    d_smooth: 3
  stochastic_2:
    k_length: 13
    k_smooth: 13
    d_smooth: 5
  ma:
    - 10
    - 20

risk:
  sl_multiplier: 1.5
  tp_multiplier: 1.5
```

### Logging Standards
```python
import logging
import sys
from pathlib import Path

# Setup logging
log_dir = Path('logs')
log_dir.mkdir(exist_ok=True)

logger = logging.getLogger('botforex')
logger.setLevel(logging.DEBUG)

# File handler
fh = logging.FileHandler(log_dir / 'bot.log')
fh.setLevel(logging.DEBUG)

# Console handler
ch = logging.StreamHandler(sys.stdout)
ch.setLevel(logging.INFO)

# Formatter
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
fh.setFormatter(formatter)
ch.setFormatter(formatter)

logger.addHandler(fh)
logger.addHandler(ch)

# Usage
logger.debug("Starting bot initialization")
logger.info("MT5 connected successfully")
logger.warning("Low balance detected: $1000")
logger.error("Failed to send order: Connection timeout")
logger.critical("Critical error: Shutdown")
```

## Performance Standards

### Indicator Calculation
- **Target**: < 1 second per calculation
- **MACD**: O(n) complexity
- **Stochastic**: O(n) with rolling window
- **MA/EMA**: O(n) complexity

### MT5 Operations
- **Connection**: < 2 seconds
- **Data Fetch**: < 5 seconds (1 week history)
- **Order Send**: < 2 seconds
- **Timeout**: 10 seconds max per operation

### Telegram Notification
- **Success Rate**: 99% (with retry)
- **Max Retries**: 5 times
- **Retry Delay**: 5 seconds
- **Timeout per Attempt**: 10 seconds

## Type Hints (Recommended)

```python
from typing import List, Dict, Tuple, Optional, Union

def calculate_macd(df: pd.DataFrame,
                   period_fast: int = 12,
                   period_slow: int = 26,
                   signal: int = 9,
                   column: str = 'close') -> Tuple[List[float], List[float]]:
    """Calculate MACD with type hints"""
    pass

def send_message(msg: str,
                 chat_id: Union[str, int, List[str]],
                 max_retries: int = 5) -> bool:
    """Send Telegram message with type hints"""
    pass

def check_cross_2_list_updated(list_1: List[float],
                               list_2: List[float],
                               period: int = 3,
                               confirm: int = 2) -> Dict[str, bool]:
    """Detect crossover with type hints"""
    pass
```

## Documentation Standards

### Inline Documentation
- **Self-documenting Code**: Clear names reduce need for comments
- **Complex Logic**: Always comment non-obvious algorithms
- **Configuration**: Document all parameters and defaults
- **Changes**: Document WHY, not WHAT

### External Documentation
- **README**: Quick start and installation
- **API Docs**: Function signatures and usage examples
- **Architecture**: System design and data flow
- **Roadmap**: Future plans and milestones

## Python Best Practices

### Avoid Common Mistakes
```python
# ❌ BAD: Global variables, state mutation
data = None

def load_data():
    global data
    data = ...

# ✅ GOOD: Return values, immutable
def load_data():
    return ...

# ❌ BAD: Bare except
try:
    result = mt5.order_send(request)
except:
    print("Error")

# ✅ GOOD: Specific exceptions
try:
    result = mt5.order_send(request)
except (MT5ConnectionError, TimeoutError) as e:
    logger.error(f"Order failed: {e}")
    raise
except Exception as e:
    logger.critical(f"Unexpected error: {e}")
    raise

# ❌ BAD: Mutable default arguments
def send_alerts(message, targets=[]):
    targets.append(message)
    return targets

# ✅ GOOD: None default, initialize in function
def send_alerts(message, targets=None):
    if targets is None:
        targets = []
    targets.append(message)
    return targets
```

## Configuration Management

### Environment Variables (.env)
```bash
# .env (never commit this)
MT5_LOGIN=243254313
MT5_PASSWORD=Test2312025@
MT5_SERVER=Exness-MT5Trial14
TELEGRAM_TOKEN=7363572293:AAHd595bWg7liBafg8qEmasPh8Zx1I2crWo
TELEGRAM_DEV_ID=123456789
TELEGRAM_USER_ID=987654321
BOT_SYMBOL=BTCUSDm
BOT_LOT=0.1
DEBUG_MODE=false
```

### .env.example (commit this)
```bash
# .env.example (template, safe to commit)
MT5_LOGIN=YOUR_MT5_ACCOUNT_HERE
MT5_PASSWORD=YOUR_MT5_PASSWORD_HERE
MT5_SERVER=Exness-MT5Trial14
TELEGRAM_TOKEN=YOUR_TELEGRAM_BOT_TOKEN_HERE
TELEGRAM_DEV_ID=YOUR_DEV_CHAT_ID
TELEGRAM_USER_ID=YOUR_USER_CHAT_ID
BOT_SYMBOL=BTCUSDm
BOT_LOT=0.1
DEBUG_MODE=false
```

## Code Review Checklist

- ✅ Code follows naming conventions
- ✅ Functions have docstrings
- ✅ Error handling is comprehensive
- ✅ No hardcoded credentials (using env vars)
- ✅ No debug print() statements (using logging)
- ✅ Tests pass locally
- ✅ Files under 500 lines (or justified)
- ✅ Commit message is clear and follows convention
- ✅ Documentation is updated
- ✅ Performance acceptable (< 1 sec indicators, < 5 sec data fetch)

## Maintenance Notes

### Regular Tasks
- **Weekly**: Review bot logs for errors
- **Monthly**: Check MT5 connection stability
- **Quarterly**: Security audit (credentials exposure check)
- **Annually**: Code refactoring pass

### Deprecation Process
1. Mark old functions with `DeprecationWarning`
2. Document migration path in docstring
3. Maintain 2-3 releases before removal
4. Add changelog entry

### Bug Reporting
Include when reporting bugs:
- Description and reproduction steps
- Expected vs actual behavior
- Python version and OS
- Relevant error trace/log
- Sample data if applicable

## References

### Internal Documentation
- [Project Overview & PDR](./project-overview-pdr.md)
- [System Architecture](./system-architecture.md)
- [Codebase Summary](./codebase-summary.md)
- [Project Roadmap](./project-roadmap.md)

### External Resources
- [PEP 8 – Style Guide](https://pep8.org/)
- [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html)
- [Python Logging Documentation](https://docs.python.org/3/library/logging.html)
- [Conventional Commits](https://conventionalcommits.org/)
- [MetaTrader5 Python API](https://www.mql5.com/en/docs/integration/python_metatrader5)

## FEG Strategy Wick Formula (v0.3.1)

### Correct Wick Calculation

For pattern detection, use **true wick** not close-based ranges:

**SELL (bearish candle)**:
- Upper wick: `h2 - o2` (not `h2 - c2`)
- Lower wick: `c2 - l2`
- Example: OHLC=[100, 105, 95, 98] → upper_wick = 105-100 = 5, lower_wick = 98-95 = 3

**BUY (bullish candle)**:
- Upper wick: `h2 - c2`
- Lower wick: `o2 - l2` (not `c2 - l2`)
- Example: OHLC=[100, 105, 95, 102] → lower_wick = 100-95 = 5, upper_wick = 105-102 = 3

This ensures wick filters correctly reflect actual price rejection levels.

## Version Changes Summary

**v0.3.1 (2026-07-08)**:
- Layout redesign: 2-column compacted form with colored section headers
- Removed Classic layout variants (no more compact vs verbose)
- Added `_section_header()` and `_vdivider()` helpers
- Replaced `use_container_width` with `width` parameter across all widgets
- Fixed FEG wick formulas: SELL=(h2-o2), BUY=(o2-l2)
- Vietnamese UI labels throughout
- Flash message success state pattern

**v0.3.0 (2026-06-27)**:
- Same-type candle rule for FEG strategy
- Trace ID system (BT-..., ORD-...)
- Full Telegram error coverage
- Auto-restart bot with 30s delay
- CI/CD pipeline with GitHub Actions
- Verification script for backtest trace

**v0.2.0 (2026-06-21)**:
- FEG EMA21 strategy added
- Multi-strategy architecture
- 25 unit tests

**v0.1.0 (2026-01)**:
- Foundation: Master Candle strategy
- Streamlit dashboard
- Backtest engine

## Unresolved Questions

1. **Type Checking**: Enforce mypy for type hints?
2. **Linting**: Which linter (black, flake8, pylint)?
3. **Testing Framework**: pytest is standard (25 tests passing)
4. **CI/CD**: GitHub Actions workflow is implemented ✅
5. **Pre-commit Hooks**: Setup husky/pre-commit?
