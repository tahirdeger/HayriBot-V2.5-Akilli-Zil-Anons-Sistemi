from telegram.ext import BaseMiddleware

class StateValidationMiddleware(BaseMiddleware):
    def __init__(self):
        super().__init__(update_processing_timeout=5)

    async def pre_process_update(self, update, data):
        # Eski durumları temizleme mantığınız
        return await super().pre_process_update(update, data)

