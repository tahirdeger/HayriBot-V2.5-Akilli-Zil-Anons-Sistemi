# handlers/command_handlers.py

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, MessageHandler, filters
from handlers.callback_handlers import trigger_cleanup
from utils.helpers import create_keyboard, create_volume_keyboard, generate_job_id, get_duration, zil_yonetim_keyboard
from config.settings import DB_PATH, media_manager
from utils.database import ayar_getir, ayar_guncelle, is_zil_exist, ekle_zil, listele_zil, get_job_id, sil_zil, is_bells_enabled, set_bells_enabled
from utils.scheduler import scheduler
from apscheduler.jobstores.base import ConflictingIdError
import sqlite3
import logging
import os
import sys
import certifi
import asyncio
import re
from mutagen.mp3 import MP3
import vlc
import time
from utils.event_emitter import ee
import tempfile

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO,
    handlers=[
        logging.FileHandler("app.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)

MEDIA_DIR = media_manager.MEDIA_DIR
ALLOWED_IDS = [id.strip() for id in ayar_getir("allowed_user_ids").split(",") if id.strip()]
BOT_TOKEN = ayar_getir("telegram_api_key")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    allowed_ids = ayar_getir("allowed_user_ids")
    ALLOWED_IDS = [id.strip() for id in allowed_ids.split(",") if id.strip()] if allowed_ids else []
    
    if user_id not in ALLOWED_IDS:
        await update.message.reply_text(
            "⛔ Bu bota erişim izniniz yok!\n"
            "Lütfen yönetici ile iletişime geçin."
        )
        return
    
    bells_status = "aktif" if is_bells_enabled() else "pasif"
    text = (
        "🔔 *Okul Zil Yönetim Sistemi*\n"
        f"🔄 Durum: Ziller şu anda *{bells_status}*\n"
        "Aşağıdaki seçenekleri kullanabilirsiniz:"
    )
    await update.message.reply_text(
        text,
        reply_markup=create_keyboard(),
        parse_mode="Markdown"
    )
    
    # BAŞLANGIÇ TEMİZLİĞİ
    chat_id = update.effective_chat.id
    await trigger_cleanup(chat_id, context, 'normal') # Normal temizlik başlat

async def handle_api_key_change(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id not in ALLOWED_IDS:
        return
    
    try:
        if not context.args:
            await update.message.reply_text("❌ Geçersiz format! Doğru kullanım: /api_key <yeni_api_key>")
            return

        new_api_key = context.args[0]
        current_key = ayar_getir("telegram_api_key")
        
        if new_api_key == current_key:
            await update.message.reply_text("⚠️ Aynı API Key zaten kullanımda!")
            return
            
        if ayar_guncelle("telegram_api_key", new_api_key):
            await update.message.reply_text("✅ API Key güncellendi! Uygulama güvenli bir şekilde yeniden başlatılıyor...")
            from utils.event_emitter import ee
            ee.emit("restart_bot") 
        else:
            await update.message.reply_text("❌ API Key güncellenemedi!")
            
    except IndexError:
        await update.message.reply_text("❌ Geçersiz format! Doğru kullanım: /api_key <yeni_api_key>")
    except Exception as e:
        logging.error(f"API_KEY Değişim Hatası: {str(e)}", exc_info=True)
        await update.message.reply_text("❌ Bir hata oluştu!")


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id not in ALLOWED_IDS:
        return

    text = update.message.text.strip().lower()
    
    # ---------------------------------------------------------
    # 1. PC KAPATMA KOMUTU (GÜNCELLENDİ: ONAY MEKANİZMASI)
    # ---------------------------------------------------------
    if text in ["/pckapat", "pc kapat", "bilgisayarı kapat", "kapat", "sistemi kapat"]:
        keyboard = [
            [
                InlineKeyboardButton("✅ Evet, Kapat", callback_data="pckapat_evet"),
                InlineKeyboardButton("❌ İptal", callback_data="pckapat_hayir")
            ]
        ]
        await update.message.reply_text(
            "⚠️ <b>DİKKAT:</b> Bilgisayar tamamen kapatılacak!\nBu işlemden emin misiniz?",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
        return
    # ---------------------------------------------------------
    
    # Tüm sesleri durdur komutu
    if text in ["dur", "durdur", "stop", "stop all", "tümünü durdur"]:
        await stop_all(update, context)
        return
    
    # Beklenen metin (Duyuru vb.)
    if context.user_data.get('expecting_text'):
        await handle_announcement(update, context, user_id)
        return
        
    if context.user_data.get('toplu_ekle_mod'):
        await handle_toplu_ekle(update, context)
        return
    
    if context.user_data.get('tek_ekle_mod'):
        await handle_tek_ekle(update, context)
        return
    
    await update.message.reply_text(
        "⚠️ Geçersiz komut! Lütfen menüden seçim yapın.",
        reply_markup=create_keyboard()
    )

async def reset_context(context: ContextTypes.DEFAULT_TYPE):
    keys_to_remove = ['toplu_ekle_mod', 'tek_ekle_mod', 'expecting_text']
    for key in keys_to_remove:
        context.user_data.pop(key, None)

async def handle_announcement(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: str):
    text = update.message.text.strip()
    processing_msg = None

    try:
        if not text:
            raise ValueError("Boş metin gönderildi!")

        clean_text = re.sub(r'[^\w\s.,!?]', '', text)
        if not clean_text:
            raise ValueError("Geçersiz veya boş metin!")

        # İşlem mesajını gönder
        processing_msg = await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="🔊 Duyuru başlıyor..."
        )

        # Kullanıcı bilgisi
        user_name = update.effective_user.first_name
        if update.effective_user.last_name:
            user_name += f" {update.effective_user.last_name}"
        user_name += f" (@{update.effective_user.username})" if update.effective_user.username else ""

        # Duyuru metnini GUI'ye event ile gönder
        ee.emit("telegram_duyuru_metni", {
            "metin": clean_text,
            "user": user_name,
            "chat_id": update.effective_chat.id
        })

        # DUYURU SONRASI TEMİZLİK
        chat_id = update.effective_chat.id
        await asyncio.sleep(2)  # son mesajların çıkması için küçük bekleme
        await trigger_cleanup(chat_id, context, 'duyuru')

    except Exception as exc:
        logging.error(f"Telegram duyuru iletme hatası: {str(exc)}", exc_info=True)
        error_msg = "❌ Duyuru iletiminde hata oluştu. Lütfen tekrar deneyin."
        
        # Telegram'a hata bildirimi gönder
        ee.emit("telegram_duyuru_durumu", {
            "durum": "hata",
            "mesaj": f"Duyuru iletim hatası: {str(exc)}",
            "chat_id": update.effective_chat.id
        })
        
        if processing_msg:
            await processing_msg.edit_text(error_msg)
        else:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=error_msg
            )
        
        # Hata durumunda da temizlik planla
        chat_id = update.effective_chat.id
        await trigger_cleanup(chat_id, context, 'normal')
    finally:
        context.user_data.pop('expecting_text', None)


def sil_zil_by_job_id(job_id):
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("DELETE FROM zil_saatleri WHERE job_id=?", (job_id,))
            conn.commit()
            logging.info(f"Rollback: Zil silindi (job_id: {job_id})")
    except Exception as e:
        logging.error(f"Rollback hatası (job_id: {job_id}): {str(e)}", exc_info=True)
        
async def show_zil_list(query):
    try:
        zil_liste = listele_zil()
        logging.info(f"Listeleme verisi: {zil_liste}")
        
        if not zil_liste:
            await query.edit_message_text("❌ Kayıtlı zil bulunamadı!", reply_markup=zil_yonetim_keyboard())
            return

        keyboard = []
        for entry in zil_liste:
            try:
                zil_id, saat, tur, _ = entry
                keyboard.append([
                    InlineKeyboardButton(
                        f"⏰ {saat} ({tur.capitalize()}) ❌",
                        callback_data=f"sil_{zil_id}"
                    )
                ])
            except IndexError:
                logging.error(f"Geçersiz veri formatı: {entry}")
                continue

        keyboard.append([InlineKeyboardButton("🔙 Geri", callback_data="zil_yonet")])
        
        await query.edit_message_text(
            "🔔 Kayıtlı Zil Saatleri:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    except Exception as e:
        logging.error(f"Listeleme hatası: {str(e)}", exc_info=True)
        await query.edit_message_text(
            "⚠️ Liste yüklenirken hata oluştu!",
            reply_markup=zil_yonetim_keyboard()
        )

async def handle_tek_ekle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        text = update.message.text.strip()
        user_id = str(update.effective_user.id)

        if '-' not in text:
            await update.message.reply_text(
                "❌ Geçersiz format! Doğru format:\n"
                "Tür-Saat. Örnek:\n"
                "ogrenci-08:30 \n" 
                "ogretmen-08:35 \n" 
                "teneffus-09:15 ",
                reply_markup=InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("🔙 Yeniden Dene", callback_data="tek_ekle"),
                        InlineKeyboardButton("🏠 Ana Menü", callback_data="ana_menu")
                    ]
                ])
            )
            return

        tur, saat = text.split('-', 1)
        tur = tur.strip().lower()
        saat = saat.strip()

        tur = tur.replace("öğrenci", "ogrenci") \
                 .replace("öğretmen", "ogretmen") \
                 .replace("teneffüs", "teneffus")
        
        if tur not in ['ogrenci', 'ogretmen', 'teneffus']:
            await update.message.reply_text(
                "❌ Geçersiz tür! Geçerli türler:\n"
                "- ogrenci\n- ogretmen\n- teneffus",
                reply_markup=InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("🔙 Yeniden Dene", callback_data="tek_ekle"),
                        InlineKeyboardButton("🏠 Ana Menü", callback_data="ana_menu")
                    ]
                ])
            )
            return

        if not re.match(r'^([0-1][0-9]|2[0-3]):[0-5][0-9]$', saat):
            await update.message.reply_text(
                "❌ Geçersiz saat formatı! Örnek: 08:30",
                reply_markup=InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("🔙 Yeniden Dene", callback_data="tek_ekle"),
                        InlineKeyboardButton("🏠 Ana Menü", callback_data="ana_menu")
                    ]
                ])
            )
            return

        if is_zil_exist(saat, tur):
            await update.message.reply_text(
                f"⏰ {tur.capitalize()} zili {saat}'te zaten kayıtlı!",
                reply_markup=InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("🔙 Yeniden Dene", callback_data="tek_ekle"),
                        InlineKeyboardButton("🏠 Ana Menü", callback_data="ana_menu")
                    ]
                ])
            )
            return

        logging.debug(f"Telegram: Tek zil ekleme denemesi: saat={saat}, tur={tur}")
        if ekle_zil(saat, tur):
            logging.info(f"Telegram: Zil eklendi: {saat}, {tur}")
            
            try:
                from utils.scheduler import refresh_scheduler
                refresh_scheduler()
                logging.info("♻️ Zamanlayıcı yenilendi (Telegram tekli ekleme)")
            except Exception as e:
                logging.error(f"⚠️ Zamanlayıcı yenilenemedi: {str(e)}")
            
            mesaj = f"✅ {tur.capitalize()} zili {saat} başarıyla eklendi!"
        else:
            logging.error(f"Telegram: Zil ekleme başarısız: {saat}, {tur}")
            mesaj = "❌ Zil eklenemedi, zaten kayıtlı veya hata oluştu!"

        await update.message.reply_text(
            mesaj,
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("➕ Yeni Ekle", callback_data="tek_ekle"),
                    InlineKeyboardButton("🏠 Ana Menü", callback_data="ana_menu")
                ]
            ])
        )
        
        chat_id = update.effective_chat.id
        await trigger_cleanup(chat_id, context, 'zil_ekle')
        context.user_data.pop('tek_ekle_mod', None)

    except Exception as e:
        logging.error(f"Telegram: Tek ekleme hatası: {str(e)}", exc_info=True)
        await update.message.reply_text(
            "⚠️ Beklenmeyen bir hata oluştu! Lütfen tekrar deneyin.",
            reply_markup=create_keyboard()
        )
        chat_id = update.effective_chat.id
        await trigger_cleanup(chat_id, context, 'normal')
        context.user_data.pop('tek_ekle_mod', None)

async def handle_toplu_ekle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        text = update.message.text.strip()
        user_id = str(update.effective_user.id)

        if text.count('-') != 2:
            await update.message.reply_text(
                "❌ Geçersiz format! Doğru format:\n"
                "Öğrenci-Öğretmen-Teneffüs\n"
                "Örnek: 08:30-08:35-09:00",
                reply_markup=InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("🔄 Yeniden Dene", callback_data="toplu_ekle"),
                        InlineKeyboardButton("🏠 Ana Menü", callback_data="ana_menu")
                    ]
                ])
            )
            return

        saatler = text.split('-')
        turler = ['ogrenci', 'ogretmen', 'teneffus']
        basarili = 0
        hatali_saatler = []

        for i in range(3):
            saat = saatler[i].strip()
            tur = turler[i]

            if not re.match(r'^([0-1][0-9]|2[0-3]):[0-5][0-9]$', saat):
                hatali_saatler.append(f"{tur} ({saat}) - Geçersiz saat formatı")
                continue

            if is_zil_exist(saat, tur):
                hatali_saatler.append(f"{tur} ({saat}) - Bu saatte zaten kayıtlı")
                continue

            logging.debug(f"Telegram: Toplu zil ekleme denemesi: saat={saat}, tur={tur}")
            if ekle_zil(saat, tur):
                basarili += 1
                logging.info(f"Telegram: Zil eklendi: {saat}, {tur}")
            else:
                hatali_saatler.append(f"{tur} ({saat}) - Veritabanına eklenemedi")
                logging.error(f"Telegram: Zil ekleme başarısız: {saat}, {tur}")

        mesaj = f"✅ Başarıyla eklenenler: {basarili}\n❌ Hatalılar: {len(hatali_saatler)}"
        
        if basarili > 0:
            try:
                from utils.scheduler import refresh_scheduler
                refresh_scheduler()
                logging.info("♻️ Zamanlayıcı yenilendi (Telegram toplu ekleme)")
            except Exception as e:
                logging.error(f"⚠️ Zamanlayıcı yenilenemedi: {str(e)}")
        
        if hatali_saatler:
            mesaj += "\n\nHata Detayları:\n- " + "\n- ".join(hatali_saatler)
        else:
            mesaj += "\n\nTüm ziller başarıyla eklendi!"

        await update.message.reply_text(
            mesaj,
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("🔄 Yeni Ekle", callback_data="toplu_ekle"),
                    InlineKeyboardButton("🏠 Ana Menü", callback_data="ana_menu")
                ]
            ])
        )

        chat_id = update.effective_chat.id
        await trigger_cleanup(chat_id, context, 'zil_ekle')
        context.user_data.pop('toplu_ekle_mod', None)

    except Exception as e:
        logging.error(f"Telegram: Toplu ekleme hatası: {str(e)}", exc_info=True)
        await update.message.reply_text(
            "⚠️ Beklenmeyen bir hata oluştu! Lütfen tekrar deneyin.",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("🔄 Yeniden Dene", callback_data="toplu_ekle"),
                    InlineKeyboardButton("🏠 Ana Menü", callback_data="ana_menu")
                ]
            ])
        )
        chat_id = update.effective_chat.id
        await trigger_cleanup(chat_id, context, 'normal')
        context.user_data.pop('toplu_ekle_mod', None)

async def _debounced_volume_update(update, volume, lock):
    async with lock:
        try:
            media_manager.set_global_volume(volume / 100)
            ee.emit("volume_changed", volume)
            await update.message.reply_text(
                f"✅ Ses seviyesi %{volume} olarak ayarlandı",
                reply_markup=create_volume_keyboard()
            )
            logging.info(f"Ses seviyesi güncellendi: {volume}%")
        except Exception as e:
            logging.error(f"Ses kontrolü hatası: {str(e)}", exc_info=True)
            await update.message.reply_text(
                f"❌ Ses seviyesi ayarlanamadı: {str(e)}",
                reply_markup=create_volume_keyboard()
            )

async def volume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id not in ALLOWED_IDS:
        return
    
    volume_lock = asyncio.Lock()
    
    args = context.args
    if not args:
        current = media_manager.get_global_volume() * 100
        await update.message.reply_text(
            f"🔊 Şu anki ses seviyesi: %{int(current)}\n"
            "Ayarlamak için: /volume <0-100>",
            reply_markup=create_volume_keyboard()
        )
        return
    
    try:
        volume = int(args[0])
        if 0 <= volume <= 100:
            asyncio.create_task(_debounced_volume_update(update, volume, volume_lock))
        else:
            await update.message.reply_text(
                "⚠️ Lütfen 0-100 arası değer girin!",
                reply_markup=create_volume_keyboard()
            )
    except ValueError:
        await update.message.reply_text(
            "❌ Geçersiz değer! Sadece sayı girin.",
            reply_markup=create_volume_keyboard()
        )
    except Exception as e:
        logging.error(f"Ses kontrolü hatası: {str(e)}", exc_info=True)
        await update.message.reply_text(
            f"❌ Ses seviyesi ayarlanırken bir hata oluştu!",
            reply_markup=create_volume_keyboard()
        )

async def toggle_bells(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    allowed_ids = ayar_getir("allowed_user_ids")
    ALLOWED_IDS = [id.strip() for id in allowed_ids.split(",") if id.strip()] if allowed_ids else []
    
    if user_id not in ALLOWED_IDS:
        await update.message.reply_text("⛔ Yetkisiz erişim!")
        return
    
    try:
        new_state = not is_bells_enabled()
        if set_bells_enabled(new_state):
            status = "aktif" if new_state else "pasif"
            await update.message.reply_text(
                f"🔔 Ziller {status} yapıldı!",
                reply_markup=create_keyboard()
            )
            logging.info(f"Telegram: Ziller {status} yapıldı")
        else:
            await update.message.reply_text(
                "❌ Zil durumu değiştirilemedi!",
                reply_markup=create_keyboard()
            )
    except Exception as e:
        logging.error(f"Telegram: Zil durumu değiştirme hatası: {str(e)}", exc_info=True)
        await update.message.reply_text(
            f"❌ Hata: {str(e)}",
            reply_markup=create_keyboard()
        )


async def stop_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id not in ALLOWED_IDS:
        await update.message.reply_text("⛔ Yetkisiz erişim!")
        return
    
    try:
        # MediaManager'ın stop_all_media metodunu kullan
        media_manager.stop_all_media()
        await update.message.reply_text(
            "⏹️ Tüm sesler durduruldu!",
            reply_markup=create_keyboard()
        )
        logging.info("Telegram: Tüm sesler durduruldu")
    except Exception as e:
        logging.error(f"Telegram: Ses durdurma hatası: {str(e)}", exc_info=True)
        await update.message.reply_text(
            "❌ Sesler durdurulurken hata oluştu!",
            reply_markup=create_keyboard()
        )


async def send_telegram_notification(chat_id, message, message_type="info"):
    """Telegram'a bildirim gönder"""
    try:
        from main import current_bot_application
        
        if current_bot_application:
            emoji = "🔔"
            if message_type == "error":
                emoji = "❌"
            elif message_type == "warning":
                emoji = "⚠️"
            elif message_type == "success":
                emoji = "✅"
                
            await current_bot_application.bot.send_message(
                chat_id=chat_id,
                text=f"{emoji} {message}"
            )
    except Exception as e:
        logging.error(f"Telegram bildirim gönderme hatası: {str(e)}")