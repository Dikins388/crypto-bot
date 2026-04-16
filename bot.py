import os
import logging
from dotenv import load_dotenv

load_dotenv()

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from analyzer import CryptoAnalyzer
from config import Config

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

logger = logging.getLogger(__name__)

analyzer = CryptoAnalyzer()
subscribed_users = set()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    subscribed_users.add(update.effective_user.id)

    pairs_list = " • ".join(
        [p.replace("USDT", "/USDT") for p in Config.PAIRS]
    )

    await update.message.reply_text(
        "🤖 Crypto Signal Bot\n\n"
        "Я анализирую рынок и отправляю сигналы:\n"
        "🟢 ПОКУПАЙ — возможный рост\n"
        "🔴 ПРОДАВАЙ — возможное падение\n\n"
        f"📊 Пары: {pairs_list}\n"
        "⏱ Проверка каждые 15 минут\n\n"
        "/signal — ручная проверка\n"
        "/stop — отписаться\n"
        "/status — статус\n\n"
        "Ты подписан.",
    )


async def stop_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    subscribed_users.discard(update.effective_user.id)

    await update.message.reply_text(
        "Ты отписан от сигналов.\n"
        "Напиши /start чтобы снова подключиться."
    )


async def signal_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Анализирую рынок...")

    try:
        signals = await analyzer.get_all_signals()
    except Exception as e:
        logger.error(f"Signal error: {e}")
        await update.message.reply_text("Ошибка анализа рынка.")
        return

    if not signals:
        await update.message.reply_text("Сигналов сейчас нет.")
        return

    for msg in signals:
        await update.message.reply_text(msg)


async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"Статус бота\n\n"
        f"Подписчиков: {len(subscribed_users)}\n"
        f"Пар: {len(Config.PAIRS)}\n"
        f"Интервал: 15 минут\n"
        f"Биржа: Binance\n"
    )


async def auto_check(context: ContextTypes.DEFAULT_TYPE):
    if not subscribed_users:
        return

    try:
        signals = await analyzer.get_all_signals()
    except Exception as e:
        logger.error(f"Auto-check error: {e}")
        return

    if not signals:
        return

    logger.info(
        f"Signals: {len(signals)} | Users: {len(subscribed_users)}"
    )

    for user_id in list(subscribed_users):
        try:
            for msg in signals:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=msg
                )
        except Exception as e:
            logger.error(f"Send error {user_id}: {e}")
            subscribed_users.discard(user_id)


def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")

    if not token:
        raise ValueError(
            "Missing TELEGRAM_BOT_TOKEN environment variable"
        )

    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop_cmd))
    app.add_handler(CommandHandler("signal", signal_cmd))
    app.add_handler(CommandHandler("status", status_cmd))

    app.job_queue.run_repeating(
        auto_check,
        interval=Config.CHECK_INTERVAL,
        first=30
    )

    logger.info("Bot started")

    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()