import sys, yaml
sys.path.insert(0, '.')
from src.bot_runner import get_mt5_connection

with open('config/auth.yaml', 'r') as f:
    cfg = yaml.safe_load(f)
creds = cfg['credentials']['usernames']['admin']['mt5']

mt5, err = get_mt5_connection(creds)
if err:
    print('ERROR:', err)
    sys.exit(1)

# Lay tat ca symbols visible
all_symbols = mt5.symbols_get()
visible = [s for s in all_symbols if s.visible]

rows = []
for info in visible:
    sym = info.name
    rates = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M5, 0, 22)
    if rates is None or len(rates) < 6:
        continue
    closed = rates[:-1]
    last5_range = max(r['high'] for r in closed[-5:]) - min(r['low'] for r in closed[-5:])
    atr = sum(r['high'] - r['low'] for r in closed) / len(closed)
    spread_pts = round((info.ask - info.bid) / info.point) if info.point else 0
    # Margin per 0.01 lot (rough: price * contract_size * lot / leverage)
    margin_est = info.bid * info.trade_contract_size * 0.01 / 2000 if info.bid > 0 else 0
    rows.append((sym, info.bid, spread_pts, last5_range, atr, margin_est, info.trade_contract_size))

mt5.shutdown()

rows.sort(key=lambda x: x[4], reverse=True)

print(f"{'Symbol':<14} {'Price':>10} {'Sprd':>5} {'5c-rng':>10} {'ATR-M5':>8} {'Margin/0.01L':>14}")
print('-' * 70)
for sym, bid, sp, r5, atr, mg, cs in rows:
    print(f"{sym:<14} {bid:>10.4f} {sp:>4}p  {r5:>10.4f} {atr:>8.4f}  ${mg:>10.2f}")
