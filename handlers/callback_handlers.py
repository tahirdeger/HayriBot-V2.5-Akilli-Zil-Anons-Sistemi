# handlers/callback_handlers.py

import asyncio
import logging
import time
import telegram
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config.settings import media_manager
from utils.event_emitter import ee
from utils.database import (
    ekle_zil, sil_zil, listele_zil, get_job_id, ayar_getir, 
    is_zil_exist, is_bells_enabled, set_bells_enabled
)
from utils.scheduler import scheduler
from apscheduler.jobstores.base import JobLookupError
from utils.internet_check import check_internet
from utils.helpers import (
    create_keyboard, create_confirmation_keyboard, 
    zil_yonetim_keyboard, create_volume_keyboard
)

# ==========================================
# 🧹 CHAT TEMİZLİK YÖNETİCİSİ
# ==========================================
class ChatCleanupManager:
    def __init__(self):
        self.cleanup_tasks = {}
        # İşlem türüne göre bekleme süreleri (saniye)
        self.cleanup_delay = {
            'normal': 45,      
            'duyuru': 45,      
            'zil_ekle': 90,    
            'media': 45        
        }
    
    async def schedule_cleanup(self, chat_id, context, cleanup_type='normal'):
        """Temizlik zamanlayıcısını başlat"""
        # Varsa eski görevi iptal et
        await self.cancel_cleanup(chat_id)
        
        delay = self.cleanup_delay.get(cleanup_type, 60)
        
        # Yeni görevi arka planda başlat
        task = asyncio.create_task(self._execute_cleanup(chat_id, context, delay))
        self.cleanup_tasks[chat_id] = task
        logging.info(f"⏰ Temizlik planlandı: chat_id={chat_id}, tip={cleanup_type}, süre={delay}s")
    
    async def cancel_cleanup(self, chat_id):
        """Mevcut temizlik görevini iptal et"""
        if chat_id in self.cleanup_tasks:
            try:
                self.cleanup_tasks[chat_id].cancel()
                del self.cleanup_tasks[chat_id]
                logging.debug(f"⏹️ Temizlik iptal edildi: {chat_id}")
            except Exception as e:
                logging.warning(f"Temizlik iptal hatası: {str(e)}")
    
    async def _execute_cleanup(self, chat_id, context, delay):
        """Bekle ve temizle"""
        try:
            await asyncio.sleep(delay)
            await self.cleanup_chat(chat_id, context)
        except asyncio.CancelledError:
            pass # Görev iptal edildiyse sessizce çık
        except Exception as e:
            logging.error(f"Temizlik hatası: {str(e)}")
    
    async def cleanup_chat(self, chat_id, context):
        """Sohbeti temizle ve ana menüyü göster"""
        try:
            logging.info(f"🧹 Sohbet temizleniyor: {chat_id}")

            # Kendi gönderdiğimiz mesajları (user_data'dan) sil
            to_delete = context.user_data.get("recent_bot_messages", [])
            
            # Batch halinde silme (Rate limit yememek için)
            for i in range(0, len(to_delete), 5):
                batch = to_delete[i:i+5]
                for msg_id in batch:
                    try:
                        await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
                        await asyncio.sleep(0.1) # Kısa bekleme
                    except Exception:
                        pass # Mesaj zaten silinmişse hatayı yut
            
            # Listeyi temizle
            context.user_data["recent_bot_messages"] = []

            # Ana menüyü tekrar gönder
            menu_text = (
                "🔔 HayriBotV2.5\n"
                "🏫 Zil ve Duyuru Sistemi\n"
                "islematolyesi.odoo.com | 2025\n"
                "\n🔄 Otomatik temizlik yapıldı. Menü yenilendi."
            )
            try:
                msg = await context.bot.send_message(
                    chat_id=chat_id,
                    text=menu_text,
                    reply_markup=create_keyboard()
                )
                # Yeni menü mesajını takip listesine ekle
                context.user_data.setdefault("recent_bot_messages", []).append(msg.message_id)
            except Exception as e:
                logging.warning(f"Menü gönderme hatası: {e}")

            # Görev listesinden çıkar
            if chat_id in self.cleanup_tasks:
                del self.cleanup_tasks[chat_id]

            logging.info(f"✅ Sohbet temizlendi: {chat_id}")
            
        except Exception as e:
            logging.error(f"Sohbet temizleme hatası genel: {str(e)}")

# Global temizlik yöneticisi örneği
cleanup_manager = ChatCleanupManager()

async def trigger_cleanup(chat_id, context, cleanup_type='normal', delay=None):
    """Dışarıdan temizliği tetiklemek için yardımcı fonksiyon"""
    try:
        if delay is not None:
            # Özel gecikme varsa direkt çalıştır (context üzerine kaydet)
            if hasattr(context, '_cleanup_task') and context._cleanup_task:
                context._cleanup_task.cancel()
            context._cleanup_task = asyncio.create_task(
                cleanup_manager._execute_cleanup(chat_id, context, delay)
            )
        else:
            # Standart temizlik yöneticisini kullan
            await cleanup_manager.schedule_cleanup(chat_id, context, cleanup_type)
    except Exception as e:
        logging.error(f"trigger_cleanup hatası: {str(e)}")

# ==========================================
# 🎮 BUTON İŞLEYİCİ (CALLBACK HANDLER)
# ==========================================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tüm buton tıklamalarını yöneten ana fonksiyon"""
    
    query = update.callback_query
    
    # 1. HIZLI İNTERNET KONTROLÜ
    if not await check_internet():
        await query.answer("🌐 İnternet bağlantısı yok!", show_alert=True)
        return

    # 2. YETKİ KONTROLÜ (CANLI KONTROL)
    user_id = str(query.from_user.id)
    raw_ids = ayar_getir("allowed_user_ids")
    allowed_ids = [id.strip() for id in raw_ids.split(",") if id.strip()] if raw_ids else []

    if user_id not in allowed_ids:
        await query.answer(f"❌ Yetkisiz işlem! ID: {user_id}", show_alert=True)
        return

    # 3. BEKLEMEYİ DURDUR
    try:
        await query.answer()
    except Exception:
        pass 

    data = query.data
    volume_lock = asyncio.Lock()

    # --- İŞLEMLER ---

    # A. SES ÇALMA ONAYI
    if data in ['ogrenci_zil', 'ogretmen_zil', 'cikis_zil', 'marscal', 'saygical', 'sirencal','ezanoku', 'selaoku']:
        action_map = {
            'ogrenci_zil': ('🔔 Öğrenci zili çalacak, emin misiniz?', 'zil'),
            'ogretmen_zil': ('👩🏫 Öğretmen zili çalacak, emin misiniz?', 'ogretmen_zil'),
            'cikis_zil': ('🚪 Çıkış zili çalacak, emin misiniz?', 'teneffus_zil'),
            'marscal': ('🎵 İstiklal Marşı çalacak, emin misiniz?', 'mars'),
            'saygical': ('🕯️ Saygı duruşu başlatılacak, emin misiniz?', 'saygi'),
            'sirencal': ('🚨 Siren çalacak, emin misiniz?', 'siren'),
            'ezanoku': ('🕌 Ezan okunacak, emin misiniz?', 'ezan'),
            'selaoku': ('🕌 Sela okunacak, emin misiniz?', 'sela')
        }
        
        if data in action_map:
            text, action = action_map[data]
            await query.edit_message_text(text, reply_markup=create_confirmation_keyboard(action))

    # B. ONAYLANMIŞ ÇALMA
    elif data.startswith('evet_'):
        action = data.split('_')[1]
        media_mapping = {
            'zil': 'zil', 'ogretmen': 'ogretmen_zil', 'teneffus': 'teneffus_zil',
            'mars': 'mars', 'saygi': 'saygi', 'siren': 'siren', 'ezan': 'ezan', 'sela': 'sela'
        }
        media_type = media_mapping.get(action)
        
        if media_type:
            if media_manager.is_media_busy():
                await query.edit_message_text(
                    f"⚠️ Şu anda {media_manager.get_busy_message()} çalıyor.",
                    reply_markup=create_keyboard()
                )
                return

            if media_manager.play_media(media_type, source='telegram'):
                await query.edit_message_text(f"✅ {media_type.capitalize()} çalınıyor...", reply_markup=create_keyboard())
                await trigger_cleanup(user_id, context, 'media')
            else:
                await query.edit_message_text(f"❌ {media_type} çalınamadı!", reply_markup=create_keyboard())

    # C. TÜMÜNÜ DURDUR
    elif data == "tumunu_durdur":
        if not media_manager.is_playing and not media_manager.is_busy:
            await query.answer("ℹ️ Zaten hiçbir ses çalmıyor!", show_alert=False)
            return
            
        media_manager.stop_all_media()
        ee.emit("stop_all_media", {'source': 'telegram', 'chat_id': user_id, 'timestamp': time.time()})
        await query.edit_message_text("⏹️ Tüm sesler durduruldu!", reply_markup=create_keyboard())
        await trigger_cleanup(user_id, context, 'media')

    # D. İPTAL
    elif data.startswith('hayır_'):
        action = data.split('_')[1]
        await query.edit_message_text(f"❌ {action.capitalize()} işlemi iptal edildi", reply_markup=create_keyboard())

    # E. SES AYARLARI
    elif data == "volume_menu":
        current_vol = int(media_manager.get_global_volume() * 100)
        await query.edit_message_text(f"🔊 Ses Seviyesi: %{current_vol}", reply_markup=create_volume_keyboard())

    elif data.startswith("vol_"):
        current = media_manager.get_global_volume()
        step = 0.1
        new_vol = current

        if data == "vol_mute": new_vol = 0.0
        elif data == "vol_50": new_vol = 0.5
        elif data == "vol_100": new_vol = 1.0
        elif data == "vol_up": new_vol = min(1.0, current + step)
        elif data == "vol_down": new_vol = max(0.0, current - step)

        asyncio.create_task(_debounced_volume_update(query, new_vol, volume_lock))

    # F. SİSTEM DURUMU
    elif data == 'bilgisayardurum':
        is_online = await check_internet()
        status = "🟢 Çalışıyor" if is_online else "🔴 Kapalı"
        await query.edit_message_text(
            f"💻 Sistem Durumu:\n• İnternet: {status}\n• Saat: {time.strftime('%H:%M:%S')}",
            reply_markup=create_keyboard()
        )
    
    # ----------------------------------
    # K. PC KAPATMA İŞLEMLERİ (FİNAL DÜZELTME)
    # ----------------------------------
    # 1. Butona ilk basıldığında ("pckapat") -> Onay Sor
    elif data == 'pckapat':
        keyboard = [
            [
                InlineKeyboardButton("✅ Evet, Kapat", callback_data="pckapat_evet"),
                InlineKeyboardButton("❌ İptal", callback_data="pckapat_hayir")
            ]
        ]
        await query.edit_message_text(
            "⚠️ <b>DİKKAT:</b> Bilgisayar tamamen kapatılacak!\nBu işlemden emin misiniz?",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )

    # 2. Onay verilirse ("pckapat_evet") -> Kapat
    elif data == 'pckapat_evet':
        try:
            await query.edit_message_text("💻 Bilgisayar 5 saniye içinde kapatılıyor... Güle güle! 👋")
        except Exception as e:
            logging.warning(f"Mesaj düzenleme uyarısı: {e}")

        logging.critical(f"🔴 TELEGRAM ÜZERİNDEN KAPATMA KOMUTU: Kullanıcı {user_id}")
        
        import os
        os.system("shutdown /s /t 5") 

    # 3. İptal edilirse ("pckapat_hayir") -> Vazgeç
    elif data == 'pckapat_hayir':
        await query.edit_message_text(
            "✅ PC kapatma işlemi iptal edildi.",
            reply_markup=create_keyboard()
        )

    # G. DUYURU GİRİŞİ
    elif data == 'textgiris':
        context.user_data['expecting_text'] = True
        await query.edit_message_text(
            "📢 Lütfen duyuru metnini girin:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ İptal", callback_data="ana_menu")]])
        )

    # H. ANA MENÜ
    elif data in ['ana_menu', 'tamam']:
        await cleanup_manager.cleanup_chat(int(user_id), context)

    # I. ZİL YÖNETİMİ
    elif data == 'zil_yonet':
        await trigger_cleanup(user_id, context, 'zil_ekle')
        await query.edit_message_text("🔔 Zil Yönetim Paneli", reply_markup=zil_yonetim_keyboard())

    elif data == 'toplu_ekle':
        context.user_data['toplu_ekle_mod'] = True
        await query.edit_message_text(
            "📥 Toplu ekleme formatı:\nÖğrenci-Öğretmen-Teneffüs\nÖrnek: 08:30-08:35-09:00",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ İptal", callback_data="zil_yonet")]])
        )
    
    elif data == 'tek_ekle':
        context.user_data['tek_ekle_mod'] = True
        await query.edit_message_text(
            "⏰ Tek zil eklemek için format:\nTür-Saat\nÖrnek:\nogrenci-08:30",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ İptal", callback_data="zil_yonet")]])
        )

    elif data == 'zil_list':
        await show_zil_list(query)

    elif data.startswith('sil_'):
        try:
            zil_id = int(data.split('_')[1])
            job_id = get_job_id(zil_id)
            if job_id:
                try: scheduler.remove_job(job_id)
                except JobLookupError: pass
            
            sil_zil(zil_id)
            await show_zil_list(query)
            await query.answer("✅ Zil silindi")
        except Exception:
            await query.answer("❌ Silme başarısız!")

    # J. ZİLLERİ AÇ/KAPA
    elif data == "toggle_bells":
        new_state = not is_bells_enabled()
        if set_bells_enabled(new_state):
            status = "aktif" if new_state else "pasif"
            await query.edit_message_text(f"🔔 Ziller {status} yapıldı!", reply_markup=create_keyboard())
        else:
            await query.answer("❌ Hata oluştu!")

    elif data == 'noop':
        await query.answer()

# ==========================================
# YARDIMCI FONKSİYONLAR
# ==========================================
async def _debounced_volume_update(query, new_vol, lock):
    """Ses seviyesi güncelleme yardımcısı"""
    async with lock:
        try:
            media_manager.set_global_volume(new_vol)
            ee.emit("volume_changed", new_vol * 100)
            await query.edit_message_text(
                f"🔊 Ses Seviyesi: %{int(new_vol * 100)}",
                reply_markup=create_volume_keyboard()
            )
        except Exception as e:
            logging.error(f"Ses güncelleme hatası: {e}")

async def show_zil_list(query):
    """Zil listesini göster"""
    try:
        zil_liste = listele_zil()
        if not zil_liste:
            await query.edit_message_text("❌ Kayıtlı zil yok!", reply_markup=zil_yonetim_keyboard())
            return

        keyboard = []
        for zil in zil_liste:
            try:
                zil_id, saat, tur, _ = zil
                keyboard.append([InlineKeyboardButton(f"⏰ {saat} ({tur}) ❌", callback_data=f"sil_{zil_id}")])
            except: continue
        
        keyboard.append([InlineKeyboardButton("🔙 Geri", callback_data="zil_yonet")])
        await query.edit_message_text("🔔 Kayıtlı Ziller:", reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception as e:
        logging.error(f"Zil listeleme hatası: {e}")
        await query.edit_message_text("⚠️ Liste alınamadı!", reply_markup=zil_yonetim_keyboard())