from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
import re
import logging
from datetime import datetime, time as dt_time
import asyncio

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

TOKEN = "7958058721:AAEXx4Zw3RYj_7Bnr_eMfUWcsjlxYbsfRBk"
ADMIN_ID = 1004037545
GROUP_ID = -1002158416026

# İKİ TOPIC
EMOJI_TOPIC_ID = 33348
SAATLI_TOPIC_ID = 16848

EMOJI_RULES = "https://t.me/zaxengage/12/33361"
SAATLI_RULES = "https://t.me/zaxengage/12/26852"

# EMOJİ MODU STATE
emoji_last_messages = []
emoji_last_rules_id = None
emoji_counter = 0
emoji_user_last_share = {}
emoji_stats = {
    'links_shared': 0,
    'violations_emoji': 0,
    'violations_cooldown': 0,
    'date': datetime.now().date()
}

# SAATLİ MOD STATE
SESSIONS = [
    {'name': 'Sabah', 'start': dt_time(10, 0), 'end': dt_time(12, 0)},
    {'name': 'Öğle', 'start': dt_time(14, 0), 'end': dt_time(15, 0)},
    {'name': 'Akşam', 'start': dt_time(21, 0), 'end': dt_time(22, 0)}
]

saatli_session_data = {
    'Sabah': {'links': [], 'users': set(), 'date': None},
    'Öğle': {'links': [], 'users': set(), 'date': None},
    'Akşam': {'links': [], 'users': set(), 'date': None}
}

saatli_all_time_links = set()
saatli_stats = {
    'links_shared': 0,
    'rejected_duplicate': 0,
    'rejected_session_limit': 0,
    'rejected_closed': 0,
    'date': datetime.now().date()
}

EMOJI_RULES_TEXT = """
📚 Check rules / Kuralları kontrol et:
{rules_channel}
"""

SAATLI_RULES_TEXT = """
📚 Check rules / Kuralları kontrol et:
{rules_channel}
"""

# EMOJİ MOD FONKSİYONLARI
def reset_emoji_daily():
    global emoji_counter, emoji_user_last_share, emoji_stats
    emoji_counter = 0
    emoji_user_last_share = {}
    emoji_stats = {
        'links_shared': 0,
        'violations_emoji': 0,
        'violations_cooldown': 0,
        'date': datetime.now().date()
    }
    logger.info("Emoji modu günlük veriler sıfırlandı")

async def emoji_daily_report(context):
    report = f"""
📊 GÜNLÜK RAPOR (EMOJİ MODU)
━━━━━━━━━━━━━━━━━━━━

📅 Tarih: {emoji_stats['date'].strftime('%d.%m.%Y')}

📈 İSTATİSTİKLER:
   ✅ Toplam paylaşılan: {emoji_stats['links_shared']} link
   ❌ Emoji eksik: {emoji_stats['violations_emoji']} kişi
   ⏳ Cooldown ihlali: {emoji_stats['violations_cooldown']} deneme

━━━━━━━━━━━━━━━━━━━━
⏰ Rapor zamanı: {datetime.now().strftime('%H:%M')}
"""
    await context.bot.send_message(chat_id=ADMIN_ID, text=report)
    logger.info("Emoji modu günlük rapor gönderildi")

async def emoji_schedule_reset(application):
    while True:
        now = datetime.now()
        reset_time = now.replace(hour=3, minute=0, second=0, microsecond=0)
        if now >= reset_time:
            from datetime import timedelta
            reset_time = reset_time + timedelta(days=1)
        
        wait_seconds = (reset_time - now).total_seconds()
        logger.info(f"Emoji mod reset: {reset_time.strftime('%d.%m.%Y 03:00')}")
        
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
        logger.error(f"Emoji kurallar gönderilemedi: {e}")

# SAATLİ MOD FONKSİYONLARI
def get_current_session():
    now = datetime.now().time()
    for session in SESSIONS:
        if session['start'] <= now <= session['end']:
            return session['name']
    return None

def reset_saatli_session(session_name):
    saatli_session_data[session_name] = {
        'links': [],
        'users': set(),
        'date': datetime.now().date()
    }
    logger.info(f"Saatli mod seans sıfırlandı: {session_name}")

def reset_saatli_stats():
    global saatli_stats
    saatli_stats = {
        'links_shared': 0,
        'rejected_duplicate': 0,
        'rejected_session_limit': 0,
        'rejected_closed': 0,
        'date': datetime.now().date()
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
        logger.error(f"Saatli özet hatası: {e}")
    
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
   ❌ Duplicate: {saatli_stats['rejected_duplicate']}
   ❌ Seans limiti: {saatli_stats['rejected_session_limit']}
   ⏰ Kapalı saat: {saatli_stats['rejected_closed']}

━━━━━━━━━━━━━━━━━━━━
⏰ {datetime.now().strftime('%H:%M')}
"""
    await context.bot.send_message(chat_id=ADMIN_ID, text=report)
    logger.info("Saatli mod günlük rapor gönderildi")
    reset_saatli_stats()

async def saatli_schedule_sessions(application):
    while True:
        now = datetime.now()
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
            from datetime import timedelta
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
    
    if not update.message:
        return
    
    if update.message.chat.id != GROUP_ID:
        return
    
    topic_id = update.message.message_thread_id
    
    if topic_id not in [EMOJI_TOPIC_ID, SAATLI_TOPIC_ID]:
        return
    
    text = update.message.text or ""
    urls = re.findall(r'https?://(?:twitter|x)\.com/\S+/status/\d+', text)
    
    if not urls:
        return
    
    user = update.message.from_user
    username = user.username or user.first_name
    link = urls[0]
    
    try:
        await update.message.delete()
    except Exception as e:
        logger.error(f"Mesaj silinemedi: {e}")
    
    # EMOJİ MODU (Topic 33348)
    if topic_id == EMOJI_TOPIC_ID:
        logger.info(f"[EMOJI] Link: @{username}")
        
        # Cooldown kontrolü
        if user.id in emoji_user_last_share:
            last_num = emoji_user_last_share[user.id]
            since = emoji_counter - last_num
            
            if since < 20:
                emoji_stats['violations_cooldown'] += 1
                remaining = 20 - since
                
                try:
                    await context.bot.send_message(
                        chat_id=user.id,
                        text=f"⏳ Cooldown!\n\n{since}/20 link geçti.\n{remaining} link daha bekle.\n\n"
                             f"Şu an: #{emoji_counter}\nSenin: #{last_num}\n✅ #{last_num + 20}'dan sonra.\n\n{EMOJI_RULES}"
                    )
                except:
                    pass
                
                try:
                    await context.bot.send_message(
                        chat_id=ADMIN_ID,
                        text=f"⏳ [EMOJI] COOLDOWN\n\n@{username}\n{since}/20\n{remaining} kaldı\n\n{link}"
                    )
                except:
                    pass
                
                logger.info(f"[EMOJI] Cooldown: @{username} - {since}/20")
                return
        
        # Emoji kontrolü
        engaged = 0
        required = min(len(emoji_last_messages), 20)
        
        for msg_data in emoji_last_messages[-20:]:
            try:
                reactions = await context.bot.get_message_reactions(GROUP_ID, msg_data['message_id'])
                if reactions:
                    for r in reactions:
                        if r.user.id == user.id and r.emoji == "👍":
                            engaged += 1
                            break
            except:
                continue
        
        if engaged >= required:
            # Onaylandı
            emoji_counter += 1
            emoji_stats['links_shared'] += 1
            
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
                    'timestamp': datetime.now()
                })
                
                emoji_user_last_share[user.id] = emoji_counter
                
                if len(emoji_last_messages) > 30:
                    emoji_last_messages.pop(0)
                
                logger.info(f"[EMOJI] Paylaşıldı: #{emoji_counter} - @{username}")
            except Exception as e:
                logger.error(f"[EMOJI] Hata: {e}")
            
            await emoji_send_rules(context)
        else:
            # Emoji eksik
            missing = required - engaged
            emoji_stats['violations_emoji'] += 1
            
            try:
                await context.bot.send_message(
                    chat_id=ADMIN_ID,
                    text=f"❌ [EMOJI] EKSİK\n\n@{username}\n{engaged}/{required}\nEksik: {missing}\n\n{link}"
                )
            except:
                pass
            
            try:
                await context.bot.send_message(
                    chat_id=user.id,
                    text=f"❌ Link paylaşılamadı!\n\n{engaged}/{required}\nEksik {missing} emoji.\n\n{EMOJI_RULES}"
                )
            except:
                pass
            
            logger.warning(f"[EMOJI] Eksik: @{username} - {engaged}/{required}")
    
    # SAATLİ MOD (Topic 16848)
    elif topic_id == SAATLI_TOPIC_ID:
        logger.info(f"[SAATLİ] Link: @{username}")
        
        current_session = get_current_session()
        
        # Kanal açık mı?
        if not current_session:
            saatli_stats['rejected_closed'] += 1
            
            try:
                now = datetime.now().time()
                next_s = None
                for s in SESSIONS:
                    if s['start'] > now:
                        next_s = s
                        break
                if not next_s:
                    next_s = SESSIONS[0]
                
                await context.bot.send_message(
                    chat_id=user.id,
                    text=f"⏰ Kapalı!\n\n🌅 Sabah: 10-12\n☀️ Öğle: 14-15\n🌙 Akşam: 21-22\n\n"
                         f"Sonraki: {next_s['name']} ({next_s['start'].strftime('%H:%M')})"
                )
            except:
                pass
            
            logger.info(f"[SAATLİ] Kapalı: @{username}")
            return
        
        # Duplicate kontrolü
        if link in saatli_all_time_links:
            saatli_stats['rejected_duplicate'] += 1
            
            try:
                await context.bot.send_message(
                    chat_id=user.id,
                    text=f"❌ Bu link daha önce paylaşıldı!\n\n{SAATLI_RULES}"
                )
            except:
                pass
            
            logger.info(f"[SAATLİ] Duplicate: @{username}")
            return
        
        # Seans limiti
        if user.id in saatli_session_data[current_session]['users']:
            saatli_stats['rejected_session_limit'] += 1
            
            try:
                await context.bot.send_message(
                    chat_id=user.id,
                    text=f"❌ Bu seansta zaten paylaştın!\n\n{SAATLI_RULES}"
                )
            except:
                pass
            
            logger.info(f"[SAATLİ] Seans dup: @{username}")
            return
        
        # Onaylandı
        saatli_stats['links_shared'] += 1
        
        try:
            sent = await context.bot.send_message(
                chat_id=GROUP_ID,
                message_thread_id=SAATLI_TOPIC_ID,
                text=f"🔗 Link by @{username}\n\n{link}",
                disable_web_page_preview=True
            )
            
            saatli_session_data[current_session]['links'].append({
                'message_id': sent.message_id,
                'user_id': user.id,
                'username': username,
                'link': link,
                'timestamp': datetime.now()
            })
            
            saatli_session_data[current_session]['users'].add(user.id)
            saatli_all_time_links.add(link)
            
            logger.info(f"[SAATLİ] Paylaşıldı: @{username} - {current_session}")
        except Exception as e:
            logger.error(f"[SAATLİ] Hata: {e}")

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
    logger.info(f"Emoji Topic: {EMOJI_TOPIC_ID}")
    logger.info(f"Saatli Topic: {SAATLI_TOPIC_ID}")
    logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    logger.info("")
    
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
