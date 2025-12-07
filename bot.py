from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
import re
import logging
from datetime import datetime, time as dt_time, timedelta, timezone
import asyncio

# TÜRKİYE TIMEZONE (UTC+3)
TURKEY_TZ = timezone(timedelta(hours=3))

def now_turkey():
    """Türkiye saati döndür"""
    return datetime.now(TURKEY_TZ)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

TOKEN = "7958058721:AAEXx4Zw3RYj_7Bnr_eMfUWcsjlxYbsfRBk"
ADMIN_ID = 1004037545
GROUP_ID = -1002158416026

EMOJI_TOPIC_ID = 33348
SAATLI_TOPIC_ID = 16848

EMOJI_RULES = "https://t.me/zaxengage/12/33361"
SAATLI_RULES = "https://t.me/zaxengage/12/26852"

# EMOJİ MODU STATE
emoji_last_messages = []
emoji_last_rules_id = None
emoji_counter = 0
emoji_user_last_share = {}
emoji_user_daily_count = {}
emoji_stats = {
    'links_shared': 0,
    'violations_cooldown': 0,
    'violations_daily_limit': 0,
    'date': now_turkey().date()
}

# SAATLİ MOD STATE - YENİ SEANS SAATLERİ
SESSIONS = [
    {'name': 'Sabah', 'start': dt_time(9, 50), 'end': dt_time(12, 10)},
    {'name': 'Öğle', 'start': dt_time(13, 50), 'end': dt_time(15, 10)},
    {'name': 'Akşam', 'start': dt_time(20, 50), 'end': dt_time(22, 10)}
]

saatli_session_data = {
    'Sabah': {'links': [], 'users': set(), 'date': None},
    'Öğle': {'links': [], 'users': set(), 'date': None},
    'Akşam': {'links': [], 'users': set(), 'date': None}
}

saatli_stats = {
    'links_shared': 0,
    'rejected_closed': 0,
    'date': now_turkey().date()
}

EMOJI_RULES_TEXT = """
📚 Check rules / Kuralları kontrol et:
{rules_channel}
"""

SAATLI_RULES_TEXT = """
📚 Check rules / Kuralları kontrol et:
{rules_channel}
"""

# YÖNETİCİ KONTROLÜ
async def is_admin(context, user_id):
    """Kullanıcı yönetici mi?"""
    try:
        member = await context.bot.get_chat_member(GROUP_ID, user_id)
        return member.status in ['creator', 'administrator']
    except:
        return False

# EMOJİ MOD FONKSİYONLARI
def reset_emoji_daily():
    global emoji_counter, emoji_user_last_share, emoji_user_daily_count, emoji_stats
    emoji_counter = 0
    emoji_user_last_share = {}
    emoji_user_daily_count = {}
    emoji_stats = {
        'links_shared': 0,
        'violations_cooldown': 0,
        'violations_daily_limit': 0,
        'date': now_turkey().date()
    }
    logger.info("Günlük veriler sıfırlandı (Emoji mod)")

async def emoji_daily_report(context):
    report = f"""
📊 GÜNLÜK RAPOR
━━━━━━━━━━━━━━━━━━━━

📅 Tarih: {emoji_stats['date'].strftime('%d.%m.%Y')}

📈 İSTATİSTİKLER:
   ✅ Toplam paylaşılan: {emoji_stats['links_shared']} link
   ⏳ Cooldown ihlali: {emoji_stats['violations_cooldown']} deneme
   📛 Günlük limit aşımı: {emoji_stats['violations_daily_limit']} deneme

━━━━━━━━━━━━━━━━━━━━
⏰ {now_turkey().strftime('%H:%M')}
"""
    await context.bot.send_message(chat_id=ADMIN_ID, text=report)
    logger.info("Günlük rapor gönderildi")

async def emoji_schedule_reset(application):
    while True:
        now = now_turkey()
        reset_time = now.replace(hour=3, minute=0, second=0, microsecond=0)
        if now >= reset_time:
            reset_time = reset_time + timedelta(days=1)
        
        wait_seconds = (reset_time - now).total_seconds()
        logger.info(f"Bir sonraki reset: {reset_time.strftime('%d.%m.%Y 03:00')}")
        
        await asyncio.sleep(wait_seconds)
        await emoji_daily_report(application)
        reset_emoji_daily()

async def emoji_delete_old_rules(context):
    global emoji_last_rules_id
    if emoji_last_rules_id:
        try:
            await context.bot.delete_message(GROUP_ID, emoji_last_rules_id)
        except:
            pass
        emoji_last_rules_id = None

async def emoji_send_rules(context):
    global emoji_last_rules_id
    try:
        msg = await context.bot.send_message(
            chat_id=GROUP_ID,
            message_thread_id=EMOJI_TOPIC_ID,
            text=EMOJI_RULES_TEXT.format(rules_channel=EMOJI_RULES),
            disable_web_page_preview=True
        )
        emoji_last_rules_id = msg.message_id
    except Exception as e:
        logger.error(f"Kurallar gönderilemedi: {e}")

# SAATLİ MOD FONKSİYONLARI
def get_current_session():
    now = now_turkey().time()
    for session in SESSIONS:
        if session['start'] <= now <= session['end']:
            return session['name']
    return None

def reset_saatli_session(session_name):
    saatli_session_data[session_name] = {
        'links': [],
        'users': set(),
        'date': now_turkey().date()
    }
    logger.info(f"Seans sıfırlandı: {session_name}")

def reset_saatli_stats():
    global saatli_stats
    saatli_stats = {
        'links_shared': 0,
        'rejected_closed': 0,
        'date': now_turkey().date()
    }

async def saatli_session_summary(context, session_name):
    session = saatli_session_data[session_name]
    
    if not session['links']:
        logger.info(f"{session_name} seansında link yok")
        reset_saatli_session(session_name)
        return
    
    summary = ""
    for link_data in session['links']:
        summary += f"{link_data['link']}\n"
    
    try:
        await context.bot.send_message(
            chat_id=GROUP_ID,
            message_thread_id=SAATLI_TOPIC_ID,
            text=summary,
            disable_web_page_preview=True
        )
        logger.info(f"{session_name} özeti gönderildi: {len(session['links'])} link")
    except Exception as e:
        logger.error(f"Özet hatası: {e}")
    
    try:
        await context.bot.send_message(
            chat_id=GROUP_ID,
            message_thread_id=SAATLI_TOPIC_ID,
            text=SAATLI_RULES_TEXT.format(rules_channel=SAATLI_RULES),
            disable_web_page_preview=True
        )
    except:
        pass
    
    reset_saatli_session(session_name)

async def saatli_daily_report(context):
    report = f"""
📊 GÜNLÜK RAPOR (SAATLİ MOD)
━━━━━━━━━━━━━━━━━━━━

📅 Tarih: {saatli_stats['date'].strftime('%d.%m.%Y')}

📈 İSTATİSTİKLER:
   ✅ Paylaşılan: {saatli_stats['links_shared']}
   ⏰ Kapalı saat: {saatli_stats['rejected_closed']}

━━━━━━━━━━━━━━━━━━━━
⏰ {now_turkey().strftime('%H:%M')}
"""
    await context.bot.send_message(chat_id=ADMIN_ID, text=report)
    logger.info("Saatli mod günlük rapor gönderildi")
    reset_saatli_stats()

async def saatli_schedule_sessions(application):
    while True:
        now = now_turkey()
        next_event = None
        next_event_type = None
        
        for session in SESSIONS:
            end_datetime = now.replace(
                hour=session['end'].hour,
                minute=session['end'].minute,
                second=0,
                microsecond=0
            )
            
            if now < end_datetime:
                if next_event is None or end_datetime < next_event:
                    next_event = end_datetime
                    next_event_type = ('end', session['name'])
        
        if next_event is None:
            tomorrow = now + timedelta(days=1)
            next_event = tomorrow.replace(
                hour=SESSIONS[0]['end'].hour,
                minute=SESSIONS[0]['end'].minute,
                second=0,
                microsecond=0
            )
            next_event_type = ('end', SESSIONS[0]['name'])
        
        wait_seconds = (next_event - now).total_seconds()
        logger.info(f"Saatli mod sonraki: {next_event_type[1]} - {next_event.strftime('%d.%m %H:%M')}")
        
        await asyncio.sleep(wait_seconds)
        
        event_type, session_name = next_event_type
        
        if event_type == 'end':
            logger.info(f"{session_name} bitti, özet gönderiliyor...")
            await saatli_session_summary(application, session_name)
        
        if session_name == 'Akşam':
            await saatli_daily_report(application)

# ANA HANDLER
async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global emoji_counter
    
    # SADECE MESAJLARI İŞLE
    if not update.message:
        return
    
    # SADECE TEXT MESAJLARA BAK (SİSTEM MESAJLARINI ATLA)
    if not update.message.text:
        return
    
    if update.message.chat.id != GROUP_ID:
        return
    
    topic_id = update.message.message_thread_id
    
    if topic_id not in [EMOJI_TOPIC_ID, SAATLI_TOPIC_ID]:
        return
    
    text = update.message.text
    user = update.message.from_user
    username = user.username or user.first_name
    
    # Twitter/X link var mı kontrol et
    urls = re.findall(r'https?://(?:twitter|x)\.com/\S+/status/\d+', text)
    
    # EMOJİ MODU (Topic 33348)
    if topic_id == EMOJI_TOPIC_ID:
        # LİNK YOKSA HİÇBİR ŞEY YAPMA (mesajı silme bile)
        if not urls:
            logger.info(f"Link yok, mesaj bırakıldı: @{username}")
            return
        
        link = urls[0]
        logger.info(f"Link: @{username}")
        
        # KULLANICI MESAJINI SİL (link varsa)
        try:
            await update.message.delete()
        except Exception as e:
            logger.error(f"Mesaj silinemedi: {e}")
        
        # KONTROL 1: GÜNLÜK LİMİT (4 paylaşım/gün)
        daily_count = emoji_user_daily_count.get(user.id, 0)
        
        if daily_count >= 4:
            emoji_stats['violations_daily_limit'] += 1
            
            try:
                await context.bot.send_message(
                    chat_id=user.id,
                    text=f"❌ Günlük limit aşıldı!\n\n"
                         f"Bugün {daily_count} kere paylaştın.\n"
                         f"Günde maksimum 4 paylaşım yapabilirsin.\n\n"
                         f"Yarın tekrar dene.\n\n"
                         f"📚 Kurallar: {EMOJI_RULES}"
                )
            except:
                pass
            
            try:
                await context.bot.send_message(
                    chat_id=ADMIN_ID,
                    text=f"📛 GÜNLÜK LİMİT\n\n"
                         f"@{username} (ID: {user.id})\n"
                         f"Bugün: {daily_count}/4\n\n"
                         f"🔗 {link}"
                )
            except:
                pass
            
            logger.info(f"Günlük limit: @{username} - {daily_count}/4")
            return
        
        # KONTROL 2: COOLDOWN (15 link)
        if user.id in emoji_user_last_share:
            last_num = emoji_user_last_share[user.id]
            since = emoji_counter - last_num
            
            if since < 15:
                emoji_stats['violations_cooldown'] += 1
                remaining = 15 - since
                
                try:
                    await context.bot.send_message(
                        chat_id=user.id,
                        text=f"⏳ Cooldown!\n\n"
                             f"Son paylaşımından bu yana {since} link geçti.\n"
                             f"Daha {remaining} link beklemen gerekiyor.\n\n"
                             f"📊 Şu anki sayaç: #{emoji_counter}\n"
                             f"🔢 Senin son paylaşımın: #{last_num}\n"
                             f"✅ #{last_num + 15}'den sonra paylaşabilirsin.\n\n"
                             f"📚 Kurallar: {EMOJI_RULES}"
                    )
                except:
                    pass
                
                try:
                    await context.bot.send_message(
                        chat_id=ADMIN_ID,
                        text=f"⏳ COOLDOWN\n\n"
                             f"@{username} (ID: {user.id})\n"
                             f"📊 {since}/15 link geçmiş\n"
                             f"⚠️ {remaining} link daha beklemeli\n\n"
                             f"🔗 {link}"
                    )
                except:
                    pass
                
                logger.info(f"Cooldown: @{username} - {since}/15")
                return
        
        # ✅ TÜM KONTROLLER GEÇTİ
        emoji_counter += 1
        emoji_stats['links_shared'] += 1
        
        # Günlük sayacı artır
        emoji_user_daily_count[user.id] = emoji_user_daily_count.get(user.id, 0) + 1
        
        await emoji_delete_old_rules(context)
        
        try:
            sent = await context.bot.send_message(
                chat_id=GROUP_ID,
                message_thread_id=EMOJI_TOPIC_ID,
                text=f"{emoji_counter}. 🔗 Link by @{username}\n\n{link}",
                disable_web_page_preview=True
            )
            
            emoji_last_messages.append({
                'message_id': sent.message_id,
                'user_id': user.id,
                'username': username,
                'link': link,
                'number': emoji_counter,
                'timestamp': now_turkey()
            })
            
            emoji_user_last_share[user.id] = emoji_counter
            
            if len(emoji_last_messages) > 30:
                emoji_last_messages.pop(0)
            
            logger.info(f"Paylaşıldı: #{emoji_counter} - @{username} (Günlük: {emoji_user_daily_count[user.id]}/4)")
        except Exception as e:
            logger.error(f"Hata: {e}")
        
        await emoji_send_rules(context)
    
    # SAATLİ MOD (Topic 16848)
    elif topic_id == SAATLI_TOPIC_ID:
        # LİNK YOKSA HİÇBİR ŞEY YAPMA
        if not urls:
            return
        
        link = urls[0]
        logger.info(f"[SAATLİ] Link: @{username}")
        
        # YÖNETİCİ KONTROLÜ
        user_is_admin = await is_admin(context, user.id)
        if user_is_admin:
            logger.info(f"[SAATLİ] Yönetici mesajı tespit edildi: @{username}")
        
        current_session = get_current_session()
        
        # Kanal açık mı?
        if not current_session:
            saatli_stats['rejected_closed'] += 1
            
            # SADECE YÖNETİCİ DEĞİLSE SİL
            if not user_is_admin:
                try:
                    await update.message.delete()
                except:
                    pass
            
            try:
                now = now_turkey().time()
                next_s = None
                for s in SESSIONS:
                    if s['start'] > now:
                        next_s = s
                        break
                if not next_s:
                    next_s = SESSIONS[0]
                
                await context.bot.send_message(
                    chat_id=user.id,
                    text=f"⏰ Kanal şu an kapalı!\n\n"
                         f"📅 SEANSLAR:\n"
                         f"🌅 Sabah: 09:50-12:10\n"
                         f"☀️ Öğle: 13:50-15:10\n"
                         f"🌙 Akşam: 20:50-22:10\n\n"
                         f"⏰ Bir sonraki seans: {next_s['name']} ({next_s['start'].strftime('%H:%M')})"
                )
            except:
                pass
            
            logger.info(f"[SAATLİ] Kapalı: @{username}")
            return
        
        # ✅ ONAYLANDI - KAYIT EDİLDİ (HİÇBİR KONTROL YOK)
        saatli_stats['links_shared'] += 1
        
        # Mesaj ID'sini kaydet
        saatli_session_data[current_session]['links'].append({
            'message_id': update.message.message_id,
            'user_id': user.id,
            'username': username,
            'link': link,
            'timestamp': now_turkey(),
            'is_admin': user_is_admin
        })
        
        saatli_session_data[current_session]['users'].add(user.id)
        
        admin_tag = " (MOD)" if user_is_admin else ""
        logger.info(f"[SAATLİ] Kayıt edildi: @{username}{admin_tag} - {current_session}")

async def post_init(application):
    asyncio.create_task(emoji_schedule_reset(application))
    asyncio.create_task(saatli_schedule_sessions(application))
    logger.info("Her iki mod başlatıldı")

def main():
    app = Application.builder().token(TOKEN).post_init(post_init).build()
    
    app.add_handler(MessageHandler(
        filters.TEXT & filters.Regex(r'https?://(?:twitter|x)\.com'),
        handle_link
    ))
    
    logger.info("")
    logger.info("BİRLEŞİK BOT BAŞLATILDI")
    logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    logger.info(f"Group ID: {GROUP_ID}")
    logger.info(f"Emoji Topic: {EMOJI_TOPIC_ID} (15 link cooldown, 4/gün limit)")
    logger.info(f"Saatli Topic: {SAATLI_TOPIC_ID} (DUPLICATE VE LIMIT KONTROLÜ YOK)")
    logger.info(f"Timezone: UTC+3 (Türkiye)")
    logger.info(f"Seans saatleri: 09:50-12:10, 13:50-15:10, 20:50-22:10")
    logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    logger.info("")
    
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
