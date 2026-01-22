# MT5 Forex Trading Bot - Lộ Trình Phát Triển

**Cập Nhật Lần Cuối**: 2026-01-17
**Phiên Bản**: 0.1.0
**Trạng Thái**: Early-Stage PoC

## Tóm Tắt Thực Hiện

MT5 Forex Trading Bot hiện ở giai đoạn **Proof-of-Concept (PoC)** với:
- Chiến lược tham chiếu hoạt động (test/ref.py)
- Core indicators implemented
- Telegram notification module
- MT5 connection & order execution working

**Next Priority**: Complete Phase 1 (Entry points, config, logging)

## Tổng Quan Phase

### Phase 1: Foundation & Cleanup (Hiện Tại - Q1 2026)
**Mục đích**: Stabilize PoC, externalize credentials, proper structure
**Tổng Effort**: 2-3 tuần
**Trạng Thái**: 🔄 In Progress

### Phase 2: Strategy Enhancement (Q2 2026)
**Mục đích**: Improve trading logic, add filters, better risk management
**Tổng Effort**: 3-4 tuần
**Trạng Thái**: 📋 Planned

### Phase 3: Infrastructure & Scale (Q3 2026)
**Mục đích**: Database, API, monitoring, multi-bot support
**Tổng Effort**: 4-5 tuần
**Trạng Thái**: 📋 Planned

### Phase 4: Optimization & Advanced (Q4 2026+)
**Mục đích**: Backtesting, machine learning, distributed processing
**Tổng Effort**: 6+ tuần
**Trạng Thái**: 📋 Future

---

## Phase 1: Foundation & Cleanup

**Timeline**: 3-4 tuần (Jan 17 - Feb 14, 2026)
**Effort**: 40-60 hours
**Status**: In Progress

### Task 1.1: Externalize Credentials & Setup Config
**Priority**: 🔴 Critical | **Effort**: 3-4 hours
**Status**: 📋 Pending

**Objectives**:
- [ ] Create .env.example file
- [ ] Move MT5 credentials to environment variables
- [ ] Move Telegram token to environment variables
- [ ] Update src/telegram.py to read from env
- [ ] Create config/config.yaml template
- [ ] Add dotenv-python to requirements.txt
- [ ] Test credential loading

**Acceptance Criteria**:
- No hardcoded credentials in code
- .env properly gitignored
- Config loads from YAML successfully
- All tests pass with env vars

**Files to Modify**:
- src/telegram.py (remove hardcoded token)
- test/ref.py (remove hardcoded credentials)
- requirements.txt (add python-dotenv)
- Create .env.example
- Create config/config.yaml

### Task 1.2: Implement main.py Entry Point
**Priority**: 🔴 Critical | **Effort**: 4-5 hours
**Status**: 📋 Pending

**Objectives**:
- [ ] Parse command-line arguments
- [ ] Load configuration from YAML
- [ ] Initialize logging
- [ ] Initialize MT5 connection
- [ ] Initialize Telegram
- [ ] Start main trading loop
- [ ] Handle graceful shutdown (Ctrl+C)
- [ ] Add error recovery

**Acceptance Criteria**:
- `python main.py` starts bot successfully
- Config loading works
- MT5 connection verified
- Telegram token verified
- Proper error messages on failure

**Code Structure**:
```python
def main():
    # 1. Parse CLI args
    # 2. Load config
    # 3. Setup logging
    # 4. Init MT5
    # 5. Init Telegram
    # 6. Run strategy loop (from test/ref.py)
    # 7. Cleanup on exit

if __name__ == '__main__':
    main()
```

### Task 1.3: Implement Comprehensive Logging
**Priority**: 🟠 High | **Effort**: 3-4 hours
**Status**: 📋 Pending

**Objectives**:
- [ ] Setup logging module with config
- [ ] Create logs/ directory if not exists
- [ ] File handler (logs/bot.log)
- [ ] Console handler (stdout)
- [ ] Different log levels (DEBUG/INFO/WARNING/ERROR/CRITICAL)
- [ ] Log format with timestamp
- [ ] Replace print() with logger calls
- [ ] Add trade logging (separate file)

**Acceptance Criteria**:
- logs/ directory created automatically
- bot.log records all operations
- Console shows INFO+ level
- Format: timestamp, level, module, message
- Trade details logged separately

**Files to Modify**:
- src/calculation.py (add debug logs)
- test/ref.py (add trade logs)
- Create src/logger.py (logging config)

### Task 1.4: Improve Error Handling & Recovery
**Priority**: 🟠 High | **Effort**: 4-5 hours
**Status**: 📋 Pending

**Objectives**:
- [ ] Add try-catch blocks for MT5 operations
- [ ] Add try-catch blocks for order execution
- [ ] Add custom exception classes
- [ ] Implement retry logic for network failures
- [ ] Graceful handling of Telegram failures
- [ ] Notify user of critical errors
- [ ] Log all errors with full context

**Custom Exceptions**:
```python
class MT5ConnectionError(Exception)
class MT5DataFetchError(Exception)
class OrderExecutionError(Exception)
class TelegramError(Exception)
class ConfigError(Exception)
```

**Files to Create/Modify**:
- Create src/exceptions.py
- test/ref.py (add error handling)
- src/telegram.py (improve retry logic)

### Task 1.5: Setup config/config.yaml Template
**Priority**: 🟡 Medium | **Effort**: 2-3 hours
**Status**: 📋 Pending

**Template Content**:
```yaml
mt5:
  login: ${MT5_LOGIN}
  password: ${MT5_PASSWORD}
  server: "Exness-MT5Trial14"

telegram:
  token: ${TELEGRAM_TOKEN}
  dev_chat_id: ${TELEGRAM_DEV_ID}
  user_chat_id: ${TELEGRAM_USER_ID}

strategy:
  symbol: "BTCUSDm"
  lot: 0.1

timeframes:
  long: H4
  mid: M30
  short: M5

indicators:
  macd: [12, 26, 9]
  stoch_1: [7, 5, 3]
  stoch_2: [13, 13, 5]
  ma: [10, 20]

risk:
  sl_multiplier: 1.5
  tp_multiplier: 1.5

logging:
  level: "INFO"
  file: "logs/bot.log"
```

**Acceptance Criteria**:
- config.yaml loads successfully
- All env vars substituted
- All parameters accessible in code
- Default values sensible

### Task 1.6: Create & Run Formal Test Suite
**Priority**: 🟡 Medium | **Effort**: 3-4 hours
**Status**: 📋 Pending

**Objectives**:
- [ ] Add test/unit/test_calculation.py
- [ ] Add test/unit/test_strategy.py
- [ ] Add test/unit/test_telegram.py
- [ ] Test indicator calculations
- [ ] Test signal detection
- [ ] Test order building
- [ ] Achieve 70%+ code coverage

**Test Cases**:
- MACD calculation returns tuple of lists
- Stochastic returns dict with k/d
- Cross detection works for up/down
- Strategy conditions check properly
- Telegram message formatting correct

**Files to Create**:
- test/unit/__init__.py
- test/unit/test_calculation.py
- test/unit/test_strategy.py
- test/unit/test_telegram.py

### Task 1.7: Update Documentation
**Priority**: 🟡 Medium | **Effort**: 2-3 hours
**Status**: ✅ In Progress (this document)

**Objectives**:
- [ ] Update README.md with new structure
- [ ] Add SETUP.md with installation steps
- [ ] Create docs/API.md
- [ ] Update docs/ files (done)

---

## Phase 2: Strategy Enhancement & Risk Management

**Timeline**: 4 tuần (Feb 15 - Mar 15, 2026)
**Effort**: 60-80 hours
**Status**: 📋 Planned

### Task 2.1: Improve Entry/Exit Conditions
**Priority**: 🔴 Critical | **Effort**: 6-8 hours
**Status**: 📋 Pending

**Objectives**:
- [ ] Add volume filter (volume > threshold)
- [ ] Add volatility filter (ATR-based)
- [ ] Add trend confirmation (EMA direction)
- [ ] Add support/resistance levels
- [ ] Implement proper exit conditions (not just SL/TP)
- [ ] Add trailing stop option
- [ ] Backtest on 1 month historical data

**New Entry Logic**:
```
BUY Entry (Enhanced):
├─ MACD cross up (H4)
├─ AND Stoch < 20 (M30)
├─ AND MA cross (M5)
├─ AND Volume > 20M (M5)
├─ AND Price above 50 SMA (H4)
└─ AND Volatility acceptable (ATR < 500)
```

**Files to Create/Modify**:
- Create src/risk_manager.py
- test/ref.py (enhance logic)
- config/config.yaml (add filters)

### Task 2.2: Implement Proper Position Management
**Priority**: 🟠 High | **Effort**: 5-6 hours
**Status**: 📋 Pending

**Objectives**:
- [ ] Track current position state
- [ ] Prevent multiple entries
- [ ] Implement partial take-profit
- [ ] Implement break-even stop loss
- [ ] Add position sizing based on account balance
- [ ] Add max positions per symbol
- [ ] Log all position changes

**Position State**:
```python
class Position:
    symbol: str
    entry_type: 'BUY' | 'SELL'
    entry_price: float
    entry_time: datetime
    entry_signal: str
    volume: float
    sl: float
    tp: float
    status: 'OPEN' | 'CLOSED'
```

**Files to Create**:
- Create src/position_manager.py

### Task 2.3: Add Portfolio Risk Limits
**Priority**: 🟠 High | **Effort**: 4-5 hours
**Status**: 📋 Pending

**Objectives**:
- [ ] Max loss per day limit
- [ ] Max loss per trade limit
- [ ] Max exposure limits (% of balance)
- [ ] Max positions limit
- [ ] Equity check before order
- [ ] Automatic stop trading if loss limit hit
- [ ] Telegram alert for risk limits breached

**Risk Checks**:
```
Before Entry:
├─ Account balance > min_balance
├─ Potential loss < daily_loss_limit
├─ Potential loss < max_trade_loss
├─ Current exposure < max_exposure
└─ Positions < max_positions
```

### Task 2.4: Implement ATR-Based SL/TP
**Priority**: 🟡 Medium | **Effort**: 3-4 hours
**Status**: 📋 Pending

**Objectives**:
- [ ] Calculate ATR (14-period)
- [ ] Dynamic SL = entry - (ATR * 1.5)
- [ ] Dynamic TP = entry + (ATR * 2.0)
- [ ] Configurable ATR multipliers
- [ ] Backtesting on historical data
- [ ] Compare results with fixed multipliers

**ATR Calculation**:
```python
def calculate_atr(df, period=14):
    high_low = df['high'] - df['low']
    high_close = abs(df['high'] - df['close'].shift())
    low_close = abs(df['low'] - df['close'].shift())
    tr = high_low.combine(high_close, max).combine(low_close, max)
    atr = tr.rolling(period).mean()
    return atr
```

### Task 2.5: Add Performance Analytics
**Priority**: 🟡 Medium | **Effort**: 4-5 hours
**Status**: 📋 Pending

**Objectives**:
- [ ] Calculate win rate
- [ ] Calculate profit factor
- [ ] Calculate Sharpe ratio
- [ ] Calculate max drawdown
- [ ] Generate daily P&L report
- [ ] Export metrics to CSV
- [ ] Display metrics in logs

**Metrics to Calculate**:
```
Total Trades: count
Winning Trades: count, %
Losing Trades: count, %
Profit Factor: gross_profit / gross_loss
Win/Loss Ratio: avg_win / avg_loss
Sharpe Ratio: (return - risk_free) / volatility
Max Drawdown: max peak-to-trough decline
ROI: total_profit / initial_balance * 100%
```

---

## Phase 3: Infrastructure & Scaling

**Timeline**: 4-5 tuần (Mar 16 - Apr 20, 2026)
**Effort**: 80-100 hours
**Status**: 📋 Planned

### Task 3.1: Implement SQLite Database
**Priority**: 🟠 High | **Effort**: 6-8 hours
**Status**: 📋 Pending

**Objectives**:
- [ ] Design database schema
- [ ] Create tables: trades, signals, errors, performance
- [ ] Implement ORM (SQLAlchemy or similar)
- [ ] Store all trades persistently
- [ ] Query historical trades
- [ ] Export reports from database
- [ ] Database backup/recovery

**Schema**:
```sql
CREATE TABLE trades (
    id INTEGER PRIMARY KEY,
    timestamp DATETIME,
    symbol TEXT,
    entry_type TEXT,
    entry_price REAL,
    volume REAL,
    sl REAL,
    tp REAL,
    exit_price REAL,
    exit_time DATETIME,
    pnl REAL,
    status TEXT
);

CREATE TABLE signals (
    id INTEGER PRIMARY KEY,
    timestamp DATETIME,
    symbol TEXT,
    signal_type TEXT,
    conditions_met TEXT,
    price REAL
);

CREATE TABLE performance (
    id INTEGER PRIMARY KEY,
    date DATE,
    daily_pnl REAL,
    win_rate REAL,
    profit_factor REAL,
    trades_count INT
);
```

### Task 3.2: Build Streamlit Dashboard (app.py)
**Priority**: 🟠 High | **Effort**: 8-10 hours
**Status**: 📋 Pending

**Objectives**:
- [ ] Live account balance display
- [ ] Current position display
- [ ] P&L metrics
- [ ] Trade history table
- [ ] Start/Stop bot controls
- [ ] Parameter adjustment interface
- [ ] Charts (equity curve, trade distribution)
- [ ] Log viewer

**Dashboard Pages**:
1. **Overview**: Balance, P&L, live metrics
2. **Positions**: Current open positions
3. **History**: Trade history, filters
4. **Signals**: Recent signals detected
5. **Analytics**: Performance charts
6. **Logs**: Real-time log viewer
7. **Settings**: Config parameter editor

### Task 3.3: Implement REST API (Optional)
**Priority**: 🟡 Medium | **Effort**: 6-8 hours
**Status**: 📋 Planned

**Objectives**:
- [ ] Create FastAPI application
- [ ] Endpoints for bot control
- [ ] Endpoints for data queries
- [ ] API authentication
- [ ] Rate limiting
- [ ] API documentation (Swagger)
- [ ] Docker containerization

**API Endpoints**:
```
POST   /bot/start          - Start bot
POST   /bot/stop           - Stop bot
GET    /bot/status         - Bot status
GET    /account/balance    - Account balance
GET    /positions          - Open positions
GET    /trades             - Trade history
POST   /config/update      - Update parameters
GET    /metrics            - Performance metrics
```

### Task 3.4: Multi-Bot Instance Support
**Priority**: 🟡 Medium | **Effort**: 5-6 hours
**Status**: 📋 Planned

**Objectives**:
- [ ] Support multiple symbol/strategy combinations
- [ ] Separate config for each instance
- [ ] Shared database, separate logs
- [ ] Instance manager script
- [ ] Monitor all instances together
- [ ] Per-instance risk limits

**Structure**:
```
instances/
├── instance_1.yaml    # BTC MACD strategy
├── instance_2.yaml    # EUR momentum strategy
└── instance_3.yaml    # GOLD counter-trend
```

---

## Phase 4: Optimization & Advanced Features

**Timeline**: 6+ tuần (May 1 - Jun 30, 2026)
**Effort**: 120+ hours
**Status**: 📋 Future

### Task 4.1: Backtesting Engine
**Priority**: 🟠 High | **Effort**: 12-15 hours
**Status**: 📋 Planned

**Objectives**:
- [ ] Historical data downloader
- [ ] Event-driven backtester
- [ ] Parameter optimization (walk-forward)
- [ ] Monte Carlo analysis
- [ ] Out-of-sample validation
- [ ] Generate backtest reports
- [ ] Compare with live results

**Backtesting Features**:
- Supports 1M to monthly timeframes
- Transaction costs simulation
- Slippage simulation
- Commission settings
- Leverage settings

### Task 4.2: Machine Learning Integration
**Priority**: 🟡 Medium | **Effort**: 10-12 hours
**Status**: 📋 Future

**Objectives**:
- [ ] Feature engineering from technical indicators
- [ ] Classification model (bull/bear market)
- [ ] Regression model (next candle direction)
- [ ] Train/test on historical data
- [ ] Online learning (update with new trades)
- [ ] Confidence threshold for signals

**ML Models to Explore**:
- Random Forest (classification)
- XGBoost (classification & regression)
- Neural Networks (LSTM for trend)
- SVM (market regime detection)

### Task 4.3: Advanced Risk Management
**Priority**: 🟡 Medium | **Effort**: 8-10 hours
**Status**: 📋 Future

**Objectives**:
- [ ] Volatility-adjusted position sizing
- [ ] Correlation-based portfolio management
- [ ] Value at Risk (VaR) calculation
- [ ] Conditional Value at Risk (CVaR)
- [ ] Kelly Criterion position sizing
- [ ] Market regime detection
- [ ] Adaptive strategy parameters

### Task 4.4: Distributed Processing
**Priority**: 🔵 Low | **Effort**: 15+ hours
**Status**: 📋 Future

**Objectives**:
- [ ] Celery task queue for distributed backtests
- [ ] Parallel parameter optimization
- [ ] Kubernetes orchestration
- [ ] Cloud deployment (AWS/GCP)
- [ ] Microservices architecture
- [ ] Real-time data streaming (Kafka)

---

## Development Timeline & Milestones

### Q1 2026 (Jan 17 - Mar 15)

**Week 1-2 (Jan 17 - Jan 31)**:
- Complete Task 1.1: Credentials externalization
- Complete Task 1.2: main.py implementation
- **Milestone**: Bot starts and stops cleanly

**Week 3-4 (Feb 1 - Feb 14)**:
- Complete Task 1.3: Logging
- Complete Task 1.4: Error handling
- Complete Task 1.6: Test suite
- **Milestone**: All Phase 1 tasks complete

**Week 5-8 (Feb 15 - Mar 15)**:
- Complete Task 2.1: Entry/exit improvements
- Complete Task 2.2: Position management
- Complete Task 2.3: Risk limits
- **Milestone**: Enhanced trading logic

### Q2 2026 (Mar 16 - Jun 15)

**Week 1-4 (Mar 16 - Apr 13)**:
- Complete Task 2.4: ATR-based SL/TP
- Complete Task 2.5: Analytics
- Complete Task 3.1: Database
- **Milestone**: Persistent storage working

**Week 5-8 (Apr 14 - May 11)**:
- Complete Task 3.2: Streamlit dashboard
- Complete Task 3.3: REST API (optional)
- Complete Task 3.4: Multi-bot support
- **Milestone**: Dashboard operational

**Week 9-12 (May 12 - Jun 15)**:
- Phase 1-3 polish and testing
- Performance optimization
- Security audit
- **Milestone**: v1.0.0 Release

### Q3 2026 (Jun 16 - Sep 15)

**Week 1-8**:
- Complete Task 4.1: Backtesting engine
- Complete Task 4.2: ML integration
- **Milestone**: Backtesting & ML available

**Week 9-12**:
- Complete Task 4.3: Advanced risk management
- Comprehensive testing
- **Milestone**: v2.0.0 Release

### Q4 2026 & Beyond

- Task 4.4: Distributed processing (optional)
- Cloud deployment
- Advanced analytics
- Community features

---

## Resource Allocation

### Team Roles

| Role | Hours/Week | Tasks |
|------|-----------|-------|
| Core Developer | 20-30 | Main coding, architecture |
| QA/Test | 10-15 | Testing, edge cases |
| DevOps | 5-10 | Infrastructure, deployment |
| Product/Docs | 5 | Planning, documentation |

### Dependency Management

- **MetaTrader5**: Terminal must run on Windows
- **Python 3.10+**: Virtual environment required
- **Telegram**: Bot token needed
- **Database**: SQLite (Phase 3)
- **Streamlit**: (Phase 3)
- **FastAPI**: (Phase 3, optional)

---

## Success Metrics

### Phase 1 Success
- Bot runs without crashes for 24+ hours
- All credentials externalized
- 70%+ test coverage
- Comprehensive logging working
- Clean error handling

### Phase 2 Success
- Win rate > 40%
- Profit factor > 1.2
- Max drawdown < 15% of balance
- Sharpe ratio > 1.0
- Database storing all trades

### Phase 3 Success
- Dashboard operational & responsive
- Multi-bot support working
- Performance metrics < 2 seconds latency
- Backtest engine producing consistent results
- v1.0.0 stable release

### Phase 4 Success
- ML model beats baseline strategy
- Distributed backtesting 10x faster
- Cloud deployment working
- Advanced risk metrics calculated
- v2.0.0 production-ready

---

## Risk Management & Mitigation

| Risk | Impact | Likelihood | Mitigation |
|------|--------|-----------|-----------|
| MT5 API breaking changes | High | Low | Version lock dependencies, stay updated |
| Strategy underperformance | High | Medium | Continuous optimization, paper trading |
| Data quality issues | Medium | Medium | Validation, alerts, manual review |
| Credential leaks | High | Low | Env vars, .env in gitignore, audit regularly |
| Market regime changes | Medium | High | Adaptive parameters, multiple strategies |
| Infrastructure failures | Medium | Medium | Monitoring, logging, alerts, backups |

---

## Unresolved Items

1. **Backtesting Framework**: Build custom or use zipline/backtrader?
2. **ML Approach**: Supervised vs reinforcement learning?
3. **Cloud Provider**: AWS, GCP, or Azure?
4. **Database**: SQLite vs PostgreSQL vs MongoDB?
5. **API Framework**: FastAPI vs Flask?
6. **Multiple Strategies**: Single config or separate?
7. **Leverage**: Support leverage trading?
8. **Hedging**: Support hedge positions?

---

## References

- [Project Overview & PDR](./project-overview-pdr.md)
- [Code Standards](./code-standards.md)
- [Codebase Summary](./codebase-summary.md)
- [System Architecture](./system-architecture.md)

---

## Version History

| Version | Date | Status | Notes |
|---------|------|--------|-------|
| 0.1.0 | 2026-01-17 | PoC | Proof-of-concept, ref.py working |
| 1.0.0 | 2026-Q2 2026 | Planned | Phase 1-2 complete, v1 release |
| 2.0.0 | 2026-Q4 2026 | Planned | Phase 3-4 complete, v2 release |
| 3.0.0 | 2027 | Planned | Advanced features, distributed |

---

**Last Updated**: 2026-01-17
**Next Review**: 2026-02-14 (Phase 1 completion checkpoint)
