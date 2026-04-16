class Config:
    # Топ-5 самых волатильных крипто пар
    PAIRS = [
        "SOLUSDT",
        "DOGEUSDT",
        "AVAXUSDT",
        "BTCUSDT",
        "ETHUSDT",
    ]

    TIMEFRAME = "15m"
    CANDLES_LIMIT = 100

    RSI_PERIOD = 14
    RSI_OVERSOLD = 35
    RSI_OVERBOUGHT = 65

    MACD_FAST = 12
    MACD_SLOW = 26
    MACD_SIGNAL = 9

    CHECK_INTERVAL = 15 * 60  # каждые 15 минут

    BINANCE_BASE_URL = "https://api.binance.com"

    TP1_PERCENT = 1.5
    TP2_PERCENT = 3.0
    SL_PERCENT = 1.0
