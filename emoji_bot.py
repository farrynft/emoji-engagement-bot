from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
import re
import logging
from datetime import datetime, time as dt_time
import asyncio

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Config
TOKEN = "7958058721:AAEXx4Zw3RYj_7Bnr_eMfUWcsjlxYbsfRBk"
ADMIN_ID = 1004037545
GROUP_ID = -1002158416026
TOPIC_ID = 33348
RULES_CHANNEL = "https://t.me/zaxengage/12/33361"

LAST_MESSAGES = []
LAST_RULES_MESSAGE_ID = None

# SIRA NUMARASI
message_counter = 0

# KULLANICI PAYLAŞIM TAKİBİ
user_last_share_number = {}

# İstatistikler
DAILY_STATS = {
    'links_shared': 0,
    'violations_emoji': 0,
    'violations_cooldown': 0,
    'date': datetime.now().date()
}

RULES_TEXT = """
📚 Check rules / Kuralları kontrol et:
{rules_channel}
"""

def reset_daily_data():
    """Günlük verileri sıfırla (03:00'da)"""
    global message_counter, user_last_share_number, DAILY_STATS
    
    message_counter = 0
    user_last_share_number = {}
    
    DAILY_STATS = {
        'links_shared': 0,
        'violations_emoji': 0,
        'violations_cooldown': 0,
        'date': datetime.now().date()
    }
    
    logger.info("✅ Günlük veriler sıfırlandı (03:00)")

async def send_daily_report(context: ContextTypes.DEFAULT_TYPE):
    """Günlük rapor gönder (03:00'da)"""
    
    report = f"""
📊 GÜNLÜK RAPOR (EMOJİ MODU)
━━━━━━━━━━━━━━━━━━━━

📅 Tarih: {DAILY_STATS['date'].strftime('%d.%m.%Y')}

📈 İSTATİSTİKLER:
   ✅ Toplam paylaşılan: {DAILY_STATS['links_shared']} link
   ❌ Emoji eksik: {DAILY_STATS['violations_emoji']} kişi
   ⏳ Cooldown ihlali: {DAILY_STATS['violations_cooldown']} deneme

━━━━━━━━━━━━━━━━━━━━
🔄 Sayaç sıfırlandı, yeni gün başlıyor!
⏰ Rapor zamanı: {datetime.now().strftime('%H:%M')}
"""
    
    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=report
    )
    
    logger.info("✅ Günlük rapor admin'e gönderildi")

async def schedule_daily_reset(application: Application):
    """Her gün 03:00'da reset yap"""
    
    while True:
        now = datetime.now()
        
        reset_time = now.replace(hour=3, minute=0, second=0, microsecond=0)
        
        if now >= reset_time:
            from datetime import timedelta
            reset_time = reset_time + timedelta(days=1)
        
        wait_seconds = (reset_time - now).total_seconds()
        
        logger.info(f"⏰ Bir sonraki reset: {reset_time.strftime('%d.%m.%Y 03:00')}")
        
        await asyncio.sleep(wait_seconds)
        
        logger.info("🔄 Günlük reset başlıyor...")
        
        await send_daily_report(application)
        reset_daily_data()

async def delete_old_rules(context):
    """Eski kural mesajını sil"""
    global LAST_RULES_MESSAGE_ID
    
    if LAST_RULES_MESSAGE_ID:
        try:
            await context.bot.delete_message(
                chat_id=GROUP_ID,
                message_id=LAST_RULES_MESSAGE_ID
            )
        except Exception as e:
            logger.error(f"Eski kural mesajı silinemedi: {e}")
        
        LAST_RULES_MESSAGE_ID = None

async def send_rules(context):
    """Yeni kural mesajı gönder"""
    global LAST_RULES_MESSAGE_ID
    
    try:
        rules_message = await context.bot.send_message(
            chat_id=GROUP_ID,
            message_thread_id=TOPIC_ID,
            text=RULES_TEXT.format(rules_channel=RULES_CHANNEL),
            disable_web_page_preview=True
        )
        
        LAST_RULES_MESSAGE_ID = rules_message.message_id
    except Exception as e:
        logger.error(f"Kural mesajı gönderilemedi: {e}")

async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kullanıcı link paylaştığında"""
    
    global message_counter
    
    if update.message.chat.id != GROUP_ID:
        return
    
    message_thread_id = update.message.message_thread_id
    if message_thread_id != TOPIC_ID:
        return
    
    text = update.message.text or ""
    urls = re.findall(r'https?://(?:twitter|x)\.com/\S+/status/\d+', text)
    
    if not urls:
        return
    
    user = update.message.from_user
    username = user.username or user.first_name
    link = urls[0]
    
    logger.info(f"📝 Link paylaşımı: @{username}")
    
    try:
        await update.message.delete()
    except Exception as e:
        logger.error(f"Mesaj silinemedi: {e}")
    
    # KONTROL 1: COOLDOWN
    if user.id in user_last_share_number:
        last_share_num = user_last_share_number[user.id]
        links_since = message_counter - last_share_num
        
        if links_since < 20:
            remaining = 20 - links_since
            
            DAILY_STATS['violations_cooldown'] += 1
            
            try:
                await context.bot.send_message(
                    chat_id=user.id,
                    text=f"⏳ Cooldown süresi!\n\n"
                         f"Son paylaşımından bu yana {links_since} link geçti.\n"
                         f"Daha {remaining} link beklemen gerekiyor.\n\n"
                         f"📊 Şu anki sayaç: #{message_counter}\n"
                         f"🔢 Senin son paylaşımın: #{last_share_num}\n"
                         f"✅ #{last_share_num + 20}'dan sonra paylaşabilirsin.\n\n"
                         f"📚 Kurallar: {RULES_CHANNEL}"
                )
            except:
                pass
            
            try:
                await context.bot.send_message(
                    chat_id=ADMIN_ID,
                    text=f"⏳ COOLDOWN İHLALİ\n\n"
                         f"👤 @{username} (ID: {user.id})\n"
                         f"📊 {links_since}/20 link geçmiş\n"
                         f"⚠️ {remaining} link daha beklemeli\n\n"
                         f"🔗 Link: {link}"
                )
            except:
                pass
            
            logger.info(f"⏳ Cooldown: @{username} - {links_since}/20")
            return
    
    # KONTROL 2: EMOJİ
    engaged_count = 0
    required_count = min(len(LAST_MESSAGES), 20)
    
    for msg_data in LAST_MESSAGES[-20:]:
        msg_id = msg_data['message_id']
        
        try:
            reactions = await context.bot.get_message_reactions(
                chat_id=GROUP_ID,
                message_id=msg_id
            )
            
            user_reacted = False
            if reactions:
                for reaction in reactions:
                    if reaction.user.id == user.id and reaction.emoji == "👍":
                        user_reacted = True
                        break
            
            if user_reacted:
                engaged_count += 1
                
        except Exception as e:
            logger.error(f"Reaction kontrol hatası: {e}")
            continue
    
    if engaged_count >= required_count:
        # ✅ ONAYLANDI
        
        message_counter += 1
        DAILY_STATS['links_shared'] += 1
        
        await delete_old_rules(context)
        
        try:
            sent_message = await context.bot.send_message(
                chat_id=GROUP_ID,
                message_thread_id=TOPIC_ID,
                text=f"{message_counter}. 🔗 Link by @{username}\n\n{link}",
                disable_web_page_preview=True
            )
            
            link_data = {
                'message_id': sent_message.message_id,
                'user_id': user.id,
                'username': username,
                'link': link,
                'number': message_counter,
                'timestamp': datetime.now()
            }
            
            LAST_MESSAGES.append(link_data)
            user_last_share_number[user.id] = message_counter
            
            if len(LAST_MESSAGES) > 30:
                LAST_MESSAGES.pop(0)
            
            logger.info(f"✅ Link paylaşıldı: #{message_counter} - @{username}")
            
        except Exception as e:
            logger.error(f"❌ Link paylaşılamadı: {e}")
        
        await send_rules(context)
            
    else:
        # ❌ EKSİK EMOJİ
        missing_count = required_count - engaged_count
        
        DAILY_STATS['violations_emoji'] += 1
        
        try:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"❌ EMOJİ EKSİK\n\n"
                     f"👤 @{username} (ID: {user.id})\n"
                     f"📊 Durum: {engaged_count}/{required_count}\n"
                     f"❌ Eksik: {missing_count} mesaj\n\n"
                     f"🔗 Link: {link}"
            )
        except:
            pass
        
        try:
            await context.bot.send_message(
                chat_id=user.id,
                text=f"❌ Link paylaşılamadı!\n\n"
                     f"📊 Durum: {engaged_count}/{required_count}\n"
                     f"⚠️ Eksik {missing_count} mesaja 👍 emoji at.\n\n"
                     f"📚 Kurallar: {RULES_CHANNEL}"
            )
        except:
            pass
        
        logger.warning(f"❌ Emoji eksik: @{username} - {engaged_count}/{required_count}")

async def post_init(application: Application):
    """Bot başladıktan sonra çalışacak"""
    asyncio.create_task(schedule_daily_reset(application))
    logger.info(f"✅ Günlük reset scheduler başlatıldı")

def main():
    """Bot'u başlat"""
    
    app = Application.builder().token(TOKEN).post_init(post_init).build()
    
    app.add_handler(MessageHandler(
        filters.TEXT & filters.Regex(r'https?://(?:twitter|x)\.com'),
        handle_link
    ))
    
    logger.info(f"")
    logger.info(f"🤖 EMOJİ MODU BOT BAŞLATILDI")
    logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    logger.info(f"📍 Group ID: {GROUP_ID}")
    logger.info(f"📍 Topic ID: {TOPIC_ID}")
    logger.info(f"📊 Günlük sayaç: #{message_counter}")
    logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    logger.info(f"")
    
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()