import aiohttp
import pandas as pd
import numpy as np
from datetime import datetime
from config import Config
import logging

logger = logging.getLogger(__name__)


class CryptoAnalyzer:

    async def fetch_klines(self, symbol: str) -> pd.DataFrame | None:
        """Загружаем свечи с Binance"""
        url = f"{Config.BINANCE_BASE_URL}/api/v3/klines"
        params = {
            "symbol": symbol,
            "interval": Config.TIMEFRAME,
            "limit": Config.CANDLES_LIMIT
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    data = await resp.json()
                    df = pd.DataFrame(data, columns=[
                        "time", "open", "high", "low", "close", "volume",
                        "close_time", "quote_vol", "trades", "taker_buy_base",
                        "taker_buy_quote", "ignore"
                    ])
                    df["close"] = df["close"].astype(float)
                    df["high"] = df["high"].astype(float)
                    df["low"] = df["low"].astype(float)
                    return df
        except Exception as e:
            logger.error(f"Ошибка загрузки {symbol}: {e}")
            return None

    def calc_rsi(self, closes: pd.Series) -> float:
        """Считаем RSI"""
        delta = closes.diff()
        gain = delta.clip(lower=0).rolling(Config.RSI_PERIOD).mean()
        loss = (-delta.clip(upper=0)).rolling(Config.RSI_PERIOD).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return round(rsi.iloc[-1], 1)

    def calc_macd(self, closes: pd.Series) -> tuple[float, float]:
        """Возвращаем (macd_line, signal_line)"""
        ema_fast = closes.ewm(span=Config.MACD_FAST, adjust=False).mean()
        ema_slow = closes.ewm(span=Config.MACD_SLOW, adjust=False).mean()
        macd = ema_fast - ema_slow
        signal = macd.ewm(span=Config.MACD_SIGNAL, adjust=False).mean()
        return round(macd.iloc[-1], 4), round(signal.iloc[-1], 4)

    def format_price(self, price: float) -> str:
        """Красивый формат цены"""
        if price >= 1000:
            return f"{price:,.2f}"
        elif price >= 1:
            return f"{price:.4f}"
        else:
            return f"{price:.6f}"

    def format_pair_name(self, symbol: str) -> str:
        base = symbol.replace("USDT", "")
        return f"{base}/USDT"

    def analyze_symbol(self, symbol: str, df: pd.DataFrame) -> dict | None:
        """Анализируем одну монету, возвращаем сигнал или None"""
        closes = df["close"]
        price = closes.iloc[-1]

        rsi = self.calc_rsi(closes)
        macd, macd_sig = self.calc_macd(closes)

        # Определяем сигнал
        macd_bullish = macd > macd_sig          # MACD выше сигнальной → рост
        macd_bearish = macd < macd_sig          # MACD ниже сигнальной → падение
        rsi_oversold = rsi < Config.RSI_OVERSOLD
        rsi_overbought = rsi > Config.RSI_OVERBOUGHT

        if rsi_oversold and macd_bullish:
            signal_type = "BUY"
        elif rsi_overbought and macd_bearish:
            signal_type = "SELL"
        else:
            return None  # Нет чёткого сигнала

        return {
            "symbol": symbol,
            "signal": signal_type,
            "price": price,
            "rsi": rsi,
            "macd": macd,
            "macd_signal": macd_sig,
        }

    def build_message(self, data: dict) -> str:
        """Строим читаемое сообщение для пользователя"""
        symbol = data["symbol"]
        signal = data["signal"]
        price = data["price"]
        rsi = data["rsi"]
        pair = self.format_pair_name(symbol)
        p = self.format_price

        if signal == "BUY":
            tp1 = price * (1 + Config.TP1_PERCENT / 100)
            tp2 = price * (1 + Config.TP2_PERCENT / 100)
            sl  = price * (1 - Config.SL_PERCENT  / 100)
            emoji = "🟢"
            action = "ПОКУПАЙ"
            lines = [
                f"{emoji} *{action} {pair}*",
                f"",
                f"💰 Цена входа:  `${p(price)}`",
                f"🎯 Цель 1:       `${p(tp1)}`  (+{Config.TP1_PERCENT}%)",
                f"🎯 Цель 2:       `${p(tp2)}`  (+{Config.TP2_PERCENT}%)",
                f"🛑 Стоп-лосс:  `${p(sl)}`  (-{Config.SL_PERCENT}%)",
                f"",
                f"📊 RSI: `{rsi}` (перепродан — отскок вверх)",
                f"📈 MACD: разворот вверх",
                f"",
                f"⏱ Таймфрейм: 15 минут",
            ]
        else:
            tp1 = price * (1 - Config.TP1_PERCENT / 100)
            tp2 = price * (1 - Config.TP2_PERCENT / 100)
            sl  = price * (1 + Config.SL_PERCENT  / 100)
            emoji = "🔴"
            action = "ПРОДАВАЙ"
            lines = [
                f"{emoji} *{action} {pair}*",
                f"",
                f"💰 Цена входа:  `${p(price)}`",
                f"🎯 Цель 1:       `${p(tp1)}`  (-{Config.TP1_PERCENT}%)",
                f"🎯 Цель 2:       `${p(tp2)}`  (-{Config.TP2_PERCENT}%)",
                f"🛑 Стоп-лосс:  `${p(sl)}`  (+{Config.SL_PERCENT}%)",
                f"",
                f"📊 RSI: `{rsi}` (перекуплен — откат вниз)",
                f"📈 MACD: разворот вниз",
                f"",
                f"⏱ Таймфрейм: 15 минут",
            ]

        now = datetime.now().strftime("%H:%M %d.%m.%Y")
        lines.append(f"🕐 Сигнал: {now}")
        return "\n".join(lines)

    async def get_all_signals(self) -> list[str]:
        """Проверяем все пары и возвращаем список сообщений"""
        messages = []
        for symbol in Config.PAIRS:
            df = await self.fetch_klines(symbol)
            if df is None or len(df) < 30:
                continue
            result = self.analyze_symbol(symbol, df)
            if result:
                messages.append(self.build_message(result))
        return messages