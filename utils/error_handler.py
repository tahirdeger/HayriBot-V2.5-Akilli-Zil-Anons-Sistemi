import logging
from telegram import Update
from telegram.ext import ContextTypes
from telegram.error import NetworkError

async def global_error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    try:
        error_info = {
            "user": update.effective_user.id if update else None,
            "message": update.message.text if update and hasattr(update, 'message') else None,
            "error": str(context.error)
        }
        if isinstance(context.error, NetworkError):
            # NetworkError için stack trace olmadan sadece uyarı logla
            logging.warning(f"NetworkError: İnternet bağlantısı kesildi, bot polling durduruluyor: {str(context.error)}")
        else:
            # Diğer hatalar için tam stack trace
            logging.critical("Kritik Hata:", extra=error_info, exc_info=True)
        
        if update and hasattr(update, 'effective_chat'):
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="⚠️ Bir sistem hatası oluştu. Lütfen tekrar deneyin."
            )
    except Exception as e:
        logging.error(f"Hata işleyicide exception: {str(e)}", exc_info=True)


