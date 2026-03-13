
dst_path = 'D:/BotForex/src/bot_runner_multi.py'

lines = []
def A(s): lines.append(s)

A('')
A('def run_bot(args):')
A('    """Main bot loop - multi-trade version for Multiple Master Candle Strategy"""')
A('    from src.strategy_manager import get_strategy, get_strategy_parameters')
A('    from src.auth import get_user_mt5_credentials')
A('')
A('    bot_id = f"{args.strategy}_{args.symbol}_{args.user}_{os.getpid()}"')
A('    log_path = setup_logging(bot_id)')
A('')
A('    log(f"Starting bot (MULTI): {args.strategy} | {args.symbol} | user={args.user}")')
A('    log(f"Process ID: {os.getpid()}")')
A("    log(f"Test mode: {'YES' if args.test else 'NO - LIVE TRADING'}")")
A('')
A('    log(f"[STEP 1/5] Loading strategy: {args.strategy}")')
A('    strategy = get_strategy(args.strategy)')
A('    if not strategy:')
A('        log(f"[ERROR] CRITICAL ERROR: Strategy not found: {args.strategy}", "ERROR")')
A('        log(f"Bot cannot start without valid strategy", "ERROR")')
A('        return')
A('')
A('    params = get_strategy_parameters(args.strategy)')
A('    log(f"[OK] Strategy loaded: {strategy.get(chr(39)name chr(39))}")')

with open(dst_path, "a", encoding="utf-8") as f:
    f.write("
".join(lines))

print("done")
