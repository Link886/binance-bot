from binance.client import Client
import time
import os

# ============================================================
# 🔑 API 配置（测试网，实盘时删掉 testnet=True）
# ============================================================
API_KEY = "gZN8yayvsUEINKPylA0N0one8kFEoHXYyAtS9QwajwqjQN4u9FjVVVy5qpHiWSIf"
API_SECRET = "Rz9ZXpZ67I1fCkcGoYROCyLEXyngEJGFMGJECvxGWC3MRLxhLQ4rJjxCetc3dPvG"

client = Client(API_KEY, API_SECRET, testnet=True)

# ============================================================
# 📐 风控参数
# ============================================================
MAX_LOSS_USDT = 5
LEVERAGE = 10
MIN_RR = 1.5
FIXED_TP_RATIO = 0.5
TRAILING_CALLBACK = 0.015
MIN_NOTIONAL = 5.5

# ============================================================
# 🔧 工具函数
# ============================================================
def get_ma(closes, period):
    if len(closes) < period:
        return None
    return sum(closes[-period:]) / period

def get_ema(closes, period):
    if len(closes) < period:
        return None
    k = 2 / (period + 1)
    ema = sum(closes[:period]) / period
    for price in closes[period:]:
        ema = price * k + ema * (1 - k)
    return ema

def get_macd_cross(closes):
    if len(closes) < 35:
        return None
    ema12_prev = get_ema(closes[:-2], 12)
    ema26_prev = get_ema(closes[:-2], 26)
    dif_prev = ema12_prev - ema26_prev if ema12_prev and ema26_prev else None
    ema12_curr = get_ema(closes[:-1], 12)
    ema26_curr = get_ema(closes[:-1], 26)
    dif_curr = ema12_curr - ema26_curr if ema12_curr and ema26_curr else None
    difs = []
    for i in range(26, len(closes)):
        e12 = get_ema(closes[:i+1], 12)
        e26 = get_ema(closes[:i+1], 26)
        if e12 and e26:
            difs.append(e12 - e26)
    if len(difs) < 10:
        return None
    dea_prev = get_ema(difs[:-2], 9)
    dea_curr = get_ema(difs[:-1], 9)
    if None in [dif_prev, dif_curr, dea_prev, dea_curr]:
        return None
    if dif_prev < dea_prev and dif_curr > dea_curr:
        return True
    if dif_prev > dea_prev and dif_curr < dea_curr:
        return False
    return None

def get_kline_data(symbol, interval, limit):
    klines = client.futures_klines(symbol=symbol, interval=interval, limit=limit)
    return [float(k[4]) for k in klines]

def get_current_price(symbol):
    return float(client.futures_symbol_ticker(symbol=symbol)['price'])

def place_order_with_stop(symbol, side, quantity, stop_price):
    client.futures_create_order(
        symbol=symbol, side=side, type='MARKET', quantity=quantity
    )
    stop_side = 'SELL' if side == 'BUY' else 'BUY'
    client.futures_create_order(
        symbol=symbol, side=stop_side, type='STOP_MARKET',
        stopPrice=round(stop_price, 2), closePosition=True
    )

def get_position(symbol):
    try:
        positions = client.futures_position_information(symbol=symbol)
        long_qty = float(positions[0]['positionAmt']) if positions else 0.0
        short_qty = float(positions[1]['positionAmt']) if len(positions) > 1 else 0.0
        return abs(long_qty), abs(short_qty)
    except:
        return 0.0, 0.0

# ============================================================
# 🧠 策略信号
# ============================================================
def check_long_signal(symbol):
    closes_4h = get_kline_data(symbol, '4h', 180)
    closes_1h = get_kline_data(symbol, '1h', 60)
    ma5_4h = get_ma(closes_4h, 5)
    ma13_4h = get_ma(closes_4h, 13)
    ma55_4h = get_ma(closes_4h, 55)
    ema144_4h = get_ema(closes_4h, 144) if len(closes_4h) >= 144 else None
    ema169_4h = get_ema(closes_4h, 169) if len(closes_4h) >= 169 else None
    ma5_1h = get_ma(closes_1h, 5)
    ma13_1h = get_ma(closes_1h, 13)
    ma55_1h = get_ma(closes_1h, 55)
    macd_cross = get_macd_cross(closes_1h)
    price = get_current_price(symbol)
    if not all([ma5_4h, ma13_4h, ma55_4h, ema144_4h, ema169_4h, ma5_1h, ma13_1h, ma55_1h, macd_cross is not None]):
        return None
    bull_4h = price > ma5_4h > ma13_4h > ma55_4h
    ema_bull = price > ema144_4h and price > ema169_4h and ema144_4h > ema169_4h
    golden = macd_cross == True
    pullback = (ma5_1h * 0.995 <= price <= ma5_1h * 1.005) or (ma13_1h * 0.995 <= price <= ma13_1h * 1.005)
    if bull_4h and ema_bull and golden and pullback:
        stop_price = ma55_1h * 0.99
        return {'stop': stop_price, 'ma55_1h': ma55_1h}
    return None

def check_short_signal(symbol):
    closes_4h = get_kline_data(symbol, '4h', 180)
    closes_1h = get_kline_data(symbol, '1h', 60)
    ma5_4h = get_ma(closes_4h, 5)
    ma13_4h = get_ma(closes_4h, 13)
    ma55_4h = get_ma(closes_4h, 55)
    ema144_4h = get_ema(closes_4h, 144) if len(closes_4h) >= 144 else None
    ema169_4h = get_ema(closes_4h, 169) if len(closes_4h) >= 169 else None
    ma5_1h = get_ma(closes_1h, 5)
    ma13_1h = get_ma(closes_1h, 13)
    ma55_1h = get_ma(closes_1h, 55)
    macd_cross = get_macd_cross(closes_1h)
    price = get_current_price(symbol)
    if not all([ma5_4h, ma13_4h, ma55_4h, ema144_4h, ema169_4h, ma5_1h, ma13_1h, ma55_1h, macd_cross is not None]):
        return None
    bear_4h = price < ma5_4h < ma13_4h < ma55_4h
    ema_bear = price < ema144_4h and price < ema169_4h and ema144_4h < ema169_4h
    dead_cross = macd_cross == False
    pullback = (ma5_1h * 0.995 <= price <= ma5_1h * 1.005) or (ma13_1h * 0.995 <= price <= ma13_1h * 1.005)
    if bear_4h and ema_bear and dead_cross and pullback:
        stop_price = ma55_1h * 1.01
        return {'stop': stop_price, 'ma55_1h': ma55_1h}
    return None

# ============================================================
# 🚀 主程序（多币种并发版，从你的脚本修改）
# ============================================================
symbols = ['SUIUSDT', 'SOLUSDT', 'UNIUSDT', 'AAVEUSDT', 'ETHUSDT', 'BTCUSDT', 'ZECUSDT', 'DOGEUSDT']

while True:
    for symbol in symbols:
        try:
            price = get_current_price(symbol)

            # 【改动】实时查询该币种的实际持仓，不再用全局字典锁定
            long_qty, short_qty = get_position(symbol)
            has_position = long_qty > 0 or short_qty > 0

            # 只有该币种完全没有仓位时才寻找信号
            if not has_position:
                # 做多信号
                long_signal = check_long_signal(symbol)
                if long_signal:
                    entry = price
                    stop = long_signal['stop']
                    stop_pct = abs(entry - stop) / entry
                    tp_price = entry * (1 + stop_pct * 2)
                    rr = abs(tp_price - entry) / abs(stop - entry)
                    if rr < MIN_RR:
                        print(f"[{symbol}] 做多盈亏比 {rr:.2f} 不达标，放弃")
                    else:
                        quantity = max(1, round((MAX_LOSS_USDT / stop_pct) / price, 0))
                        print(f"\n🚀 [{symbol}] 做多信号！价格={entry:.4f} 止损={stop:.2f} 止盈={tp_price:.2f} 盈亏比={rr:.2f} 数量={quantity}")
                        place_order_with_stop(symbol, 'BUY', quantity, stop)
                        tp_qty = max(1, round(quantity * FIXED_TP_RATIO, 0))
                        if tp_qty >= 1:
                            client.futures_create_order(
                                symbol=symbol, side='SELL', type='TAKE_PROFIT_MARKET',
                                stopPrice=round(tp_price, 2), quantity=tp_qty
                            )
                        # 【改动】不再手动设置 in_long，持仓状态由下一次实时查询决定

                # 做空信号
                short_signal = check_short_signal(symbol)
                if short_signal:
                    entry = price
                    stop = short_signal['stop']
                    stop_pct = abs(stop - entry) / entry
                    tp_price = entry * (1 - stop_pct * 2)
                    rr = abs(entry - tp_price) / abs(stop - entry)
                    if rr < MIN_RR:
                        print(f"[{symbol}] 做空盈亏比 {rr:.2f} 不达标，放弃")
                    else:
                        quantity = max(1, round((MAX_LOSS_USDT / stop_pct) / price, 0))
                        print(f"\n🐻 [{symbol}] 做空信号！价格={entry:.4f} 止损={stop:.2f} 止盈={tp_price:.2f} 盈亏比={rr:.2f} 数量={quantity}")
                        place_order_with_stop(symbol, 'SELL', quantity, stop)
                        tp_qty = max(1, round(quantity * FIXED_TP_RATIO, 0))
                        if tp_qty >= 1:
                            client.futures_create_order(
                                symbol=symbol, side='BUY', type='TAKE_PROFIT_MARKET',
                                stopPrice=round(tp_price, 2), quantity=tp_qty
                            )

            # 【保留】你原来就有的运行状态日志
            print(f"[{symbol}] 脚本运行正常，等待数据...")

        except Exception as e:
            print(f"[{symbol}] 错误: {e}")

    time.sleep(60)
