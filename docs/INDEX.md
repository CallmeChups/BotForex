# BotForex Documentation Index

**Last Updated**: 2026-02-26
**Total Documentation**: 2,205 lines across 4 comprehensive guides + this index

---

## Quick Navigation

### For Different Roles

**New Developer?**
→ Start with [Developer Guide](developer-guide.md) (15-minute quick start)

**Need to Configure Bot?**
→ Check [Bot Parameters](bot-parameters.md) (parameter reference with UI mapping)

**Understanding the System?**
→ Review [System Architecture](system-architecture.md) (design and data flow)

**Exploring Codebase?**
→ Read [Codebase Summary](codebase-summary.md) (module documentation)

**Operations/Debugging?**
→ Refer to [Developer Guide](developer-guide.md) (log reading and troubleshooting)

---

## Documentation Files

### 1. System Architecture (`system-architecture.md`) - 469 lines

**What**: Complete system design and data flow documentation

**Contents**:
- Architecture overview with visual diagram
- Core components (11 sections)
- Data flow diagrams
- Key parameters and features
- Error handling and resilience
- Security considerations
- Performance metrics
- Deployment instructions

**When to use**:
- Understanding how the system works
- Planning new features
- Troubleshooting design issues
- Architecture reviews

**Key sections**:
```
- Overview
- Architecture Pattern
- Core Components (1-8)
- Data Flow
- Key Parameters & Features
- Error Handling & Resilience
- Security Considerations
- Performance
- Deployment
- Future Enhancements
```

---

### 2. Bot Parameters (`bot-parameters.md`) - 459 lines

**What**: Complete reference for all 45+ command-line parameters

**Contents**:
- 45 command-line parameters documented
- Type, default, example, UI field for each
- Entry configuration parameters
- Risk & money management parameters
- Exit configuration parameters
- Breakeven feature parameters
- Pending order retry parameters
- Bot control parameters
- 3 complete example configurations
- UI field mapping table
- Formulas and calculations

**When to use**:
- Configuring a bot in Streamlit UI
- Running bot from command line
- Understanding parameter formulas
- Debugging bot behavior

**Key sections**:
```
- Required Parameters (3)
- Entry Configuration (6)
- Risk & Money Management (10)
- Exit Configuration (3)
- Breakeven Move Feature (3)
- Pending Order Retry Feature (2)
- Bot Control (2)
- Example Configurations (3)
- UI Field Mapping
```

**Parameters included**:
- `--strategy`: Strategy ID
- `--symbol`: Trading symbol
- `--user`: MT5 user credentials
- `--timeframe`: M5, M15, H1, H4, D1
- `--entry_time`: Time in HH:MM format
- `--entry_mode`: "close" (market) or "range_percent" (LIMIT)
- `--entry_percent`: Entry price % of candle range
- `--sl_pips`: Stop loss in pips
- `--rr_ratio`: Risk:Reward ratio
- `--lot_size`: Fixed lot size
- `--lot_mode`: "fixed" or "flex"
- `--risk_percent`: Risk % per trade
- `--risk_amount`: Fixed USD risk
- `--tp_type`: "price_based" or "close_based"
- `--sl_type`: "price_based" or "close_based"
- `--max_candles`: Max candles to hold position
- `--move_sl_to_breakeven`: Enable/disable breakeven move
- `--breakeven_trigger_percent`: Trigger at N% of TP
- `--breakeven_target`: "entry" or "close"
- `--pending_order_max_candles`: Retry LIMIT for N candles
- `--pending_order_expire_candles`: Cancel LIMIT after N candles
- `--test`: 1 (test) or 0 (live)
- `--interval`: Check interval in seconds
- ... and 20+ more

---

### 3. Codebase Summary (`codebase-summary.md`) - 648 lines

**What**: Complete module documentation for 13 core Python modules

**Contents**:
- Project overview and stats
- Directory structure with annotations
- 13 core modules documented:
  - bot_runner.py (~1850 lines)
  - bot_manager.py (~200 lines)
  - orders.py (~250 lines)
  - backtest.py (~400 lines)
  - strategy.py (~323 lines)
  - auth.py (~150 lines)
  - strategy_manager.py (~200 lines)
  - utils.py (~300 lines)
  - calculation.py (~350 lines)
  - telegram.py (~100 lines)
  - symbol_validator.py (~150 lines)
  - backtest_history.py (~200 lines)
  - bot_config_history.py (~150 lines)
- 8 Streamlit dashboard pages
- Data storage structures
- Dependencies (16 libraries)
- Configuration reference
- Key patterns and conventions
- Error handling strategy
- Performance characteristics

**When to use**:
- Understanding what each module does
- Finding function locations
- Learning code patterns
- Code reviews
- Refactoring planning

**Key sections**:
```
- Project Overview
- Directory Structure
- Core Modules (13 detailed)
- Streamlit Pages (8)
- Data Storage
- Dependencies
- Configuration
- Key Patterns
- Error Handling
- Performance
- Future Enhancements
```

---

### 4. Developer Guide (`developer-guide.md`) - 629 lines

**What**: Practical developer onboarding and development guide

**Contents**:
- 15-minute quick start (clone, setup, run)
- Project structure overview
- Bot lifecycle and flow
- How to add new strategies (5-step process)
- Reading bot logs for debugging (4 key sections)
- Common development tasks (5 examples)
- Testing checklist (8 categories, 40+ items)
- Code standards and patterns
- Performance optimization tips
- Troubleshooting guide (7 common issues)
- Learning path and resources
- Next steps

**When to use**:
- Setting up development environment
- Onboarding new developers
- Adding new strategies
- Debugging bot issues
- Before deploying to live trading

**Key sections**:
```
- Getting Started (15 min)
- Project Structure Overview
- Understanding the Bot Flow
- How to Add a New Strategy
- Reading Bot Logs
- Common Development Tasks
- Testing Checklist
- Code Standards & Patterns
- Performance Optimization
- Troubleshooting Guide
- Resources & Learning Path
```

---

## Quick Reference Tables

### By Task

| Task | Document | Section |
|------|----------|---------|
| Set up bot for first time | Developer Guide | Getting Started |
| Configure bot parameters | Bot Parameters | Parameter Reference |
| Understand system design | System Architecture | Overview & Components |
| Add new strategy | Developer Guide | How to Add Strategy |
| Debug entry time issues | Developer Guide | Troubleshooting |
| Read bot logs | Developer Guide | Reading Bot Logs |
| Calculate lot size | Bot Parameters | --lot_size |
| Configure breakeven move | Bot Parameters | Breakeven Feature |
| Test strategy | Developer Guide | Testing Checklist |
| Review module X | Codebase Summary | Core Modules |

### By Parameter

| Parameter | Document | Section |
|-----------|----------|---------|
| --strategy | Bot Parameters | Required Parameters |
| --symbol | Bot Parameters | Required Parameters |
| --timeframe | Bot Parameters | Entry Configuration |
| --entry_time | Bot Parameters | Entry Configuration |
| --entry_mode | Bot Parameters | Entry Configuration |
| --sl_pips | Bot Parameters | Risk & Money Management |
| --rr_ratio | Bot Parameters | Risk & Money Management |
| --lot_size | Bot Parameters | Risk & Money Management |
| --move_sl_to_breakeven | Bot Parameters | Breakeven Move Feature |
| --pending_order_max_candles | Bot Parameters | Pending Order Retry |
| --pending_order_expire_candles | Bot Parameters | Pending Order Retry |
| --test | Bot Parameters | Bot Control |

### By Module

| Module | Document | Section |
|--------|----------|---------|
| bot_runner.py | Codebase Summary | Core Modules #3 |
| bot_manager.py | Codebase Summary | Core Modules #2 |
| orders.py | Codebase Summary | Core Modules #5 |
| strategy.py | Codebase Summary | Core Modules #4 |
| backtest.py | Codebase Summary | Core Modules #6 |
| auth.py | Codebase Summary | Core Modules #7 |
| All modules | System Architecture | Core Components |

---

## Content Statistics

| Metric | Value |
|--------|-------|
| Total documentation lines | 2,205 |
| Total documentation size | 72 KB |
| Number of files | 4 |
| Sections | 176 |
| Code examples | 90+ |
| Tables | 202 |
| Visual diagrams | 3 |
| Parameters documented | 45+ |
| Modules documented | 13 |
| Functions documented | 100+ |
| Common tasks covered | 5+ |
| Troubleshooting issues | 7+ |
| Testing checklist items | 40+ |

---

## Search Guide

### Looking for...

**Parameter information**
→ [Bot Parameters](bot-parameters.md) - use Ctrl+F to search parameter name

**Module information**
→ [Codebase Summary](codebase-summary.md) - use Ctrl+F to search module name

**How to perform task**
→ [Developer Guide](developer-guide.md) - see "Common Development Tasks"

**System design**
→ [System Architecture](system-architecture.md) - see "Core Components"

**Getting started**
→ [Developer Guide](developer-guide.md) - see "Getting Started in 15 Minutes"

**Troubleshooting**
→ [Developer Guide](developer-guide.md) - see "Troubleshooting Guide"

**Testing before deployment**
→ [Developer Guide](developer-guide.md) - see "Testing Checklist"

**Code examples**
→ [Bot Parameters](bot-parameters.md) - "Example Configurations"
→ [Developer Guide](developer-guide.md) - "Common Development Tasks"

**Data formats**
→ [Codebase Summary](codebase-summary.md) - "Data Storage" section

**API/Function reference**
→ [Codebase Summary](codebase-summary.md) - Module sections

---

## Integration with Existing Docs

This documentation complements:

- **README.md**: High-level project overview (Vietnamese)
- **CLAUDE.md**: Development workflow and CI/CD rules
- **project-overview-pdr.md**: Product requirements and features
- **code-standards.md**: Code style and conventions
- **project-roadmap.md**: Future development plans

---

## How to Use These Docs

### For Quick Answers (< 5 min)
1. Identify your role (Developer, Operator, Maintainer)
2. Go to "Quick Navigation" above
3. Search for specific topic in Ctrl+F
4. Find answer in relevant section

### For Learning (30 min - 2 hours)
1. Start with [Developer Guide](developer-guide.md) - "Getting Started"
2. Run the bot following quick start
3. Read [System Architecture](system-architecture.md) - "Overview"
4. Explore relevant modules in [Codebase Summary](codebase-summary.md)

### For Deep Dive (2+ hours)
1. Read [System Architecture](system-architecture.md) in full
2. Read [Codebase Summary](codebase-summary.md) for your area of interest
3. Read source code in `src/` directory
4. Run tests and backtests from [Developer Guide](developer-guide.md)

### For Troubleshooting (5-30 min)
1. Find your issue in [Developer Guide](developer-guide.md) - "Troubleshooting"
2. Follow suggested solutions
3. Check bot logs location in [Developer Guide](developer-guide.md) - "Reading Bot Logs"
4. Search logs with terms from error message

---

## Documentation Maintenance

### When to Update
- New parameter added → Update [Bot Parameters](bot-parameters.md)
- New module added → Update [Codebase Summary](codebase-summary.md)
- Architecture change → Update [System Architecture](system-architecture.md)
- New strategy added → Update [Developer Guide](developer-guide.md) examples

### Update Process
1. Identify documentation file to update
2. Search for relevant section
3. Verify against current source code
4. Update with accurate information
5. Test examples if code examples included

---

## Version History

**Version 2.0.0** (2026-02-26)
- Complete system documentation (4 files)
- All 45 parameters documented
- 13 modules fully documented
- Developer onboarding guide
- 2,205 total lines of documentation

---

## Support & Contribution

### Getting Help
1. Search documentation using Ctrl+F
2. Check [Developer Guide](developer-guide.md) - "Resources" section
3. Review GitHub issues
4. Ask team members

### Contributing to Documentation
1. Identify needed documentation or update
2. Follow same format as existing docs
3. Include examples and tables
4. Test all code examples
5. Submit pull request with documentation updates

---

## Document References

All documentation files located in `/d/BotForex/docs/`:

- **system-architecture.md** (18 KB, 469 lines)
- **bot-parameters.md** (16 KB, 459 lines)
- **codebase-summary.md** (21 KB, 648 lines)
- **developer-guide.md** (17 KB, 629 lines)

---

## Next Steps

1. **Choose Your Path**:
   - Developer? → [Developer Guide](developer-guide.md)
   - Configuration? → [Bot Parameters](bot-parameters.md)
   - Architecture? → [System Architecture](system-architecture.md)
   - Code review? → [Codebase Summary](codebase-summary.md)

2. **Read Selected Document** (30-60 minutes)

3. **Run First Bot** (15 minutes)

4. **Continue Learning** (ongoing)

5. **Contribute** (improvements welcome!)

---

**Happy learning and trading!**

For questions, refer to the appropriate documentation section or ask your team lead.
