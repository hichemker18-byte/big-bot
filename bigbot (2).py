import telebot
from telebot import types, apihelper
import sqlite3
try:
    import psycopg2
    from psycopg2 import IntegrityError as PgIntegrityError
    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False
    PgIntegrityError = Exception
import re
import logging
import os
import time
import html
import threading
import warnings
from datetime import datetime, timedelta
from typing import List, Tuple
try:
    from flask import Flask
    app = Flask(__name__)

    @app.route('/')
    def home():
        return "Bot is active and running 24/7!", 200
    HAS_FLASK = True
except ImportError:
    HAS_FLASK = False
    app = None

# كتم تحذيرات بايثون الداخلية لمكتبة تيليجرام
warnings.filterwarnings("ignore")

# فلتر مخصص لتنظيف السجلات من تحذيرات التفاعلات الداخلية لمكتبة تيليجرام
class CleanLogFilter(logging.Filter):
    def filter(self, record):
        msg = record.getMessage()
        if "ReactionType" in msg:
            return False
        return True

clean_filter = CleanLogFilter()

# تهيئة التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# تطبيق الفلتر على جميع السجلات وضبط المستويات
logging.getLogger('TeleBot').setLevel(logging.ERROR)
telebot.logger.setLevel(logging.ERROR)
logging.getLogger('urllib3').setLevel(logging.WARNING)
logging.getLogger('requests').setLevel(logging.WARNING)

for log_name in ('TeleBot', 'urllib3', 'requests', ''):
    l = logging.getLogger(log_name)
    l.addFilter(clean_filter)
    for h in l.handlers:
        h.addFilter(clean_filter)

for h in logging.root.handlers:
    h.addFilter(clean_filter)

# ضبط مهلات الاتصال وإعادة المحاولة التلقائية عند تقلبات الإنترنت
apihelper.CONNECT_TIMEOUT = 20
apihelper.READ_TIMEOUT = 60
apihelper.RETRY_ON_ERROR = True

# استبدل بالتوكن الخاص بك
TOKEN = '8035660396:AAHlTw8dS5aIVwnGm5nxpnq3n0mzI_xrOY4'
ADMIN_ID = 5945226339  # غيره إلى معرفك الحقيقي

# تهيئة البوت
bot = telebot.TeleBot(TOKEN)
# رابط اتصال Supabase PostgreSQL
DATABASE_URL = os.environ.get('DATABASE_URL', '')
BOT_USERNAME = None

DAYS_AR = {
    0: "الإثنين",
    1: "الثلاثاء",
    2: "الأربعاء",
    3: "الخميس",
    4: "الجمعة",
    5: "السبت",
    6: "الأحد",
}

LISTING_STATUS_AR = {
    "draft": "مسودة — ما كملتش التأكيد",
    "pending": "قيد المراجعة ⏳",
    "approved": "مقبول ✅",
    "rejected": "مرفوض ❌",
    "cancelled": "ملغى",
}

USER_RULES_TEXT = (
    "<blockquote>\n"
    "📜 <b>الشروط والقوانين الرسمية لدعم ونشر القنوات</b>\n"
    "━━━━━━━━━━━━━━━━━━\n"
    "⚠️ <b>يرجى قراءة القوانين بعناية، الانضمام للمجلد يعني موافقتك التامة عليها:</b>\n\n"
    "🚫 <b>1. منع قنوات التسريبات منعاً باتاً:</b>\n"
    "• يُمنع نشر أي محتوى مسرب، دورات مدفوعة مقرصنة، أو اختبارات مسربة.\n"
    "• <b>أي قناة تخالف هذا البند سيتم حظرها وطردها فوراً ونهائياً من المجلد وبدون سابق إنذار.</b>\n\n"
    "🔒 <b>2. حصرية الانضمام للمجلد (منع ازدواجية الدعم):</b>\n"
    "• المجلد يقبل انضمام قناتك لدينا وفقط؛ يُمنع المشاركة في مجلدات دعم أخرى بالتزامن أثناء فترة دعمنا تجنباً لإزعاج الطلبة.\n"
    "• في حال رصد مشاركة قناتك في مجلد آخر متزامن، <b>ستتلقى 3 إنذارات رسمية</b>، وإذا لم يتم تصحيح الخطأ سيتم <b>حذف قناتك واستبعادها نهائياً من المجلد</b>.\n\n"
    "👥 <b>3. شرط التفاعل الحقيقي (منع المشتركين الوهميين):</b>\n"
    "• يجب أن تكون القناة ذات تفاعل ومشاهدات حقيقية تتناسب مع عدد مشتركيها.\n"
    "• يُستبعد تماماً أي حساب أو قناة تعتمد على المشتركين الوهميين أو الرشق لضمان نمو حقيقي وعادل لجميع القنوات.\n\n"
    "🔄 <b>4. إلزامية الإبلاغ عند تغيير معرف/رابط القناة:</b>\n"
    "• في حال قمت بتغيير يوزر القناة (@) أو رابطها، <b>يجب مراسلة الإدارة والإبلاغ فوراً</b> لتحديث الرابط في المنشور الموحد وضمان عدم تعطل وصول الطلبة لقناتك.\n\n"
    "🛡️ <b>5. منع السبام والتكرار العشوائي:</b>\n"
    "• يُمنع إغراق البوت بالطلبات المتكررة أو إرسال معرفات وهمية.\n"
    "• أي محاولة سبام ستؤدي إلى تقييد وحظر حسابك فوراً من استخدام البوت.\n\n"
    "📢 <b>6. معايير القناة وجودة المحتوى:</b>\n"
    "• يجب أن تكون القناة عامة (@) ومحتواها تعليمي هادف ومفيد لطلبة البكالوريا وخالياً من التضليل.\n\n"
    "🤖 <b>7. صلاحية البوت الإلزامية:</b>\n"
    "• يجب إضافة البوت كمشرف في قناتك مع تفعيل <b>صلاحية النشر (Post Messages)</b> ليتمكن من نشر وإدارة المنشور الموحد في موعده.\n\n"
    "📌 <b>8. الالتزام بعدم الحذف المبكر:</b>\n"
    "• يُمنع حذف منشور المجلد قبل انتهاء الوقت المحدد؛ نظام الرادار الآلي يرصد ذلك تلقائياً ويطبق عقوبات فورية.\n"
    "━━━━━━━━━━━━━━━━━━\n"
    "⚖️ <b>تحتفظ الإدارة بالحق الكامل في استبعاد أو حظر أي قناة لا تلتزم بهذه الشروط.</b>\n"
    "</blockquote>\n\n"
    "👨‍💻 <b>إدارة المنصة:</b> @NEXUS_IMTIAZ"
)

class DatabaseManager:
    """مدير قاعدة البيانات - يدعم تلقائياً SQLite محلياً و PostgreSQL سحابياً (Supabase)"""

    @staticmethod
    def adapt_query(query: str) -> str:
        """تحويل استعلامات PostgreSQL إلى SQLite عند التشغيل المحلي"""
        q = query.replace('%s', '?')
        q = re.sub(r'EXTRACT\s*\([^)]+\)(?:::BIGINT)?', "strftime('%s', 'now')", q, flags=re.IGNORECASE)
        q = re.sub(r'\bSERIAL\s+PRIMARY\s+KEY\b', 'INTEGER PRIMARY KEY AUTOINCREMENT', q, flags=re.IGNORECASE)
        q = re.sub(r'\bBIGINT\b', 'INTEGER', q, flags=re.IGNORECASE)
        q = re.sub(r'\bEXCLUDED\.', 'excluded.', q, flags=re.IGNORECASE)
        return q

    def __init__(self):
        self.database_url = (DATABASE_URL or os.environ.get('DATABASE_URL', '')).strip()
        if self.database_url and HAS_PSYCOPG2:
            self.is_sqlite = False
            if self.database_url.startswith("postgres://"):
                self.database_url = self.database_url.replace("postgres://", "postgresql://", 1)
            logger.info("🐘 تم تفعيل وضع قاعدة البيانات السحابية PostgreSQL (Supabase / Render).")
        else:
            self.is_sqlite = True
            script_dir = os.path.dirname(os.path.abspath(__file__))
            self.db_name = os.path.join(script_dir, 'channels.db')
            logger.info(f"📁 تم تفعيل وضع قاعدة البيانات المحلية SQLite ({self.db_name}).")
        self.init_db()

    def get_connection(self):
        """إنشاء اتصال بقاعدة البيانات المناسبة للبيئة الحالية"""
        if self.is_sqlite:
            return sqlite3.connect(self.db_name)
        else:
            return psycopg2.connect(self.database_url)

    def execute_query(self, query: str, params: tuple = (), fetch: bool = False):
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            q = self.adapt_query(query) if self.is_sqlite else query
            cursor.execute(q, params)
            if fetch:
                result = cursor.fetchall()
                conn.commit()
                return result
            else:
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"خطأ في قاعدة البيانات: {e}")
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass
            return False
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

    def execute_returning(self, query: str, params: tuple = ()):
        """تنفيذ INSERT وإرجاع الـ id الجديد في كلا الوضعين"""
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            if self.is_sqlite:
                q = self.adapt_query(query)
                try:
                    cursor.execute(q, params)
                    res = cursor.fetchone()
                    if res:
                        conn.commit()
                        return res[0]
                except Exception:
                    q_no_ret = re.sub(r'\s*RETURNING\s+\w+', '', q, flags=re.IGNORECASE)
                    cursor.execute(q_no_ret, params)
                    conn.commit()
                    return cursor.lastrowid
            else:
                cursor.execute(query, params)
                res = cursor.fetchone()
                conn.commit()
                return res[0] if res else None
        except Exception as e:
            logger.error(f"خطأ في execute_returning: {e}")
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass
            return None
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

    def init_db(self):
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            if self.is_sqlite:
                self._init_sqlite_tables(cursor, conn)
            else:
                self._init_postgres_tables(cursor, conn)
        except Exception as e:
            logger.error(f"❌ خطأ في تهيئة قاعدة البيانات: {e}")
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass
            raise
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

    def _init_sqlite_tables(self, cursor, conn):
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id TEXT NOT NULL UNIQUE,
            channel_name TEXT
        )''')
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE,
            username TEXT UNIQUE,
            added_at INTEGER DEFAULT (strftime('%s', 'now'))
        )''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_id ON admins(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_username ON admins(username)')
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS sent_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id INTEGER,
            channel_id TEXT,
            chat_id INTEGER,
            message_type TEXT,
            timestamp INTEGER DEFAULT (strftime('%s', 'now')),
            content TEXT,
            batch_id INTEGER,
            is_deleted_early INTEGER DEFAULT 0
        )''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_sent_batch ON sent_messages(batch_id)')
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS pending_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            message_id INTEGER,
            chat_id INTEGER,
            message_type TEXT,
            content TEXT,
            created_at INTEGER DEFAULT (strftime('%s', 'now')),
            batch_id INTEGER
        )''')
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS bot_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE,
            username TEXT,
            first_name TEXT,
            started_at INTEGER DEFAULT (strftime('%s', 'now'))
        )''')
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS listing_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            username TEXT,
            first_name TEXT,
            channel_id TEXT NOT NULL,
            channel_title TEXT,
            members_count INTEGER,
            status TEXT NOT NULL DEFAULT 'draft',
            reject_reason TEXT,
            last_milestone INTEGER DEFAULT 0,
            created_at INTEGER DEFAULT (strftime('%s', 'now')),
            updated_at INTEGER DEFAULT (strftime('%s', 'now'))
        )''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_listing_user ON listing_requests(user_id)')
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS bot_settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )''')
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS blacklist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target_type TEXT NOT NULL,
            target_id TEXT NOT NULL UNIQUE,
            reason TEXT,
            blocked_by TEXT,
            created_at INTEGER DEFAULT (strftime('%s', 'now'))
        )''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_blacklist_target ON blacklist(target_id)')
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS scheduled_deletions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id INTEGER UNIQUE,
            delete_at INTEGER NOT NULL,
            hours_duration INTEGER NOT NULL,
            total_messages INTEGER,
            created_at INTEGER DEFAULT (strftime('%s', 'now')),
            status TEXT DEFAULT 'pending'
        )''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_sched_del ON scheduled_deletions(status, delete_at)')
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS channel_strikes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id TEXT NOT NULL UNIQUE,
            strikes_count INTEGER DEFAULT 0,
            last_strike_at INTEGER DEFAULT (strftime('%s', 'now')),
            last_reason TEXT
        )''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_channel_strikes ON channel_strikes(channel_id)')
        cursor.execute('SELECT user_id FROM admins WHERE user_id = ?', (ADMIN_ID,))
        if not cursor.fetchone():
            cursor.execute('INSERT INTO admins (user_id, username) VALUES (?, ?)', (ADMIN_ID, 'المشرف الأساسي'))
        conn.commit()
        logger.info("✅ تم تهيئة قاعدة البيانات بنجاح (SQLite محلياً)")

    def _init_postgres_tables(self, cursor, conn):
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS channels (
            id SERIAL PRIMARY KEY,
            channel_id TEXT NOT NULL UNIQUE,
            channel_name TEXT
        )''')
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS admins (
            id SERIAL PRIMARY KEY,
            user_id BIGINT UNIQUE,
            username TEXT UNIQUE,
            added_at BIGINT DEFAULT EXTRACT(EPOCH FROM NOW())::BIGINT
        )''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_id ON admins(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_username ON admins(username)')
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS sent_messages (
            id SERIAL PRIMARY KEY,
            message_id BIGINT,
            channel_id TEXT,
            chat_id BIGINT,
            message_type TEXT,
            timestamp BIGINT DEFAULT EXTRACT(EPOCH FROM NOW())::BIGINT,
            content TEXT,
            batch_id BIGINT,
            is_deleted_early INTEGER DEFAULT 0
        )''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_sent_batch ON sent_messages(batch_id)')
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS pending_messages (
            id SERIAL PRIMARY KEY,
            user_id BIGINT,
            message_id BIGINT,
            chat_id BIGINT,
            message_type TEXT,
            content TEXT,
            created_at BIGINT DEFAULT EXTRACT(EPOCH FROM NOW())::BIGINT,
            batch_id BIGINT
        )''')
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS bot_users (
            id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL UNIQUE,
            username TEXT,
            first_name TEXT,
            started_at BIGINT DEFAULT EXTRACT(EPOCH FROM NOW())::BIGINT
        )''')
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS listing_requests (
            id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            username TEXT,
            first_name TEXT,
            channel_id TEXT NOT NULL,
            channel_title TEXT,
            members_count INTEGER,
            status TEXT NOT NULL DEFAULT 'draft',
            reject_reason TEXT,
            last_milestone INTEGER DEFAULT 0,
            created_at BIGINT DEFAULT EXTRACT(EPOCH FROM NOW())::BIGINT,
            updated_at BIGINT DEFAULT EXTRACT(EPOCH FROM NOW())::BIGINT
        )''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_listing_user ON listing_requests(user_id)')
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS bot_settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )''')
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS blacklist (
            id SERIAL PRIMARY KEY,
            target_type TEXT NOT NULL,
            target_id TEXT NOT NULL UNIQUE,
            reason TEXT,
            blocked_by TEXT,
            created_at BIGINT DEFAULT EXTRACT(EPOCH FROM NOW())::BIGINT
        )''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_blacklist_target ON blacklist(target_id)')
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS scheduled_deletions (
            id SERIAL PRIMARY KEY,
            batch_id BIGINT UNIQUE,
            delete_at BIGINT NOT NULL,
            hours_duration INTEGER NOT NULL,
            total_messages INTEGER,
            created_at BIGINT DEFAULT EXTRACT(EPOCH FROM NOW())::BIGINT,
            status TEXT DEFAULT 'pending'
        )''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_sched_del ON scheduled_deletions(status, delete_at)')
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS channel_strikes (
            id SERIAL PRIMARY KEY,
            channel_id TEXT NOT NULL UNIQUE,
            strikes_count INTEGER DEFAULT 0,
            last_strike_at BIGINT DEFAULT EXTRACT(EPOCH FROM NOW())::BIGINT,
            last_reason TEXT
        )''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_channel_strikes ON channel_strikes(channel_id)')
        cursor.execute('SELECT user_id FROM admins WHERE user_id = %s', (ADMIN_ID,))
        if not cursor.fetchone():
            cursor.execute('INSERT INTO admins (user_id, username) VALUES (%s, %s)', (ADMIN_ID, 'المشرف الأساسي'))
        conn.commit()
        logger.info("✅ تم تهيئة قاعدة البيانات بنجاح (PostgreSQL سحابياً)")

    def save_scheduled_deletion(self, batch_id: int, delete_at: int, hours_duration: int, total_messages: int) -> int:
        return self.execute_query(
            '''INSERT INTO scheduled_deletions (batch_id, delete_at, hours_duration, total_messages, created_at, status)
               VALUES (%s, %s, %s, %s, EXTRACT(EPOCH FROM NOW())::BIGINT, 'pending')
               ON CONFLICT (batch_id) DO UPDATE SET
                   delete_at = EXCLUDED.delete_at,
                   hours_duration = EXCLUDED.hours_duration,
                   total_messages = EXCLUDED.total_messages,
                   status = 'pending' ''',
            (batch_id, delete_at, hours_duration, total_messages)
        )

    def get_expired_scheduled_deletions(self):
        return self.execute_query(
            '''SELECT id, batch_id, hours_duration, total_messages FROM scheduled_deletions 
               WHERE status='pending' AND delete_at <= EXTRACT(EPOCH FROM NOW())::BIGINT''',
            fetch=True
        ) or []

    def get_active_scheduled_deletion(self):
        rows = self.execute_query(
            '''SELECT id, batch_id, delete_at, hours_duration, total_messages, created_at 
               FROM scheduled_deletions WHERE status='pending' AND delete_at > EXTRACT(EPOCH FROM NOW())::BIGINT
               ORDER BY id DESC LIMIT 1''',
            fetch=True
        )
        return rows[0] if rows else None

    def mark_scheduled_deletion_done(self, sched_id: int):
        self.execute_query("UPDATE scheduled_deletions SET status='completed' WHERE id=%s", (sched_id,))

    def cancel_scheduled_deletion(self, batch_id: int = None, sched_id: int = None):
        if sched_id:
            self.execute_query("UPDATE scheduled_deletions SET status='cancelled' WHERE id=%s", (sched_id,))
        elif batch_id:
            self.execute_query("UPDATE scheduled_deletions SET status='cancelled' WHERE batch_id=%s", (batch_id,))

    def get_channel_strikes(self, channel_id: str) -> int:
        clean_ch = channel_id.strip()
        variants = [clean_ch, clean_ch.lower()]
        if clean_ch.startswith('@'):
            variants.append(clean_ch[1:])
        else:
            variants.append(f"@{clean_ch}")
        for v in variants:
            res = self.execute_query('SELECT strikes_count FROM channel_strikes WHERE channel_id = %s', (v,), fetch=True)
            if res and res[0][0] is not None:
                return res[0][0]
        return 0

    def add_channel_strike(self, channel_id: str, reason: str = "حذف منشور المجلد مبكراً") -> int:
        clean_ch = channel_id.strip()
        if not clean_ch.startswith('@') and not clean_ch.startswith('-'):
            clean_ch = f"@{clean_ch}"
        current = self.get_channel_strikes(clean_ch)
        new_count = current + 1
        self.execute_query(
            '''INSERT INTO channel_strikes (channel_id, strikes_count, last_strike_at, last_reason)
               VALUES (%s, %s, EXTRACT(EPOCH FROM NOW())::BIGINT, %s)
               ON CONFLICT (channel_id) DO UPDATE SET
               strikes_count = channel_strikes.strikes_count + 1,
               last_strike_at = EXTRACT(EPOCH FROM NOW())::BIGINT,
               last_reason = EXCLUDED.last_reason''',
            (clean_ch, new_count, reason)
        )
        return new_count

    def reset_channel_strikes(self, channel_id: str) -> bool:
        clean_ch = channel_id.strip()
        variants = [clean_ch, clean_ch.lower()]
        if clean_ch.startswith('@'):
            variants.append(clean_ch[1:])
        else:
            variants.append(f"@{clean_ch}")
        for v in set(variants):
            self.execute_query('DELETE FROM channel_strikes WHERE channel_id = %s', (v,))
        return True

    def get_channel_owner_id(self, channel_id: str) -> int:
        clean_ch = channel_id.strip()
        variants = [clean_ch, clean_ch.lower()]
        if clean_ch.startswith('@'):
            variants.append(clean_ch[1:])
        else:
            variants.append(f"@{clean_ch}")
        for v in set(variants):
            res = self.execute_query(
                "SELECT user_id FROM listing_requests WHERE (channel_id = %s OR channel_id = %s) AND status='approved' ORDER BY id DESC LIMIT 1",
                (v, v), fetch=True
            )
            if res and res[0][0]:
                return res[0][0]
        return None

    def get_active_broadcast_messages_for_monitoring(self):
        return self.execute_query(
            '''SELECT s.id, s.message_id, s.channel_id, s.batch_id, 
                      COALESCE(sd.hours_duration, 0) as hours_duration
               FROM sent_messages s
               LEFT JOIN scheduled_deletions sd ON s.batch_id = sd.batch_id
               WHERE (s.is_deleted_early IS NULL OR s.is_deleted_early = 0)
                 AND s.timestamp > (EXTRACT(EPOCH FROM NOW())::BIGINT - 86400)
                 AND (sd.status IS NULL OR sd.status = 'pending')
                 AND (sd.delete_at IS NULL OR sd.delete_at > (EXTRACT(EPOCH FROM NOW())::BIGINT + 10))
               ORDER BY s.id DESC''',
            fetch=True
        ) or []

    def mark_sent_message_deleted_early(self, sent_id: int):
        self.execute_query('UPDATE sent_messages SET is_deleted_early = 1 WHERE id = %s', (sent_id,))

    def get_last_milestone(self, request_id: int) -> int:
        res = self.execute_query('SELECT last_milestone FROM listing_requests WHERE id = %s', (request_id,), fetch=True)
        return res[0][0] if res and res[0][0] is not None else 0

    def update_last_milestone(self, request_id: int, milestone: int) -> bool:
        return self.execute_query(
            '''UPDATE listing_requests SET last_milestone = %s, updated_at = EXTRACT(EPOCH FROM NOW())::BIGINT WHERE id = %s''',
            (milestone, request_id)
        )

    def get_all_approved_requests(self) -> List[Tuple]:
        result = self.execute_query(
            '''SELECT id, user_id, username, first_name, channel_id, channel_title,
                      members_count, status, reject_reason, created_at, last_milestone
               FROM listing_requests
               WHERE status = 'approved' ''',
            fetch=True
        )
        return result or []

    def is_blacklisted(self, user_id: int = None, channel_id: str = None) -> bool:
        if user_id:
            res = self.execute_query(
                "SELECT 1 FROM blacklist WHERE target_type = 'user' AND target_id = %s",
                (str(user_id),), fetch=True
            )
            if res:
                return True
        if channel_id:
            clean_chan = channel_id.strip()
            variants = [clean_chan, clean_chan.lower()]
            if clean_chan.startswith('@'):
                variants.append(clean_chan[1:])
                variants.append(clean_chan[1:].lower())
            else:
                variants.append(f"@{clean_chan}")
                variants.append(f"@{clean_chan}".lower())
            for v in set(variants):
                res = self.execute_query(
                    "SELECT 1 FROM blacklist WHERE target_type = 'channel' AND target_id = %s",
                    (v,), fetch=True
                )
                if res:
                    return True
        return False

    def add_to_blacklist(self, target_type: str, target_id: str, reason: str = None, blocked_by: str = None) -> bool:
        target_clean = str(target_id).strip()
        if target_type == 'channel' and not target_clean.startswith('@') and not target_clean.startswith('-'):
            target_clean = f"@{target_clean}"
        return self.execute_query(
            '''INSERT INTO blacklist (target_type, target_id, reason, blocked_by)
               VALUES (%s, %s, %s, %s)
               ON CONFLICT (target_id) DO UPDATE SET
                   reason = EXCLUDED.reason,
                   blocked_by = EXCLUDED.blocked_by,
                   created_at = EXTRACT(EPOCH FROM NOW())::BIGINT''',
            (target_type, target_clean, reason, blocked_by)
        )

    def remove_from_blacklist(self, target_id: str) -> bool:
        target_clean = str(target_id).strip()
        variants = [target_clean, target_clean.lower()]
        if target_clean.startswith('@'):
            variants.append(target_clean[1:])
            variants.append(target_clean[1:].lower())
        else:
            variants.append(f"@{target_clean}")
            variants.append(f"@{target_clean}".lower())
        placeholders = ','.join('%s' for _ in set(variants))
        return self.execute_query(f'DELETE FROM blacklist WHERE target_id IN ({placeholders})', tuple(set(variants)))

    def get_blacklist(self) -> List[Tuple]:
        result = self.execute_query(
            'SELECT id, target_type, target_id, reason, blocked_by, created_at FROM blacklist ORDER BY id DESC',
            fetch=True
        )
        return result or []

    def get_setting(self, key: str, default: str = None) -> str:
        result = self.execute_query('SELECT value FROM bot_settings WHERE key = %s', (key,), fetch=True)
        return result[0][0] if result else default

    def set_setting(self, key: str, value: str) -> bool:
        return self.execute_query(
            '''INSERT INTO bot_settings (key, value) VALUES (%s, %s)
               ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value''',
            (key, str(value))
        )

    def delete_setting(self, key: str) -> bool:
        return self.execute_query('DELETE FROM bot_settings WHERE key = %s', (key,))
    
    def is_admin(self, user_id: int = None, username: str = None) -> bool:
        """التحقق من كون المستخدم مشرفاً عبر user_id أو username"""
        if not user_id and not username:
            logger.warning(f"التحقق من المشرف بدون معاملات - user_id: {user_id}, username: {username}")
            return False
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            if user_id:
                cursor.execute('SELECT 1 FROM admins WHERE user_id = %s', (user_id,))
                if cursor.fetchone():
                    logger.info(f"✅ تم العثور على المشرف بالـ user_id: {user_id}")
                    return True

            if username:
                username_clean = username.lstrip('@').strip()
                if username_clean:
                    username_variants = list(set([
                        username_clean,
                        f'@{username_clean}',
                        username_clean.lower(),
                        f'@{username_clean}'.lower()
                    ]))
                    for variant in username_variants:
                        cursor.execute(
                            'SELECT 1 FROM admins WHERE LOWER(TRIM(username)) = LOWER(TRIM(%s))',
                            (variant,)
                        )
                        if cursor.fetchone():
                            logger.info(f"✅ تم العثور على المشرف باليوزرنيم: {variant}")
                            return True
                    cursor.execute(
                        "SELECT 1 FROM admins WHERE LOWER(TRIM(REPLACE(username, '@', ''))) = LOWER(%s)",
                        (username_clean,)
                    )
                    if cursor.fetchone():
                        logger.info(f"✅ تم العثور على المشرف باليوزرنيم (بدون @): {username_clean}")
                        return True

            logger.warning(f"❌ لم يتم العثور على المشرف - user_id: {user_id}, username: {username}")
            return False
        except Exception as e:
            logger.error(f"خطأ في التحقق من المشرف: {e}")
            return False
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

    def add_channel(self, channel_id: str) -> bool:
        channel_name = channel_id[1:] if channel_id.startswith('@') else channel_id
        return self.execute_query(
            'INSERT INTO channels (channel_id, channel_name) VALUES (%s, %s) ON CONFLICT (channel_id) DO NOTHING',
            (channel_id, channel_name)
        )

    def save_bot_user(self, user_id: int, username: str = None, first_name: str = None) -> bool:
        return self.execute_query(
            '''INSERT INTO bot_users (user_id, username, first_name)
               VALUES (%s, %s, %s)
               ON CONFLICT (user_id) DO UPDATE SET
                   username=EXCLUDED.username,
                   first_name=EXCLUDED.first_name''',
            (user_id, username, first_name)
        )

    def get_all_bot_users(self) -> List[Tuple]:
        result = self.execute_query('SELECT user_id FROM bot_users ORDER BY id ASC', fetch=True)
        return result or []

    def save_listing_request(
        self,
        user_id: int,
        username: str,
        first_name: str,
        channel_id: str,
        channel_title: str,
        members_count: int,
        status: str = "draft",
    ) -> int:
        return self.execute_returning(
            '''INSERT INTO listing_requests
               (user_id, username, first_name, channel_id, channel_title, members_count, status)
               VALUES (%s, %s, %s, %s, %s, %s, %s)
               RETURNING id''',
            (user_id, username, first_name, channel_id, channel_title, members_count, status)
        )

    def get_listing_request(self, request_id: int):
        result = self.execute_query(
            '''SELECT id, user_id, username, first_name, channel_id, channel_title,
                      members_count, status, reject_reason, created_at, last_milestone
               FROM listing_requests WHERE id = %s''',
            (request_id,), fetch=True
        )
        return result[0] if result else None

    def get_latest_listing_request(self, user_id: int):
        result = self.execute_query(
            '''SELECT id, user_id, username, first_name, channel_id, channel_title,
                      members_count, status, reject_reason, created_at, last_milestone
               FROM listing_requests
               WHERE user_id = %s AND status != 'cancelled'
               ORDER BY id DESC LIMIT 1''',
            (user_id,), fetch=True
        )
        return result[0] if result else None

    def update_listing_status(self, request_id: int, status: str, user_id: int = None, reject_reason: str = None) -> bool:
        if reject_reason is not None:
            return self.execute_query(
                '''UPDATE listing_requests SET status = %s, reject_reason = %s, updated_at = EXTRACT(EPOCH FROM NOW())::BIGINT
                   WHERE id = %s''',
                (status, reject_reason, request_id)
            )
        if user_id is None:
            return self.execute_query(
                '''UPDATE listing_requests SET status = %s, updated_at = EXTRACT(EPOCH FROM NOW())::BIGINT
                   WHERE id = %s''',
                (status, request_id)
            )
        return self.execute_query(
            '''UPDATE listing_requests SET status = %s, updated_at = EXTRACT(EPOCH FROM NOW())::BIGINT
               WHERE id = %s AND user_id = %s''',
            (status, request_id, user_id)
        )

    def get_admin_user_ids(self) -> List[int]:
        rows = self.execute_query('SELECT user_id FROM admins WHERE user_id IS NOT NULL', fetch=True) or []
        return [uid for (uid,) in rows if uid]

    def get_all_channels(self) -> List[Tuple]:
        result = self.execute_query('SELECT channel_id, channel_name FROM channels', fetch=True)
        if result is False:
            logger.error("فشل في قراءة القنوات من قاعدة البيانات")
            return []
        channels = result or []
        logger.info(f"تم جلب {len(channels)} قناة من قاعدة البيانات")
        return channels

    def get_channels_with_ids(self) -> List[Tuple]:
        result = self.execute_query(
            'SELECT id, channel_id, channel_name FROM channels ORDER BY id ASC',
            fetch=True
        )
        if result is False:
            logger.error("فشل في قراءة القنوات من قاعدة البيانات")
            return []
        return result or []

    def get_channel_by_pk(self, pk: int):
        result = self.execute_query(
            'SELECT id, channel_id, channel_name FROM channels WHERE id = %s',
            (pk,), fetch=True
        )
        return result[0] if result else None

    def delete_channel(self, channel_id: str) -> bool:
        return self.execute_query('DELETE FROM channels WHERE channel_id = %s', (channel_id,))

    def save_sent_message(self, message_id: int, channel_id: str, chat_id: int, message_type: str, content: str, batch_id: int = None) -> bool:
        return self.execute_query(
            '''INSERT INTO sent_messages (message_id, channel_id, chat_id, message_type, content, batch_id)
            VALUES (%s, %s, %s, %s, %s, %s)''',
            (message_id, channel_id, chat_id, message_type, content, batch_id)
        )

    def new_broadcast_batch_id(self) -> int:
        result = self.execute_query(
            'SELECT COALESCE(MAX(batch_id), 0) + 1 FROM sent_messages',
            fetch=True
        )
        return result[0][0] if result else 1

    def get_recent_broadcasts(self, limit: int = 10) -> List[Tuple]:
        return self.execute_query(
            '''SELECT s.batch_id, s.content, s.message_type, c.cnt
               FROM sent_messages s
               INNER JOIN (
                   SELECT batch_id, MAX(id) AS max_id, COUNT(*) AS cnt
                   FROM sent_messages
                   GROUP BY batch_id
               ) c ON s.id = c.max_id
               ORDER BY s.id DESC
               LIMIT %s''',
            (limit,), fetch=True
        ) or []

    def get_broadcast_rows(self, batch_id: int) -> List[Tuple]:
        return self.execute_query(
            '''SELECT sm.id, sm.message_id, sm.channel_id,
                      COALESCE(NULLIF(ch.channel_name, ''), sm.channel_id)
               FROM sent_messages sm
               LEFT JOIN channels ch ON ch.channel_id = sm.channel_id
               WHERE sm.batch_id = %s
               ORDER BY sm.id ASC''',
            (batch_id,), fetch=True
        ) or []

    def get_broadcast_preview(self, batch_id: int) -> Tuple:
        result = self.execute_query(
            '''SELECT content, message_type FROM sent_messages
               WHERE batch_id = %s ORDER BY id DESC LIMIT 1''',
            (batch_id,), fetch=True
        )
        return result[0] if result else None

    def get_recent_messages(self, limit: int = 10) -> List[Tuple]:
        return self.execute_query(
            '''SELECT id, message_id, channel_id, message_type, content
            FROM sent_messages ORDER BY id DESC LIMIT %s''',
            (limit,), fetch=True
        ) or []

    def delete_message_from_db(self, message_db_id: int) -> bool:
        return self.execute_query('DELETE FROM sent_messages WHERE id = %s', (message_db_id,))

    def get_latest_sent_for_channel(self, channel_id: str):
        result = self.execute_query(
            '''SELECT id, message_id, channel_id FROM sent_messages
               WHERE channel_id = %s ORDER BY id DESC LIMIT 1''',
            (channel_id,), fetch=True
        )
        return result[0] if result else None

    def get_latest_batch_id(self):
        result = self.execute_query(
            'SELECT batch_id FROM sent_messages ORDER BY id DESC LIMIT 1',
            fetch=True
        )
        if not result:
            return None
        return result[0][0]

    def delete_broadcast_from_db(self, batch_id: int) -> bool:
        return self.execute_query('DELETE FROM sent_messages WHERE batch_id = %s', (batch_id,))

    def save_pending_message(self, user_id: int, message_id: int, chat_id: int, message_type: str, content: str) -> int:
        """حفظ رسالة مؤقتة وإرجاع ID"""
        batch_id = self.new_broadcast_batch_id()
        return self.execute_returning(
            '''INSERT INTO pending_messages (user_id, message_id, chat_id, message_type, content, batch_id)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id''',
            (user_id, message_id, chat_id, message_type, content, batch_id)
        )

    def get_pending_message(self, pending_id: int) -> Tuple:
        """الحصول على رسالة مؤقتة"""
        result = self.execute_query(
            'SELECT user_id, message_id, chat_id, message_type, content, batch_id FROM pending_messages WHERE id = %s',
            (pending_id,), fetch=True
        )
        return result[0] if result else None

    def was_sent_in_batch(self, batch_id: int, channel_id: str) -> bool:
        if batch_id is None:
            return False
        result = self.execute_query(
            'SELECT 1 FROM sent_messages WHERE batch_id = %s AND channel_id = %s LIMIT 1',
            (batch_id, channel_id), fetch=True
        )
        return bool(result)

    def delete_pending_message(self, pending_id: int) -> bool:
        """حذف رسالة مؤقتة"""
        return self.execute_query('DELETE FROM pending_messages WHERE id = %s', (pending_id,))

    def add_admin(self, user_id: int = None, username: str = None) -> bool:
        """إضافة مشرف جديد"""
        if not user_id and not username:
            logger.error("محاولة إضافة مشرف بدون user_id أو username")
            return False

        if username:
            username = username.lstrip('@').strip()
            if not username:
                username = None

        if self.is_admin(user_id=user_id, username=username):
            logger.info(f"المشرف موجود بالفعل - user_id: {user_id}, username: {username}")
            return False

        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute(
                'INSERT INTO admins (user_id, username) VALUES (%s, %s)',
                (user_id, username)
            )
            conn.commit()
            logger.info(f"✅ تم إضافة مشرف جديد - user_id: {user_id}, username: {username}")
            return True
        except PgIntegrityError:
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass
            if user_id and username:
                try:
                    conn2 = self.get_connection()
                    cursor2 = conn2.cursor()
                    cursor2.execute('UPDATE admins SET username = %s WHERE user_id = %s AND username IS NULL', (username, user_id))
                    cursor2.execute('UPDATE admins SET user_id = %s WHERE username = %s AND user_id IS NULL', (user_id, username))
                    conn2.commit()
                    conn2.close()
                    return True
                except Exception as e2:
                    logger.warning(f"المشرف موجود بالفعل: {e2}")
                    return False
            return False
        except Exception as e:
            logger.error(f"خطأ في إضافة المشرف: {e}")
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass
            return False
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass


# تهيئة قاعدة البيانات
db = DatabaseManager()

def is_admin(user_id: int, username: str = None) -> bool:
    """التحقق من كون المستخدم مشرفاً"""
    return db.is_admin(user_id=user_id, username=username)

def is_owner(user_id: int) -> bool:
    """التحقق من كون المستخدم هو المشرف الأساسي (الاونر)"""
    return user_id == ADMIN_ID

def clear_chat_step_handlers(chat_id: int):
    """إلغاء وتصفير أي خطوات معلقة للمشرف أو المستخدم لتفادي تداخل العمليات"""
    try:
        bot.clear_step_handler_by_chat_id(chat_id=chat_id)
    except Exception:
        try:
            if hasattr(bot, 'step_helper') and hasattr(bot.step_helper, 'handlers'):
                bot.step_helper.handlers.pop(chat_id, None)
        except Exception:
            pass

def get_bot_username() -> str:
    global BOT_USERNAME
    if BOT_USERNAME:
        return BOT_USERNAME
    try:
        BOT_USERNAME = bot.get_me().username or ""
    except Exception as e:
        logger.error(f"فشل جلب يوزر البوت: {e}")
        BOT_USERNAME = ""
    return BOT_USERNAME

def parse_channel_ref(raw_input: str):
    if not raw_input:
        return None
    text = raw_input.strip()
    if text.startswith("https://t.me/") or text.startswith("http://t.me/") or text.startswith("t.me/"):
        path = text.split("t.me/", 1)[-1].split("?")[0].strip("/")
        if not path or path.startswith("+") or path.startswith("joinchat"):
            return None
        path = path.split("/")[0]
        return f"@{path}" if not path.startswith("@") else path
    if text.startswith("@"):
        return text.split()[0]
    if re.match(r"^[a-zA-Z0-9][a-zA-Z0-9_]{3,31}$", text):
        return f"@{text}"
    return None

def inspect_channel(channel_ref: str):
    chat = None
    last_err = None
    for attempt in range(2):
        try:
            chat = bot.get_chat(channel_ref)
            break
        except Exception as e:
            last_err = e
            time.sleep(1)

    if not chat:
        logger.warning(f"فشل get_chat لـ {channel_ref}: {last_err}")
        return None, "تعذر الوصول للقناة حالياً. تأكد من صحة الرابط/المعرف، وأن القناة عامة أو البوت بداخلها."

    if getattr(chat, "type", None) != "channel":
        return None, "هذا المعرف ليس قناة! يرجى إرسال معرف قناة (Channel) عامة وليس مجموعة."

    me = bot.get_me()
    is_admin = False
    can_post = False
    try:
        member = bot.get_chat_member(chat.id, me.id)
        is_admin = member.status in ("administrator", "creator")
        can_post = member.status == "creator" or bool(getattr(member, "can_post_messages", False))
    except Exception as e:
        logger.info(f"البوت ليس عضواً في {channel_ref}: {e}")

    try:
        members_count = bot.get_chat_member_count(chat.id)
    except Exception:
        try:
            members_count = bot.get_chat_members_count(chat.id)
        except Exception:
            members_count = 0

    username = f"@{chat.username}" if chat.username else channel_ref
    return {
        "telegram_id": chat.id,
        "username": username,
        "title": chat.title or username,
        "members_count": members_count or 0,
        "bot_ok": is_admin and can_post,
    }, None

def add_bot_admin_url() -> str:
    uname = get_bot_username()
    if not uname:
        return "https://t.me/"
    return (
        f"https://t.me/{uname}?startchannel"
        "&admin=post_messages+edit_messages+delete_messages"
    )

def show_user_menu(chat_id: int, message_id: int = None):
    text = (
        "<blockquote>\n"
        "✨ <b>مرحباً بك في بوت امتياز (@NEXUS_IMTIAZ) لدعم ونشر قنوات البكالوريا! 🚀</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "📚 <b>منصتك الأولى للنمو الحقيقي والوصول لآلاف الطلبة:</b>\n\n"
        "• 📢 <b>إدراج قناتك في مجلدات الدعم الموحدة</b>\n"
        "• 📈 <b>تتبع نمو المشتركين وإحصائيات القناة لحظة بلحظة</b>\n"
        "• 🏆 <b>بطاقات تهنئة حصرية عند كسر حواجز النمو</b>\n"
        "• 🛡️ <b>نشر تلقائي ومنظم يضمن أمان قناتك</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "👇 <b>اختر ما تود القيام به من الأزرار أدناه:</b>\n"
        "</blockquote>\n\n"
        "👨‍💻 <b>إدارة المنصة:</b> @NEXUS_IMTIAZ"
    )
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("🚀 تقديم طلب إدراج قناة", callback_data="u_apply"),
        types.InlineKeyboardButton("📋 متابعة حالة طلبي", callback_data="u_status"),
        types.InlineKeyboardButton("📈 إحصائيات قناتي فالمجلد", callback_data="u_growth"),
        types.InlineKeyboardButton("💬 الدعم الفني وحل المشاكل / إرسال انشغال", callback_data="u_support"),
        types.InlineKeyboardButton("📜 شروط وقوانين الدعم", callback_data="u_rules"),
    )
    try:
        if message_id:
            bot.edit_message_text(text, chat_id, message_id, reply_markup=markup, parse_mode='HTML')
        else:
            bot.send_message(chat_id, text, reply_markup=markup, parse_mode='HTML')
    except Exception:
        plain_text = text.replace("<blockquote>\n", "").replace("</blockquote>\n", "")
        try:
            if message_id:
                bot.edit_message_text(plain_text, chat_id, message_id, reply_markup=markup, parse_mode='HTML')
            else:
                bot.send_message(chat_id, plain_text, reply_markup=markup, parse_mode='HTML')
        except Exception:
            bot.send_message(chat_id, plain_text, reply_markup=markup, parse_mode=None)

def check_and_send_growth_celebration(request_id: int, user_id: int, first_name: str, channel_id: str, channel_title: str, current_members: int, initial_members: int, last_milestone: int = None) -> bool:
    """إرسال بطاقة التهنئة التلقائية عند كسر حاجز ألف مشترك جديد"""
    if not current_members or current_members < 1000:
        return False

    current_milestone = (current_members // 1000) * 1000
    
    if last_milestone is None:
        last_milestone = db.get_last_milestone(request_id)
        
    init_base = (initial_members // 1000) * 1000 if initial_members else 0
    
    # يجب أن يكون الحاجز الحالي أكبر من حاجز التسجيل وأكبر من آخر حاجز تم تهنئته
    if current_milestone <= init_base or current_milestone <= last_milestone:
        return False

    milestone_k = f"{current_milestone // 1000}k" if current_milestone >= 1000 else str(current_milestone)
    subscriber_count_str = f"{current_milestone:,}"
    safe_name = html.escape(first_name or "صديقنا المبدع")
    safe_title = html.escape(channel_title or channel_id)
    clean_chan = channel_id.lstrip('@')
    chan_url = f"https://t.me/{clean_chan}"
    
    text = (
        f"🎉 <b>مبروك وصول قناتك لـ {milestone_k} مشترك!</b> 🚀\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"يا {safe_name}، قناتك الممتازة [<b>{safe_title}</b>] فاتت رسمياً حاجز <b>{subscriber_count_str}</b> مشترك! 🚀\n\n"
        "كل خطوة تكبرها هي دليل على جودة المحتوى لي تقدم فيه، ويسعدنا بزاف فالبوت نكونوا جزء من هاد الرحلة والنمو الحقيقي. "
        "واصل الإبداع، فخورون بوجود قناتك معنا في المجلد، ونتمنى لك دوام النمو والتألق في عالم صناعة المحتوى التعليمي! ✨💪\n\n"
        "ادارة : @NEXUS_IMTIAZ\n"
        "━━━━━━━━━━━━━━━━━━"
    )
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("👁️ معاينة القناة", url=chan_url),
        types.InlineKeyboardButton("📈 إحصائيات قناتي", callback_data="u_growth")
    )
    
    try:
        bot.send_message(user_id, text, reply_markup=markup, parse_mode='HTML')
        db.update_last_milestone(request_id, current_milestone)
        logger.info(f"🏆 تم إرسال بطاقة التهنئة بالنمو ({milestone_k}) للمستخدم {user_id} لقناته {channel_id}")
        return True
    except Exception as e:
        logger.warning(f"تعذر إرسال بطاقة التهنئة للمستخدم {user_id}: {e}")
        return False

def check_all_channels_milestones():
    """فحص جميع القنوات المعتمدة وإرسال بطاقات التهنئة للمشتركين الذين حققوا حواجز نمو جديدة"""
    approved = db.get_all_approved_requests()
    if not approved:
        return 0
    
    celebrated_count = 0
    for req in approved:
        try:
            req_id, uid, _un, fn, ch_id, ch_title, init_m, st, rej, cr_at, last_m = req
            info, err = inspect_channel(ch_id)
            if info and info["members_count"]:
                curr_m = info["members_count"]
                sent = check_and_send_growth_celebration(
                    request_id=req_id,
                    user_id=uid,
                    first_name=fn,
                    channel_id=ch_id,
                    channel_title=info["title"] or ch_title,
                    current_members=curr_m,
                    initial_members=init_m or 0,
                    last_milestone=last_m
                )
                if sent:
                    celebrated_count += 1
            time.sleep(0.5)
        except Exception as e:
            logger.warning(f"خطأ أثناء فحص إنجاز القناة {req[4]}: {e}")
    return celebrated_count

def check_and_execute_scheduled_deletions():
    """فحص دوري لحذف المنشورات المؤقتة التي انتهت مدتها المحددة"""
    expired_list = db.get_expired_scheduled_deletions()
    if not expired_list:
        return
    
    for item in expired_list:
        sched_id, batch_id, hours_duration, total_msgs = item
        rows = db.get_broadcast_rows(batch_id)
        
        deleted_count = 0
        failed_count = 0
        
        if rows:
            for row_id, mid, ch_id, _name in rows:
                if delete_message_from_channel(ch_id, mid):
                    deleted_count += 1
                else:
                    failed_count += 1
                db.delete_message_from_db(row_id)
        
        db.mark_scheduled_deletion_done(sched_id)
        logger.info(f"⏱️ تم تنفيذ الحذف التلقائي للمنشور المؤقت (دفعة #{batch_id}): {deleted_count} نجح، {failed_count} فشل.")
        
        # إرسال إشعار للمشرفين / قروب الطلبات
        notify_text = (
            "<blockquote>\n"
            "⏱️ <b>إشعار اكتمال الحذف التلقائي للمنشور المؤقت! 🚀</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            f"⏳ <b>مدة النشر المحددة:</b> <b>{hours_duration} ساعة</b>\n"
            f"🗑️ <b>القنوات المحذوف منها بنجاح:</b> <b>{deleted_count} قناة</b>\n"
        )
        if failed_count > 0:
            notify_text += f"⚠️ <b>تعذر الحذف من:</b> <b>{failed_count} قناة</b>\n"
        notify_text += (
            "━━━━━━━━━━━━━━━━━━\n"
            "✅ <b>تم تنظيف القنوات أوتوماتيكياً في الموعد دون الحاجة لتدخلك!</b>\n"
            "</blockquote>\n\n"
            "👨‍💻 <b>إدارة المنصة:</b> @NEXUS_IMTIAZ"
        )
        send_notification_to_requests_group_or_admins(notify_text)

def check_if_message_deleted(channel_id: str, message_id: int) -> bool:
    """فحص صامت وشامل للتحقق مما إذا كان المنشور قد تم حذفه من القناة دون تثبيت إطلاقاً ودون أي أثر"""
    try:
        bot.edit_message_reply_markup(chat_id=channel_id, message_id=message_id, reply_markup=None)
        return False  # الرسالة موجودة
    except Exception as e:
        err_str = str(e).lower()
        # حالات تدل على أن الرسالة محذوفة 100%
        if any(w in err_str for w in [
            "message to edit not found",
            "message not found",
            "chat not found",
            "message_id_invalid",
            "wrong message_id"
        ]):
            return True
        # حالات تدل على أن البوت تم طرده أو سحب صلاحياته
        if any(w in err_str for w in [
            "bot was kicked",
            "not a member",
            "chat admin required",
            "have no rights",
            "not enough rights"
        ]):
            return True
        # حالات تدل على أن الرسالة موجودة (مثل: الرسالة لم تتغير أو رسالة محولة)
        if any(w in err_str for w in [
            "message is not modified",
            "message can't be edited",
            "cannot be edited",
            "message to edit not modified"
        ]):
            return False
            
        return False

def run_anti_cheat_check() -> int:
    """رادار كشف الغش: يفحص المنشورات المنشورة في القنوات ويتأكد من عدم حذفها قبل انقضاء الموعد"""
    active_msgs = db.get_active_broadcast_messages_for_monitoring()
    if not active_msgs:
        return 0
    
    from datetime import datetime
    now = datetime.now()
    day_name = DAYS_AR.get(now.weekday(), "")
    date_str = f"{day_name} {now.strftime('%Y-%m-%d')}"
    time_str = now.strftime("%H:%M:%S")
    detected_count = 0

    for msg_row in active_msgs:
        sent_id, message_id, channel_id, batch_id, hours_duration = msg_row
        
        is_deleted = check_if_message_deleted(channel_id, message_id)
        if is_deleted:
            detected_count += 1
            # 1. وضع علامة لعدم تكرار الإنذار لنفس المنشور
            db.mark_sent_message_deleted_early(sent_id)
            
            # 2. زيادة عدد الإنذارات للقناة في قاعدة البيانات
            new_strikes = db.add_channel_strike(channel_id, reason="حذف منشور المجلد قبل انتهاء الوقت")
            
            clean_chan = channel_id.lstrip('@')
            safe_channel = html.escape(channel_id)
            owner_user_id = db.get_channel_owner_id(channel_id)
            
            # 3. إشعار تحذيري لصاحب القناة في الخاص
            if owner_user_id:
                user_warn_text = (
                    "<blockquote>\n"
                    "⚠️ <b>تحذير رسمي — رادار كشف حذف المنشورات!</b>\n"
                    "━━━━━━━━━━━━━━━━━━\n"
                    f"📢 <b>القناة:</b> <code>{safe_channel}</code>\n"
                    f"⚠️ <b>الإنذار رقم:</b> <b>({new_strikes}/5)</b>\n"
                    "━━━━━━━━━━━━━━━━━━\n"
                    "🚨 <b>لقد تم رصد حذف منشور المجلد الموحد من قناتك قبل انتهاء فترة النشر المحددة!</b>\n\n"
                    "📌 <b>تذكير بالقوانين:</b> يجب إبقاء منشور المجلد طيلة فترة الدعم لضمان استفادة ونمو جميع القنوات المشتركة.\n"
                    "⚠️ <b>تنبيه:</b> عند الوصول إلى 5 إنذارات، سيتم نفي واستبعاد قناتك نهائياً وحظرها من المشاركة في المجلدات.\n"
                    "</blockquote>\n\n"
                    "👨‍💻 <b>إدارة المنصة:</b> @NEXUS_IMTIAZ"
                )
                try:
                    bot.send_message(owner_user_id, user_warn_text, parse_mode='HTML')
                except Exception as e:
                    logger.warning(f"تعذر إرسال الإنذار للمستخدم {owner_user_id}: {e}")

            # 4. إرسال إشعار في قروب الطلبات
            if new_strikes >= 5:
                # بلوغ 5 إنذارات -> يظهر زر نفي واستبعاد القناة
                group_alert = (
                    "<blockquote>\n"
                    "🚨 <b>إنذار أقصى — قناة بلغت الحد الأقصى من المخالفات!</b>\n"
                    "━━━━━━━━━━━━━━━━━━\n"
                    f"📢 <b>القناة:</b> <code>{safe_channel}</code>\n"
                    f"⚠️ <b>سجل المخالفات:</b> <b>5 إنذارات من أصل 5 (5/5) ❌</b>\n"
                    f"⏱️ <b>السبب:</b> <b>تكرار حذف منشورات المجلد قبل انقضاء الموعد 5 مرات.</b>\n"
                    f"📅 <b>توقيت الرصد:</b> <b>{date_str} {time_str}</b>\n"
                    "━━━━━━━━━━━━━━━━━━\n"
                    "👇 <b>يمكنك الآن نفي واستبعاد القناة وحظرها نهائياً بضغطة زر:</b>\n"
                    "</blockquote>\n\n"
                    "👨‍💻 <b>إدارة المنصة:</b> @NEXUS_IMTIAZ"
                )
                markup = types.InlineKeyboardMarkup(row_width=1)
                markup.add(
                    types.InlineKeyboardButton("⛔ نفي واستبعاد القناة وحظرها نهائياً", callback_data=f"adm_ban_strike_channel_{clean_chan}"),
                    types.InlineKeyboardButton("👁️ معاينة القناة", url=f"https://t.me/{clean_chan}"),
                    types.InlineKeyboardButton("🔄 تصفير الإنذارات والسماح لها", callback_data=f"adm_reset_strikes_{clean_chan}")
                )
            else:
                # إنذار عادي أقل من 5
                group_alert = (
                    "<blockquote>\n"
                    "🕵️‍♂️ <b>رادار كشف الغش — رصد حذف منشور مبكراً!</b>\n"
                    "━━━━━━━━━━━━━━━━━━\n"
                    f"📢 <b>القناة:</b> <code>{safe_channel}</code>\n"
                    f"⚠️ <b>الإنذار الحالي:</b> <b>({new_strikes}/5)</b>\n"
                    f"⏱️ <b>المخالفة:</b> <b>حذف منشور المجلد قبل الموعد المحدد.</b>\n"
                    f"📅 <b>التوقيت:</b> <b>{date_str} {time_str}</b>\n"
                    "━━━━━━━━━━━━━━━━━━\n"
                    "📩 <b>تم إرسال تحذير رسمي لصاحب القناة في الخاص.</b>\n"
                    "</blockquote>\n\n"
                    "👨‍💻 <b>إدارة المنصة:</b> @NEXUS_IMTIAZ"
                )
                markup = types.InlineKeyboardMarkup(row_width=2)
                markup.add(
                    types.InlineKeyboardButton("👁️ معاينة القناة", url=f"https://t.me/{clean_chan}"),
                    types.InlineKeyboardButton("💬 مراسلة المالك", callback_data=f"adm_contact_actor_{owner_user_id}" if owner_user_id else f"adm_contact_actor_{ADMIN_ID}")
                )
            
            send_notification_to_requests_group_or_admins(group_alert, markup=markup)
            logger.warning(f"🕵️‍♂️ تم رصد حذف مبكر في {channel_id} (إنذار {new_strikes}/5)")
            
        time.sleep(0.5)
    return detected_count

def run_milestones_checker_loop():
    """مراقب ذكي في الخلفية يعمل باستمرار:
    1. الحذف التلقائي للمنشورات المؤقتة في موعدها (كل 15 ثانية).
    2. رادار كشف الغش والحذف المبكر للمنشورات (كل 30 ثانية = دورتين).
    3. فحص إنجازات نمو القنوات وإرسال بطاقات التهنئة (كل 10 دقائق = 40 دورة).
    """
    time.sleep(3)  # فحص فوري بعد 3 ثوانٍ من تشغيل البوت
    counter = 0
    while True:
        try:
            # 1. فحص الحذف التلقائي للمنشورات كل 15 ثانية لدقة التوقيت
            check_and_execute_scheduled_deletions()
        except Exception as e:
            logger.error(f"خطأ في فحص الحذف التلقائي: {e}")

        try:
            # 2. رادار كشف الغش: يفحص المنشورات النشطة كل 30 ثانية (دورتين × 15 ثانية = 30 ثانية)
            if counter % 2 == 0:
                run_anti_cheat_check()
        except Exception as e:
            logger.error(f"خطأ في رادار كشف الغش: {e}")

        try:
            # 3. فحص إنجازات النمو كل 10 دقائق (40 دورة × 15 ثانية = 600 ثانية)
            if counter % 40 == 0:
                check_all_channels_milestones()
        except Exception as e:
            logger.error(f"خطأ في دورة فحص إنجازات النمو: {e}")

        counter += 1
        time.sleep(15)

def show_personal_growth_dashboard(chat_id: int, user_id: int, message_id: int = None):
    row = db.get_latest_listing_request(user_id)
    if not row:
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("🚀 تقديم طلب إدراج قناة", callback_data="u_apply"),
            types.InlineKeyboardButton("🔙 رجوع للقائمة الرئيسية", callback_data="u_main_menu")
        )
        text = (
            "<blockquote>\n"
            "📭 <b>لا توجد قناة مسجلة لحسابك حتى الآن!</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "💡 <b>قدم طلب إدراج قناتك عبر زر [ 🚀 تقديم طلب إدراج قناة ] لتبدأ المنصة في تتبع نمو قناتك وإحصائيات المشتركين من اليوم الأول!</b>\n"
            "</blockquote>\n\n"
            "👨‍💻 <b>إدارة المنصة:</b> @NEXUS_IMTIAZ"
        )
        try:
            if message_id:
                bot.edit_message_text(text, chat_id, message_id, reply_markup=markup, parse_mode='HTML')
            else:
                bot.send_message(chat_id, text, reply_markup=markup, parse_mode='HTML')
        except Exception:
            bot.send_message(chat_id, text, reply_markup=markup, parse_mode='HTML')
        return

    _id, req_user_id, _un, _fn, channel_id, channel_title, initial_members, status, reject_reason, *rest = row
    created_at = rest[0] if len(rest) > 0 else None
    last_milestone = rest[1] if len(rest) > 1 else None
    
    # فحص مباشر ومحدث لعدد الأعضاء وحالة البوت في القناة
    info, err = inspect_channel(channel_id)
    if info:
        current_members = info["members_count"]
        channel_title = info["title"] or channel_title
        bot_status = "✅ البوت مشرف وبصلاحية النشر" if info["bot_ok"] else "⚠️ البوت ليس مشرفاً (أو بدون نشر)"
        
        # التحقق من كسر حاجز نمو جديد وإرسال بطاقة التهنئة
        check_and_send_growth_celebration(
            request_id=_id,
            user_id=req_user_id,
            first_name=_fn,
            channel_id=channel_id,
            channel_title=channel_title,
            current_members=current_members,
            initial_members=initial_members or 0,
            last_milestone=last_milestone
        )
    else:
        current_members = initial_members or 0
        bot_status = "⚠️ تعذر فحص القناة حالياً"

    init_count = initial_members if initial_members is not None else 0
    curr_count = current_members if current_members is not None else 0
    diff = curr_count - init_count
    
    if init_count > 0:
        growth_rate = (diff / init_count) * 100
        rate_str = f"{growth_rate:+.1f}%"
    else:
        rate_str = "+0.0%"
        
    if diff > 0:
        growth_display = f"📈 <b>+{diff:,}</b> عضو جديد (<code>{rate_str}</code>) 🚀"
    elif diff < 0:
        growth_display = f"📉 <b>{diff:,}</b> عضو (<code>{rate_str}</code>)"
    else:
        growth_display = f"⚖️ <b>0</b> عضو جديد (<code>{rate_str}</code>) - لا تغيير بعد ⏳"

    # حساب مدة الانضمام بالبوت
    if created_at:
        try:
            elapsed_seconds = max(0, int(time.time() - int(created_at)))
            elapsed_days = elapsed_seconds // 86400
            elapsed_hours = (elapsed_seconds % 86400) // 3600
            if elapsed_days > 0:
                elapsed_str = f"منذ {elapsed_days} يوم و {elapsed_hours} ساعة"
            elif elapsed_hours > 0:
                elapsed_str = f"منذ {elapsed_hours} ساعة"
            else:
                elapsed_str = "اليوم (حديثاً)"
        except Exception:
            elapsed_str = "حديثاً"
    else:
        elapsed_str = "غير محدد"

    # حالة القناة في المجلد
    if status == "approved":
        status_display = "🟢 مقبولة ومجدولة في المجلد القادم ✅"
    elif status == "pending":
        status_display = "🟡 قيد مراجعة الإدارة حالياً ⏳"
    elif status == "rejected":
        status_display = "🔴 مرفوضة حالياً ❌"
    else:
        status_display = f"⚪ {LISTING_STATUS_AR.get(status, status)}"

    safe_channel = html.escape(channel_id)
    safe_title = html.escape(channel_title or channel_id)

    text = (
        "<blockquote>\n"
        "📈 <b>لوحة إحصائيات ونمو قناتك الشخصية</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"📢 <b>القناة:</b> <code>{safe_channel}</code> (<b>{safe_title}</b>)\n"
        f"📅 <b>تاريخ الانضمام:</b> <b>{elapsed_str}</b>\n\n"
        "👥 <b>تطور المشتركين:</b>\n"
        f"• <b>المشتركين عند التسجيل:</b> <b>{init_count:,} عضو</b>\n"
        f"• <b>المشتركين حالياً (مباشر):</b> <b>{curr_count:,} عضو</b>\n"
        f"• <b>صافي النمو المحقق:</b> {growth_display}\n\n"
        "🚀 <b>حالة القناة في الدعم:</b>\n"
        f"• <b>حالة الإدراج:</b> <b>{status_display}</b>\n"
        f"• <b>اتصال وتفاعل البوت:</b> <b>{bot_status}</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "💡 <b>نصيحة ذهبية لزيادة النمو:</b>\n"
        "<b>تأكد من ترك منشور المجلد مثبتاً في قناتك طيلة فترة النشر لضمان تحقيق أعلى نسبة تبادل ونمو للمشتركين!</b>\n"
        "</blockquote>\n\n"
        "👨‍💻 <b>إدارة المنصة:</b> @NEXUS_IMTIAZ"
    )

    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("🔄 تحديث الإحصائيات الآن", callback_data="u_growth"),
        types.InlineKeyboardButton("🔙 رجوع للقائمة الرئيسية", callback_data="u_main_menu")
    )

    try:
        if message_id:
            bot.edit_message_text(text, chat_id, message_id, reply_markup=markup, parse_mode='HTML')
        else:
            bot.send_message(chat_id, text, reply_markup=markup, parse_mode='HTML')
    except Exception:
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode='HTML')

def show_add_bot_admin_prompt(chat_id: int, request_id: int):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("➕ إضافة البوت كـ مشرف في قناتك", url=add_bot_admin_url()),
        types.InlineKeyboardButton("🔄 تحققت، أعد الفحص الآن", callback_data=f"u_recheck_{request_id}"),
        types.InlineKeyboardButton("❌ إلغاء الطلب", callback_data=f"u_cancel_{request_id}")
    )
    text = (
        "<blockquote>\n"
        "⚠️ <b>خطوة مهمة لتفعيل النشر التلقائي!</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "• 🤖 <b>يجب إضافة البوت مشرفاً (Admin) في قناتك مع تفعيل صلاحية النشر (Post Messages).</b>\n"
        "• 🔐 <b>البوت يحتاج هذه الصلاحية فقط لنشر وحذف منشور المجلد الموحد تلقائياً في الموعد المحدد.</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "👇 <b>بعد إضافة البوت، اضغط على زر '🔄 تحققت، أعد الفحص الآن':</b>\n"
        "</blockquote>\n\n"
        "👨‍💻 <b>إدارة المنصة:</b> @NEXUS_IMTIAZ"
    )
    try:
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode='HTML')
    except Exception:
        bot.send_message(chat_id, text.replace('<blockquote>\n', '').replace('</blockquote>\n', ''), reply_markup=markup, parse_mode='HTML')

def show_listing_confirm_card(chat_id: int, request_id: int):
    row = db.get_listing_request(request_id)
    if not row:
        bot.send_message(chat_id, "❌ لم يتم العثور على الطلب.")
        return
    _id, user_id, username, first_name, channel_id, channel_title, members_count, status, *rest = row
    safe_name = html.escape(first_name or "مستخدم")
    safe_uname = f"@{html.escape(username)}" if username else "بدون يوزر"
    safe_title = html.escape(channel_title or channel_id)
    safe_channel = html.escape(channel_id)
    members = f"{members_count:,}" if members_count is not None else "غير معروف"
    text = (
        "<blockquote>\n"
        "📋 <b>تأكيد بطاقة معلومات طلبك</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"• 📢 <b>معرف القناة:</b> <code>{safe_channel}</code>\n"
        f"• 🏷️ <b>اسم القناة:</b> <b>{safe_title}</b>\n"
        f"• 👥 <b>عدد المشتركين:</b> <b>{members} عضو</b>\n"
        f"• 👤 <b>مقدم الطلب:</b> <b>{safe_name}</b> (<code>{safe_uname}</code>)\n"
        f"• 🤖 <b>صلاحية البوت:</b> <b>✅ مشرف (صلاحية النشر مفعلة)</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "👇 <b>هل المعلومات صحيحة وترغب في إرسال الطلب للإدارة للمراجعة؟</b>\n"
        "</blockquote>\n\n"
        "👨‍💻 <b>إدارة المنصة:</b> @NEXUS_IMTIAZ"
    )
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("✅ تأكيد وإرسال الطلب للإدارة", callback_data=f"u_confirm_{request_id}"),
        types.InlineKeyboardButton("❌ إلغاء الطلب", callback_data=f"u_cancel_{request_id}"),
    )
    try:
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode='HTML')
    except Exception:
        bot.send_message(chat_id, text.replace('<blockquote>\n', '').replace('</blockquote>\n', ''), reply_markup=markup, parse_mode='HTML')

REJECTION_REASONS = {
    "leaks": "قناة تسريبات / محتوى مسرب مقرصن ومخالف لسياسة وقوانين المنصة.",
    "multi": "المشاركة في مجلدات دعم أخرى بالتزامن مخالف لشرط الحصرية.",
    "fake": "القناة تحتوي على أعضاء وهميين / رشق بدون تفاعل حقيقي.",
    "content": "محتوى القناة غير مناسب أو مخالف لقوانين وشروط الدعم.",
    "weak": "القناة ضعيفة / تفاعل ضعيف أو عدد المشتركين غير كافٍ.",
    "notadmin": "البوت ليس مشرفاً (Admin) في القناة أو لا يملك صلاحية النشر.",
}

def make_request_card_markup(request_id: int, channel_id: str) -> types.InlineKeyboardMarkup:
    channel_clean = channel_id.lstrip('@')
    channel_url = f"https://t.me/{channel_clean}"
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("✅ قبول القناة", callback_data=f"adm_approve_{request_id}"),
        types.InlineKeyboardButton("❌ رفض الطلب", callback_data=f"adm_rej_menu_{request_id}")
    )
    markup.row(
        types.InlineKeyboardButton("💬 مراسلة صاحب القناة", callback_data=f"adm_contact_{request_id}"),
        types.InlineKeyboardButton("👁️ معاينة القناة", url=channel_url)
    )
    markup.row(
        types.InlineKeyboardButton("🚫 حظر المستخدم", callback_data=f"adm_ban_user_{request_id}"),
        types.InlineKeyboardButton("🚫 حظر القناة", callback_data=f"adm_ban_chan_{request_id}")
    )
    return markup

def send_safe_admin_message(chat_id: int, html_text: str, markup=None, thread_id: int = None):
    """إرسال رسالة بتنسيق HTML مع حماية تلقائية fallback لنص عادي في حال أي خطأ"""
    try:
        if thread_id:
            return bot.send_message(chat_id, html_text, reply_markup=markup, parse_mode='HTML', message_thread_id=thread_id)
        return bot.send_message(chat_id, html_text, reply_markup=markup, parse_mode='HTML')
    except Exception as e:
        logger.warning(f"فشل إرسال HTML إلى {chat_id} ({e})، جاري المحاولة بنص عادي آمن...")
        clean_text = re.sub(r'<[^>]+>', '', html_text)
        try:
            if thread_id:
                return bot.send_message(chat_id, clean_text, reply_markup=markup, parse_mode=None, message_thread_id=thread_id)
            return bot.send_message(chat_id, clean_text, reply_markup=markup, parse_mode=None)
        except Exception as e2:
            logger.error(f"فشل الإرسال النهائي إلى {chat_id}: {e2}")
            return None

def send_notification_to_requests_group_or_admins(html_text: str, markup=None) -> bool:
    """إرسال الإشعار لقروب الطلبات المخصص، وفي حال عدم وجوده يتم الإرسال في الخاص لجميع المشرفين"""
    req_group_id = db.get_setting("requests_group_id")
    req_thread_id = db.get_setting("requests_thread_id")
    sent_to_group = False
    
    if req_group_id:
        try:
            group_id_int = int(req_group_id)
            thread_id_int = int(req_thread_id) if req_thread_id else None
            
            if thread_id_int:
                msg = send_safe_admin_message(group_id_int, html_text, markup=markup, thread_id=thread_id_int)
                if msg:
                    sent_to_group = True
            
            if not sent_to_group:
                msg = send_safe_admin_message(group_id_int, html_text, markup=markup)
                if msg:
                    sent_to_group = True
        except Exception as e:
            logger.error(f"خطأ أثناء الإرسال لقروب الطلبات: {e}")

    if sent_to_group:
        return True

    # إرسال للمشرفين في الخاص إن لم يتم الإرسال للقروب
    admin_ids = db.get_admin_user_ids()
    for admin_id in admin_ids:
        try:
            send_safe_admin_message(admin_id, html_text, markup=markup)
        except Exception as e:
            logger.warning(f"فشل إرسال الإشعار للمشرف {admin_id}: {e}")
    return True

def send_safe_admin_photo(chat_id: int, photo_file_id: str, html_caption: str, markup=None, thread_id: int = None):
    """إرسال صورة بتنسيق HTML مع حماية تلقائية ضد تجاوز حدود التيليجرام أو أخطاء التنسيق"""
    try:
        if len(html_caption) > 1000:
            if thread_id:
                bot.send_photo(chat_id, photo_file_id, message_thread_id=thread_id)
                return bot.send_message(chat_id, html_caption, reply_markup=markup, parse_mode='HTML', message_thread_id=thread_id)
            else:
                bot.send_photo(chat_id, photo_file_id)
                return bot.send_message(chat_id, html_caption, reply_markup=markup, parse_mode='HTML')
        else:
            if thread_id:
                return bot.send_photo(chat_id, photo_file_id, caption=html_caption, reply_markup=markup, parse_mode='HTML', message_thread_id=thread_id)
            return bot.send_photo(chat_id, photo_file_id, caption=html_caption, reply_markup=markup, parse_mode='HTML')
    except Exception as e:
        logger.warning(f"فشل إرسال صورة HTML إلى {chat_id} ({e})، جاري المحاولة بنص عادي...")
        clean_cap = re.sub(r'<[^>]+>', '', html_caption)
        try:
            if len(clean_cap) > 1000:
                if thread_id:
                    bot.send_photo(chat_id, photo_file_id, message_thread_id=thread_id)
                    return bot.send_message(chat_id, clean_cap, reply_markup=markup, parse_mode=None, message_thread_id=thread_id)
                else:
                    bot.send_photo(chat_id, photo_file_id)
                    return bot.send_message(chat_id, clean_cap, reply_markup=markup, parse_mode=None)
            else:
                if thread_id:
                    return bot.send_photo(chat_id, photo_file_id, caption=clean_cap, reply_markup=markup, parse_mode=None, message_thread_id=thread_id)
                return bot.send_photo(chat_id, photo_file_id, caption=clean_cap, reply_markup=markup, parse_mode=None)
        except Exception as e2:
            logger.error(f"فشل إرسال الصورة النهائي إلى {chat_id}: {e2}")
            return None

def send_support_ticket_to_requests_group_or_admins(message, html_text: str, markup=None) -> bool:
    """إرسال تذكرة الدعم (صورة / وسائط / نص) كاملة لقروب الطلبات أو المشرفين"""
    req_group_id = db.get_setting("requests_group_id")
    req_thread_id = db.get_setting("requests_thread_id")
    
    photo_id = message.photo[-1].file_id if message.photo else None
    
    targets = []
    if req_group_id:
        try:
            targets.append((int(req_group_id), int(req_thread_id) if req_thread_id else None))
        except Exception:
            pass
            
    if not targets:
        admin_ids = db.get_admin_user_ids()
        for aid in admin_ids:
            targets.append((aid, None))
            
    sent_any = False
    for chat_id, thread_id in targets:
        try:
            if photo_id:
                res = send_safe_admin_photo(chat_id, photo_id, html_text, markup=markup, thread_id=thread_id)
            elif message.document:
                res = bot.send_document(chat_id, message.document.file_id, caption=html_text if len(html_text) <= 1000 else None, reply_markup=markup if len(html_text) <= 1000 else None, parse_mode='HTML', message_thread_id=thread_id)
                if len(html_text) > 1000:
                    send_safe_admin_message(chat_id, html_text, markup=markup, thread_id=thread_id)
            elif message.video:
                res = bot.send_video(chat_id, message.video.file_id, caption=html_text if len(html_text) <= 1000 else None, reply_markup=markup if len(html_text) <= 1000 else None, parse_mode='HTML', message_thread_id=thread_id)
                if len(html_text) > 1000:
                    send_safe_admin_message(chat_id, html_text, markup=markup, thread_id=thread_id)
            elif message.voice:
                res = bot.send_voice(chat_id, message.voice.file_id, caption=html_text if len(html_text) <= 1000 else None, reply_markup=markup if len(html_text) <= 1000 else None, parse_mode='HTML', message_thread_id=thread_id)
                if len(html_text) > 1000:
                    send_safe_admin_message(chat_id, html_text, markup=markup, thread_id=thread_id)
            else:
                res = send_safe_admin_message(chat_id, html_text, markup=markup, thread_id=thread_id)
                
            if res:
                sent_any = True
        except Exception as e:
            logger.error(f"خطأ أثناء إرسال تذكرة الدعم إلى {chat_id}: {e}")
            send_safe_admin_message(chat_id, html_text, markup=markup, thread_id=thread_id)
            
    return sent_any

def notify_admins_listing_request(request_id: int):
    row = db.get_listing_request(request_id)
    if not row:
        return
    _id, user_id, username, first_name, channel_id, channel_title, members_count, status, _reason, *rest = row
    safe_name = html.escape(str(first_name or 'مستخدم'))
    safe_uname = f"@{html.escape(str(username))}" if username else "بدون يوزر"
    safe_title = html.escape(str(channel_title or channel_id))
    safe_channel = html.escape(str(channel_id))
    members = f"{members_count:,}" if members_count is not None else "غير معروف"
    
    text = (
        "<blockquote>\n"
        "📥 <b>طلب إدراج قناة جديد في الدعم!</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>مقدم الطلب:</b> <b>{safe_name}</b> (<code>{safe_uname}</code>)\n"
        f"🆔 <b>آيدي المستخدم:</b> <code>{user_id}</code>\n\n"
        "📢 <b>معلومات القناة:</b>\n"
        f"• 🏷️ <b>الاسم:</b> <b>{safe_title}</b>\n"
        f"• 🔗 <b>المعرف:</b> <code>{safe_channel}</code>\n"
        f"• 👥 <b>عدد المشتركين:</b> <b>{members} عضو</b>\n"
        "• 🤖 <b>صلاحية البوت فيها:</b> <b>✅ مشرف (صلاحية النشر مفعلة)</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "👇 <b>اتخذ قرارك بضغطة زر:</b>\n"
        "</blockquote>"
    )
    markup = make_request_card_markup(request_id, channel_id)
    send_notification_to_requests_group_or_admins(text, markup=markup)

def start_listing_apply(chat_id: int):
    if db.is_blacklisted(user_id=chat_id):
        text = (
            "<blockquote>\n"
            "🚫 <b>أنت محظور من تقديم طلبات إدراج القنوات في البوت لمخالفة القوانين والشروط.</b>\n"
            "</blockquote>\n\n"
            "👨‍💻 <b>إدارة المنصة:</b> @NEXUS_IMTIAZ"
        )
        bot.send_message(chat_id, text, parse_mode='HTML')
        return
    text = (
        "<blockquote>\n"
        "📢 <b>تقديم طلب إدراج قناة جديدة في الدعم</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "✍️ <b>أرسل الآن رابط قناتك أو معرفها العام:</b>\n"
        "• <b>مثال بالمعرف:</b> <code>@my_channel</code>\n"
        "• <b>مثال بالرابط:</b> <code>https://t.me/my_channel</code>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "💡 <b>تأكد أن القناة عامة ومحتواها تعليمي مفيد!</b>\n"
        "</blockquote>\n\n"
        "👨‍💻 <b>إدارة المنصة:</b> @NEXUS_IMTIAZ"
    )
    msg = bot.send_message(chat_id, text, parse_mode='HTML')
    clear_chat_step_handlers(chat_id)
    bot.register_next_step_handler(msg, process_listing_channel)

def process_listing_channel(message):
    try:
        if not message.text:
            bot.send_message(message.chat.id, "❌ <b>يرجى إرسال رابط أو معرف القناة كنص.</b>", parse_mode='HTML')
            return
        if message.text.startswith("/"):
            return

        if message.text.strip().lower() in ["الغاء", "إلغاء", "cancel", "/cancel"]:
            bot.send_message(message.chat.id, "❌ تم إلغاء تقديم الطلب.")
            return

        if db.is_blacklisted(user_id=message.from_user.id):
            bot.send_message(message.chat.id, "🚫 <b>أنت محظور من تقديم طلبات إدراج القنوات في البوت لمخالفة القوانين.</b>", parse_mode='HTML')
            return

        channel_ref = parse_channel_ref(message.text)
        if not channel_ref or not re.match(r'^@[a-zA-Z0-9][a-zA-Z0-9_-]{0,31}$', channel_ref):
            bot.send_message(
                message.chat.id,
                "<blockquote>\n❌ <b>المعرف غير صحيح!</b>\n\nأرسل مثلاً: <code>@my_channel</code> أو <code>https://t.me/my_channel</code>\n</blockquote>",
                parse_mode='HTML'
            )
            return

        if db.is_blacklisted(channel_id=channel_ref):
            bot.send_message(message.chat.id, "🚫 <b>هذه القناة محظورة من الإدراج في قائمة الدعم لمخالفتها الشروط.</b>", parse_mode='HTML')
            return

        info, err = inspect_channel(channel_ref)
        if err:
            bot.send_message(message.chat.id, f"<blockquote>\n❌ <b>{err}</b>\n</blockquote>", parse_mode='HTML')
            return

        request_id = db.save_listing_request(
            message.from_user.id,
            message.from_user.username,
            message.from_user.first_name,
            info["username"],
            info["title"],
            info["members_count"],
            "draft",
        )
        if not request_id:
            bot.send_message(message.chat.id, "❌ <b>حدث خطأ في حفظ الطلب، يرجى المحاولة مرة أخرى.</b>", parse_mode='HTML')
            return

        if not info["bot_ok"]:
            show_add_bot_admin_prompt(message.chat.id, request_id)
            return

        show_listing_confirm_card(message.chat.id, request_id)
    except Exception as e:
        logger.error(f"خطأ في process_listing_channel: {e}", exc_info=True)
        bot.send_message(message.chat.id, "❌ <b>حدث خطأ أثناء معالجة القناة. يرجى المحاولة مجدداً.</b>", parse_mode='HTML')

def handle_user_callback(call):
    try:
        bot.answer_callback_query(call.id)
    except Exception:
        pass

    data = call.data
    chat_id = call.message.chat.id
    user_id = call.from_user.id

    if data == "u_apply":
        start_listing_apply(chat_id)
        return

    if data == "u_status":
        row = db.get_latest_listing_request(user_id)
        if not row:
            text = (
                "<blockquote>\n"
                "📭 <b>ليس لديك أي طلب مسجل حتى الآن!</b>\n"
                "━━━━━━━━━━━━━━━━━━\n"
                "💡 <b>اضغط على زر '🚀 تقديم طلب إدراج قناة' لبدء إرسال قناتك ومتابعة حالتها.</b>\n"
                "</blockquote>\n\n"
                "👨‍💻 <b>إدارة المنصة:</b> @NEXUS_IMTIAZ"
            )
            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(
                types.InlineKeyboardButton("🚀 تقديم طلب إدراج قناة", callback_data="u_apply"),
                types.InlineKeyboardButton("🔙 رجوع للقائمة الرئيسية", callback_data="u_main_menu")
            )
            try:
                bot.edit_message_text(text, chat_id, call.message.message_id, reply_markup=markup, parse_mode='HTML')
            except Exception:
                bot.send_message(chat_id, text, reply_markup=markup, parse_mode='HTML')
            return

        _id, _uid, _un, _fn, channel_id, channel_title, members_count, status, reject_reason, *rest = row
        members = f"{members_count:,}" if members_count is not None else "غير معروف"
        safe_channel = html.escape(channel_id)
        safe_title = html.escape(channel_title or channel_id)
        
        status_card = (
            "<blockquote>\n"
            f"📋 <b>بطاقة متابعة حالة طلبك #{_id}</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            f"• 📢 <b>معرف القناة:</b> <code>{safe_channel}</code>\n"
            f"• 🏷️ <b>اسم القناة:</b> <b>{safe_title}</b>\n"
            f"• 👥 <b>عدد المشتركين:</b> <b>{members} عضو</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
        )
        
        if status == "pending":
            status_card += (
                "🟡 <b>الحالة:</b> <b>قيد المراجعة والتدقيق من طرف الإدارة ⏳</b>\n\n"
                "💡 <b>سيصلك إشعار فوري وتلقائي هنا بمجرد مراجعة طلبك وقبوله.</b>\n"
            )
        elif status == "approved":
            status_card += (
                "🟢 <b>الحالة:</b> <b>مقبول ومجدول للمجلد القادم بنجاح ✅</b>\n\n"
                "🚀 <b>سيقوم البوت بنشر المنشور الموحد في قناتك تلقائياً في الموعد المحدد.</b>\n"
            )
        elif status == "rejected":
            status_card += "🔴 <b>الحالة:</b> <b>مرفوض ❌</b>\n\n"
            if reject_reason:
                safe_reason = html.escape(reject_reason)
                status_card += f"📝 <b>سبب الرفض:</b> <b>{safe_reason}</b>\n\n"
            status_card += "💡 <b>يمكنك تصحيح المشكلة وإعادة تقديم طلبك في أي وقت!</b>\n"
        else:
            status_card += f"⚪ <b>الحالة:</b> <b>{LISTING_STATUS_AR.get(status, status)}</b>\n"
            
        status_card += (
            "</blockquote>\n\n"
            "👨‍💻 <b>إدارة المنصة:</b> @NEXUS_IMTIAZ"
        )
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("🔄 تحديث الحالة", callback_data="u_status"),
            types.InlineKeyboardButton("🔙 رجوع للقائمة الرئيسية", callback_data="u_main_menu")
        )
        try:
            bot.edit_message_text(status_card, chat_id, call.message.message_id, reply_markup=markup, parse_mode='HTML')
        except Exception:
            bot.send_message(chat_id, status_card, reply_markup=markup, parse_mode='HTML')
        return

    if data == "u_growth":
        show_personal_growth_dashboard(chat_id, user_id, message_id=call.message.message_id)
        return

    if data == "u_main_menu":
        show_user_menu(chat_id, message_id=call.message.message_id)
        return

    if data == "u_rules":
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("🚀 تقديم طلب إدراج قناة", callback_data="u_apply"),
            types.InlineKeyboardButton("🔙 رجوع للقائمة الرئيسية", callback_data="u_main_menu")
        )
        try:
            bot.edit_message_text(USER_RULES_TEXT, chat_id, call.message.message_id, reply_markup=markup, parse_mode="HTML")
        except Exception:
            bot.send_message(chat_id, USER_RULES_TEXT, reply_markup=markup, parse_mode="HTML")
        return

    if data == "u_support":
        if db.is_blacklisted(user_id=user_id):
            text = (
                "<blockquote>\n"
                "🚫 <b>أنت محظور من استخدام البوت ومراسلة الإدارة لمخالفة القوانين والشروط.</b>\n"
                "</blockquote>\n\n"
                "👨‍💻 <b>إدارة المنصة:</b> @NEXUS_IMTIAZ"
            )
            try:
                bot.edit_message_text(text, chat_id, call.message.message_id, parse_mode='HTML')
            except Exception:
                bot.send_message(chat_id, text, parse_mode='HTML')
            return

        text = (
            "<blockquote>\n"
            "💬 <b>قسم الدعم الفني وخدمة أصحاب القنوات 👨‍💻</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "✍️ <b>أرسل الآن رسالتك أو استفسارك أو مشكلتك في رسالة واحدة:</b>\n\n"
            "• يمكنك كتابة أي سؤال أو انشغال أو اقتراح أو مشكلة تواجهك.\n"
            "• يمكنك أيضاً إرفاق صورة توضيحية مع رسالتك.\n"
            "• سيتم إيصال رسالتك مباشرة لقروب الإدارة وسيصلك الرد هنا فوراً.\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "👇 <b>أو اضغط رجوع إذا لم تكن ترغب في إرسال شيء:</b>\n"
            "</blockquote>\n\n"
            "👨‍💻 <b>إدارة المنصة:</b> @NEXUS_IMTIAZ"
        )
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("🔙 إلغاء والعودة للقائمة", callback_data="u_main_menu"))
        
        try:
            msg = bot.edit_message_text(text, chat_id, call.message.message_id, reply_markup=markup, parse_mode='HTML')
        except Exception:
            msg = bot.send_message(chat_id, text, reply_markup=markup, parse_mode='HTML')
            
        clear_chat_step_handlers(chat_id)
        bot.register_next_step_handler(msg, process_user_support_message)
        return

    if data.startswith("u_recheck_"):
        request_id = int(data.replace("u_recheck_", "", 1))
        row = db.get_listing_request(request_id)
        if not row or row[1] != user_id:
            bot.send_message(chat_id, "❌ <b>ما قدرتش نتحقق من هاد الطلب.</b>", parse_mode='HTML')
            return
        info, err = inspect_channel(row[4])
        if err:
            bot.send_message(chat_id, f"<blockquote>\n❌ <b>{err}</b>\n</blockquote>", parse_mode='HTML')
            show_add_bot_admin_prompt(chat_id, request_id)
            return
        db.execute_query(
            '''UPDATE listing_requests SET channel_id=?, channel_title=?, members_count=?,
               updated_at=strftime('%s', 'now') WHERE id=? AND user_id=?''',
            (info["username"], info["title"], info["members_count"], request_id, user_id)
        )
        if not info["bot_ok"]:
            bot.send_message(
                chat_id,
                "<blockquote>\n⚠️ <b>البوت مازال مش مشرف (أو بدون صلاحية النشر). أضف البوت مشرفاً ثم اضغط إعادة الفحص.</b>\n</blockquote>",
                parse_mode='HTML'
            )
            show_add_bot_admin_prompt(chat_id, request_id)
            return
        show_listing_confirm_card(chat_id, request_id)
        return

    if data.startswith("u_confirm_"):
        request_id = int(data.replace("u_confirm_", "", 1))
        row = db.get_listing_request(request_id)
        if not row or row[1] != user_id:
            bot.send_message(chat_id, "❌ <b>تعذر تأكيد هذا الطلب.</b>", parse_mode='HTML')
            return
        if row[7] == "pending":
            bot.send_message(chat_id, "⏳ <b>طلبك مرسول مسبقاً وهو قيد المراجعة حالياً.</b>", parse_mode='HTML')
            return
        if not db.update_listing_status(request_id, "pending", user_id):
            bot.send_message(chat_id, "❌ <b>حدث خطأ أثناء إرسال الطلب، يرجى المحاولة لاحقاً.</b>", parse_mode='HTML')
            return
        try:
            bot.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
        except Exception:
            pass
        confirm_text = (
            "<blockquote>\n"
            "🎉 <b>تم إرسال طلبك بنجاح للإدارة! 🚀</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "• 🔍 <b>الطلب الآن قيد المراجعة والتدقيق من طرف فريق الإدارة.</b>\n"
            "• 🔔 <b>سوف يصلك إشعار فوري وتلقائي هنا فور قبول قناتك وجدولتها في المجلد القادم!</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "</blockquote>\n\n"
            "👨‍💻 <b>إدارة المنصة:</b> @NEXUS_IMTIAZ"
        )
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("📋 متابعة حالة طلبي", callback_data="u_status"),
            types.InlineKeyboardButton("🔙 رجوع للقائمة الرئيسية", callback_data="u_main_menu")
        )
        bot.send_message(chat_id, confirm_text, reply_markup=markup, parse_mode='HTML')
        notify_admins_listing_request(request_id)
        return

    if data.startswith("u_cancel_"):
        request_id = int(data.replace("u_cancel_", "", 1))
        db.update_listing_status(request_id, "cancelled", user_id)
        try:
            bot.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
        except Exception:
            pass
        cancel_text = (
            "<blockquote>\n"
            "❌ <b>تم إلغاء الطلب بنجاح.</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "💡 <b>يمكنك تقديم طلب إدراج جديد في أي وقت تشاء!</b>\n"
            "</blockquote>\n\n"
            "👨‍💻 <b>إدارة المنصة:</b> @NEXUS_IMTIAZ"
        )
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("🔙 رجوع للقائمة الرئيسية", callback_data="u_main_menu"))
        bot.send_message(chat_id, cancel_text, reply_markup=markup, parse_mode='HTML')
        return

def process_user_support_message(message):
    try:
        user_id = message.from_user.id
        username = message.from_user.username
        first_name = message.from_user.first_name
        
        if message.text and message.text.strip().lower() in ["الغاء", "إلغاء", "cancel", "/cancel"]:
            bot.send_message(message.chat.id, "❌ تم إلغاء مراسلة الدعم الفني.")
            return

        if message.text and message.text.startswith("/"):
            return
            
        if db.is_blacklisted(user_id=user_id):
            bot.send_message(message.chat.id, "🚫 أنت محظور من مراسلة الإدارة.", parse_mode='HTML')
            return

        if message.photo:
            user_content = message.caption or "📷 [صورة مرفقة بدون نص]"
        elif message.document:
            user_content = message.caption or "📄 [ملف / مستند مرفق]"
        elif message.video:
            user_content = message.caption or "🎥 [مقطع فيديو مرفق]"
        elif message.voice:
            user_content = message.caption or "🎙️ [تسجيل صوتي مرفق]"
        else:
            user_content = message.text or "محتوى فارغ"

        safe_name = html.escape(first_name or "مستخدم")
        safe_uname = f"@{html.escape(username)}" if username else "بدون يوزر"
        safe_content = html.escape(user_content)
        
        now = datetime.now()
        day_name = DAYS_AR.get(now.weekday(), "")
        date_str = f"{day_name} {now.strftime('%Y-%m-%d')}"
        time_str = now.strftime("%H:%M:%S")

        # 1. إشعار للمستخدم بتأكيد وصول الرسالة
        confirm_text = (
            "<blockquote>\n"
            "✅ <b>تم إرسال رسالتك بنجاح إلى فريق الإدارة! 🚀</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "• 📩 <b>وصلت رسالتك لفريق الدعم، وسيتم الرد عليك هنا في الخاص قريباً.</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "</blockquote>\n\n"
            "👨‍💻 <b>إدارة المنصة:</b> @NEXUS_IMTIAZ"
        )
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("🔙 رجوع للقائمة الرئيسية", callback_data="u_main_menu"))
        bot.send_message(message.chat.id, confirm_text, reply_markup=markup, parse_mode='HTML')

        # 2. تجهيز الإشعار لقروب الطلبات / المشرفين
        ticket_text = (
            "<blockquote>\n"
            "📨 <b>رسالة دعم / انشغال جديدة من مستخدم!</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            f"👤 <b>المرسل:</b> <b>{safe_name}</b> (<code>{safe_uname}</code>)\n"
            f"🆔 <b>آيدي المستخدم:</b> <code>{user_id}</code>\n"
            f"📅 <b>التوقيت:</b> <b>{date_str} {time_str}</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            f"📝 <b>نص الرسالة:</b>\n\n<b>{safe_content}</b>\n"
            "</blockquote>\n\n"
            "👇 <b>الإجراءات المتاحة للرد أو الإدارة:</b>"
        )
        
        ticket_markup = types.InlineKeyboardMarkup(row_width=2)
        ticket_markup.add(
            types.InlineKeyboardButton("💬 الرد على المستخدم", callback_data=f"adm_reply_support_{user_id}"),
            types.InlineKeyboardButton("🚫 حظر المستخدم", callback_data=f"adm_ban_actor_{user_id}")
        )
        
        send_support_ticket_to_requests_group_or_admins(message, ticket_text, markup=ticket_markup)
        logger.info(f"📨 تم استلام رسالة دعم من user_id: {user_id}")
    except Exception as e:
        logger.error(f"خطأ في معالجة رسالة الدعم: {e}")

def delete_message_from_channel(channel_id: str, message_id: int) -> bool:
    try:
        bot.delete_message(channel_id, message_id)
        return True
    except Exception as e:
        logger.error(f"فشل في حذف الرسالة من {channel_id}: {e}")
        return False

@bot.my_chat_member_handler()
def handle_bot_membership_change(update: types.ChatMemberUpdated):
    """
    مراقبة ذكية لكافة تحركات البوت في القنوات:
    1. إضافة البوت مباشرة لقناة بدون طلب إدراج مسبق.
    2. ترقية البوت لمشرف أو تنزيل رتبته.
    3. طرد أو حذف البوت نهائياً من القناة.
    ترسل جميع الإشعارات فورياً لقروب الطلبات المخصص أو في الخاص للمشرفين.
    """
    try:
        chat = update.chat
        old_status = update.old_chat_member.status
        new_status = update.new_chat_member.status

        # نتجاهل التغييرات خارج القنوات
        if chat.type != "channel":
            return

        from datetime import datetime
        now = datetime.now()
        day_name = DAYS_AR.get(now.weekday(), "")
        date_str = f"{day_name} {now.strftime('%Y-%m-%d')}"
        time_str = now.strftime("%H:%M:%S")

        channel_title = html.escape(chat.title or "بدون اسم")
        channel_username = f"@{chat.username}" if chat.username else f"ID: {chat.id}"
        safe_username = html.escape(channel_username)
        channel_clean = chat.username.lstrip('@') if chat.username else str(chat.id)

        actor = update.from_user
        actor_id = actor.id if actor else None
        actor_name = html.escape(actor.first_name or "مستخدم") if actor else "غير معروف"
        actor_uname = f"@{html.escape(actor.username)}" if (actor and actor.username) else "بدون يوزر"

        # محاولة جلب عدد أعضاء القناة
        try:
            m_count = bot.get_chat_member_count(chat.id)
            members_str = f"{m_count:,} عضو"
        except Exception:
            members_str = "غير متاح"

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # الحالة 1: تم طرد / حذف البوت نهائياً من القناة
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        if old_status in ("administrator", "member") and new_status in ("kicked", "left"):
            alert_text = (
                "<blockquote>\n"
                "🚨 <b>تنبيه عاجل — طرد / حذف البوت من قناة!</b>\n"
                "━━━━━━━━━━━━━━━━━━\n"
                f"📢 <b>القناة:</b> <b>{channel_title}</b> (<code>{safe_username}</code>)\n"
                f"🆔 <b>آيدي القناة:</b> <code>{chat.id}</code>\n"
                f"👥 <b>عدد المشتركين:</b> <b>{members_str}</b>\n"
                "━━━━━━━━━━━━━━━━━━\n"
                f"👤 <b>تم الإجراء بواسطة:</b> <b>{actor_name}</b> (<code>{actor_uname}</code>)\n"
                f"🆔 <b>آيدي الفاعل:</b> <code>{actor_id or 'غير معروف'}</code>\n"
                "━━━━━━━━━━━━━━━━━━\n"
                f"🔔 <b>الحدث:</b> 🚫 <b>تم طرد أو إزالة البوت نهائياً من القناة</b>\n"
                f"📅 <b>اليوم والتاريخ:</b> <b>{date_str}</b>\n"
                f"🕐 <b>الوقت:</b> <b>{time_str}</b>\n"
                "━━━━━━━━━━━━━━━━━━\n"
                "</blockquote>\n\n"
                "👨‍💻 <b>إدارة المنصة:</b> @NEXUS_IMTIAZ"
            )
            markup = types.InlineKeyboardMarkup(row_width=2)
            btns = []
            if chat.username:
                btns.append(types.InlineKeyboardButton("👁️ معاينة القناة", url=f"https://t.me/{channel_clean}"))
                btns.append(types.InlineKeyboardButton("🚫 حظر القناة", callback_data=f"adm_ban_chan_ref_{safe_username}"))
            if actor_id:
                btns.append(types.InlineKeyboardButton("💬 مراسلة الفاعل", callback_data=f"adm_contact_actor_{actor_id}"))
                btns.append(types.InlineKeyboardButton("🚫 حظر المستخدم", callback_data=f"adm_ban_actor_{actor_id}"))
            markup.add(*btns)

            send_notification_to_requests_group_or_admins(alert_text, markup=markup if btns else None)
            logger.warning(f"🚨 تم طرد البوت من {channel_username} بواسطة {actor_uname} ({actor_id})")
            return

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # الحالة 2: تم تنزيل البوت من رتبة المشرف
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        elif old_status == "administrator" and new_status == "member":
            alert_text = (
                "<blockquote>\n"
                "⚠️ <b>تنبيه — تنزيل البوت من المشرفين (Demoted)!</b>\n"
                "━━━━━━━━━━━━━━━━━━\n"
                f"📢 <b>القناة:</b> <b>{channel_title}</b> (<code>{safe_username}</code>)\n"
                f"🆔 <b>آيدي القناة:</b> <code>{chat.id}</code>\n"
                f"👥 <b>عدد المشتركين:</b> <b>{members_str}</b>\n"
                "━━━━━━━━━━━━━━━━━━\n"
                f"👤 <b>تم التنزيل بواسطة:</b> <b>{actor_name}</b> (<code>{actor_uname}</code>)\n"
                f"🆔 <b>آيدي الفاعل:</b> <code>{actor_id or 'غير معروف'}</code>\n"
                "━━━━━━━━━━━━━━━━━━\n"
                f"🔔 <b>الحدث:</b> ⚠️ <b>تم سحب صلاحيات الإدارة من البوت وأصبح عضواً عادياً</b>\n"
                f"📅 <b>اليوم والتاريخ:</b> <b>{date_str}</b>\n"
                f"🕐 <b>الوقت:</b> <b>{time_str}</b>\n"
                "━━━━━━━━━━━━━━━━━━\n"
                "</blockquote>\n\n"
                "👨‍💻 <b>إدارة المنصة:</b> @NEXUS_IMTIAZ"
            )
            markup = types.InlineKeyboardMarkup(row_width=2)
            btns = []
            if chat.username:
                btns.append(types.InlineKeyboardButton("👁️ معاينة القناة", url=f"https://t.me/{channel_clean}"))
                btns.append(types.InlineKeyboardButton("🚫 حظر القناة", callback_data=f"adm_ban_chan_ref_{safe_username}"))
            if actor_id:
                btns.append(types.InlineKeyboardButton("💬 مراسلة الفاعل", callback_data=f"adm_contact_actor_{actor_id}"))
                btns.append(types.InlineKeyboardButton("🚫 حظر المستخدم", callback_data=f"adm_ban_actor_{actor_id}"))
            markup.add(*btns)

            send_notification_to_requests_group_or_admins(alert_text, markup=markup if btns else None)
            logger.warning(f"⚠️ تم تنزيل البوت من {channel_username} بواسطة {actor_uname} ({actor_id})")
            return

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # الحالة 3: إضافة البوت لقناة جديدة أو ترقيته مشرفاً
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        elif (new_status in ("administrator", "member") and old_status in ("left", "kicked", "restricted", None)) or (old_status == "member" and new_status == "administrator"):
            # فحص إن كانت القناة قد قدمت طلباً في البوت حديثاً
            ch_lookup = f"@{chat.username}" if chat.username else str(chat.id)
            recent_req = None
            if actor_id:
                recent_req = db.execute_query(
                    "SELECT id, status, created_at FROM listing_requests WHERE user_id=? AND (channel_id=? OR channel_id=?) ORDER BY id DESC LIMIT 1",
                    (actor_id, ch_lookup, f"@{chat.username}" if chat.username else ch_lookup),
                    fetch=True
                )

            # صلاحيات البوت في القناة
            if new_status == "administrator":
                new_adm = update.new_chat_member
                can_post = getattr(new_adm, 'can_post_messages', False)
                can_edit = getattr(new_adm, 'can_edit_messages', False)
                can_del = getattr(new_adm, 'can_delete_messages', False)
                perms = []
                if can_post: perms.append("النشر ✅")
                if can_edit: perms.append("التعديل ✅")
                if can_del: perms.append("الحذف ✅")
                perms_str = "، ".join(perms) if perms else "مشرف بدون صلاحيات نشر"
                bot_role_str = f"👑 مشرف ({perms_str})"
            else:
                bot_role_str = "👤 عضو عادي (بدون رتبة إدارة)"

            # إذا كان المستخدم في خضم تقديم الطلب (draft)، فالبوت سيكمل المسار الطبيعي للطلب
            is_in_active_draft = False
            if recent_req and recent_req[0]:
                r_id, r_status, r_created_at = recent_req[0]
                if r_status == "draft" and (time.time() - (r_created_at or 0) < 600):
                    is_in_active_draft = True

            # إذا لم يكن هناك طلب مسجل أو إضافة مباشرة بدون استخدام البوت:
            if not is_in_active_draft:
                alert_text = (
                    "<blockquote>\n"
                    "📥 <b>إشعار — إضافة البوت لقناة جديدة!</b>\n"
                    "━━━━━━━━━━━━━━━━━━\n"
                    f"📢 <b>القناة:</b> <b>{channel_title}</b> (<code>{safe_username}</code>)\n"
                    f"🆔 <b>آيدي القناة:</b> <code>{chat.id}</code>\n"
                    f"👥 <b>عدد المشتركين:</b> <b>{members_str}</b>\n"
                    f"🤖 <b>رتبة البوت:</b> <b>{bot_role_str}</b>\n"
                    "━━━━━━━━━━━━━━━━━━\n"
                    f"👤 <b>أضيف بواسطة:</b> <b>{actor_name}</b> (<code>{actor_uname}</code>)\n"
                    f"🆔 <b>آيدي الفاعل:</b> <code>{actor_id or 'غير معروف'}</code>\n"
                    "━━━━━━━━━━━━━━━━━━\n"
                    "📌 <b>ملاحظة:</b> <b>تمت إضافة البوت مباشرة في القناة بدون تقديم طلب إدراج مسبق.</b>\n"
                    f"📅 <b>اليوم والتاريخ:</b> <b>{date_str}</b>\n"
                    f"🕐 <b>الوقت:</b> <b>{time_str}</b>\n"
                    "━━━━━━━━━━━━━━━━━━\n"
                    "</blockquote>\n\n"
                    "👨‍💻 <b>إدارة المنصة:</b> @NEXUS_IMTIAZ"
                )
                markup = types.InlineKeyboardMarkup(row_width=2)
                btns = []
                if chat.username:
                    btns.append(types.InlineKeyboardButton("👁️ معاينة القناة", url=f"https://t.me/{channel_clean}"))
                    btns.append(types.InlineKeyboardButton("➕ إدراج بالمجلد مباشرة", callback_data=f"adm_direct_add_@{channel_clean}"))
                if actor_id:
                    btns.append(types.InlineKeyboardButton("💬 مراسلة الفاعل", callback_data=f"adm_contact_actor_{actor_id}"))
                    btns.append(types.InlineKeyboardButton("🚫 حظر المستخدم", callback_data=f"adm_ban_actor_{actor_id}"))
                markup.add(*btns)

                send_notification_to_requests_group_or_admins(alert_text, markup=markup if btns else None)
                logger.info(f"📥 تم إضافة البوت إلى القناة {channel_username} بواسطة {actor_uname} ({actor_id})")

    except Exception as e:
        logger.error(f"خطأ في handle_bot_membership_change: {e}", exc_info=True)

@bot.message_handler(commands=['start'])
def send_welcome(message):
    username = message.from_user.username
    user_id = message.from_user.id
    first_name = message.from_user.first_name

    try:
        bot.clear_step_handler_by_chat_id(message.chat.id)
    except Exception:
        pass

    db.save_bot_user(user_id, username, first_name)

    logger.info(f"طلب /start من user_id: {user_id}, username: {username}")
    if is_admin(user_id, username):
        show_main_menu(message.chat.id, user_id)
    else:
        show_user_menu(message.chat.id)

@bot.message_handler(commands=['broadcast'])
def broadcast_to_all_users(message):
    """إرسال رسالة في الخاص لكل من عمل /start سابقاً - للأونر فقط"""
    sender_id = message.from_user.id
    if not is_owner(sender_id):
        bot.send_message(message.chat.id, "❌ هذا الأمر متاح للأونر فقط.")
        return

    text_to_send = message.text.replace('/broadcast', '', 1).strip() if message.text else ""
    if not text_to_send:
        bot.send_message(
            message.chat.id,
            "✍️ اكتب الرسالة بعد الأمر مباشرة:\n`/broadcast نص الرسالة`",
            parse_mode='Markdown'
        )
        return

    users = db.get_all_bot_users()
    if not users:
        bot.send_message(message.chat.id, "📭 لا يوجد مستخدمون مسجلون بعد.")
        return

    sent_count = 0
    failed_count = 0

    for (target_user_id,) in users:
        try:
            # إرسال بدون Markdown لتجنب مشاكل الروابط التي تحتوي "_"
            bot.send_message(target_user_id, text_to_send, parse_mode=None)
            sent_count += 1
            time.sleep(0.05)
        except Exception as e:
            logger.warning(f"فشل الإرسال إلى user_id {target_user_id}: {e}")
            failed_count += 1

    result_text = (
        "📢 *نتيجة الإرسال الجماعي*\n\n"
        f"✅ تم الإرسال: *{sent_count}*\n"
        f"❌ فشل: *{failed_count}*\n"
        f"👥 الإجمالي: *{len(users)}*"
    )
    bot.send_message(message.chat.id, result_text, parse_mode='Markdown')

@bot.message_handler(commands=['check'])
def check_admin_status(message):
    """أمر لاختبار حالة المشرف"""
    username = message.from_user.username
    user_id = message.from_user.id
    is_admin_result = is_admin(user_id, username)
    
    # الحصول على قائمة المشرفين من قاعدة البيانات
    admins_list = db.execute_query('SELECT user_id, username FROM admins', fetch=True) or []
    
    response = f"🔍 *حالة المشرف:*\n\n"
    response += f"• User ID: `{user_id}`\n"
    response += f"• Username: `{username or 'غير موجود'}`\n"
    response += f"• حالة المشرف: {'✅ مشرف' if is_admin_result else '❌ ليس مشرفاً'}\n\n"
    response += f"📋 *المشرفون المسجلون ({len(admins_list)}):*\n"
    for uid, uname in admins_list:
        if uid and uname:
            response += f"• `@{uname}` (ID: `{uid}`)\n"
        elif uid:
            response += f"• ID: `{uid}`\n"
        elif uname:
            response += f"• `@{uname}` (يوزرنيم فقط)\n"
    
    bot.send_message(message.chat.id, response, parse_mode='Markdown')

@bot.message_handler(commands=['check_milestones'])
def check_milestones_cmd(message):
    """أمر يدوي لفحص حواجز نمو القنوات وإرسال بطاقات التهنئة للمستحقين"""
    user_id = message.from_user.id
    username = message.from_user.username
    if not is_admin(user_id, username):
        return
    msg = bot.send_message(message.chat.id, "⏳ جاري فحص إنجازات وحواجز نمو القنوات المعتمدة...")
    count = check_all_channels_milestones()
    bot.edit_message_text(f"✅ اكتمل الفحص! تم إرسال {count} بطاقة تهنئة بالقنوات التي حققت حواجز نمو جديدة (1k, 2k, 3k, 5k...).", message.chat.id, msg.message_id)

@bot.message_handler(commands=['check_radar', 'check_anticheat'])
def check_radar_cmd(message):
    """أمر يدوي لتشغيل رادار كشف الغش وفحص بقاء المنشورات في القنوات فوراً"""
    user_id = message.from_user.id
    username = message.from_user.username
    if not is_admin(user_id, username):
        return
    msg = bot.send_message(message.chat.id, "🕵️‍♂️ <b>جاري فحص جميع المنشورات في القنوات والتأكد من عدم حذفها...</b>", parse_mode='HTML')
    detected = run_anti_cheat_check()
    if detected > 0:
        bot.edit_message_text(f"🚨 <b>اكتمل الفحص! تم رصد {detected} قناة قامت بحذف المنشور وإرسال التنبيهات اللازمة.</b>", message.chat.id, msg.message_id, parse_mode='HTML')
    else:
        bot.edit_message_text("✅ <b>اكتمل فحص الرادار بنجاح! جميع المنشورات سليمة وموجودة في القنوات ولم يحذفها أحد.</b>", message.chat.id, msg.message_id, parse_mode='HTML')

@bot.message_handler(commands=['setgroup', 'set_requests_group'])
def set_requests_group_cmd(message):
    """أمر لتعيين القروب المخصص لاستقبال طلبات إدراج القنوات"""
    user_id = message.from_user.id
    username = message.from_user.username
    if not is_admin(user_id, username):
        try:
            bot.send_message(message.chat.id, "❌ هذا الأمر متاح للمشرفين فقط.")
        except Exception:
            pass
        return

    if message.chat.type in ['group', 'supergroup']:
        chat_id = message.chat.id
        chat_title = message.chat.title or "القروب"
        thread_id = getattr(message, 'message_thread_id', None)
        
        db.set_setting("requests_group_id", str(chat_id))
        if thread_id:
            db.set_setting("requests_thread_id", str(thread_id))
        else:
            db.delete_setting("requests_thread_id")

        response_text = (
            f"✅ *تم بنجاح ربط القروب لاستقبال الطلبات!*\n\n"
            f"📌 الاسم: *{chat_title}*\n"
            f"🆔 المعرف: `{chat_id}`\n"
        )
        if thread_id:
            response_text += f"📂 رقم الموضوع (Topic): `{thread_id}`\n"
        response_text += "\nمن الآن، ستصل جميع طلبات إدراج القنوات إلى هنا مباشرة مع أزرار القبول والرفض 🚀"

        # محاولة الإرسال بأمان داخل القروب
        sent = False
        if thread_id:
            try:
                bot.send_message(chat_id, response_text, parse_mode='Markdown', message_thread_id=thread_id)
                sent = True
            except Exception as e:
                logger.warning(f"فشل الإرسال في الموضوع {thread_id}: {e}")
        
        if not sent:
            try:
                bot.send_message(chat_id, response_text, parse_mode='Markdown')
                sent = True
            except Exception as e:
                logger.warning(f"تعذر الإرسال في الموضوع العام (قد يكون مغلقاً TOPIC_CLOSED): {e}")

        # إذا كان الموضوع مغلقاً وتعذر الإرسال داخل القروب، نخطر المشرف في الخاص
        if not sent:
            try:
                private_alert = (
                    f"✅ *تم حفظ ربط القروب ({chat_title}) بنجاح!*\n\n"
                    f"⚠️ *ملاحظة مهمة:*\n"
                    f"تعذر إرسال رسالة التأكيد داخل القروب لأن الموضوع العام (General) أو الموضوع الذي كتبت فيه مقفل `🔒 (Topic Closed)` في إعدادات التيليجرام.\n\n"
                    f"👉 *الحل:* تأكد من فتح الموضوع (Reopen Topic) أو أرسل `/setgroup` داخل موضوع مفتوح، لتتمكن من استقبال الطلبات داخل القروب بسلاسة."
                )
                bot.send_message(user_id, private_alert, parse_mode='Markdown')
            except Exception:
                pass
    else:
        parts = message.text.strip().split()
        if len(parts) > 1 and (parts[1].startswith('-') or parts[1].isdigit()):
            target_chat_id = parts[1]
            db.set_setting("requests_group_id", target_chat_id)
            db.delete_setting("requests_thread_id")
            bot.send_message(message.chat.id, f"✅ تم تعيين معرف القروب بنجاح: `{target_chat_id}`", parse_mode='Markdown')
        else:
            current_group = db.get_setting("requests_group_id")
            current_thread = db.get_setting("requests_thread_id")
            status_str = f"`{current_group}`" if current_group else "لم يتم التعيين بعد"
            if current_thread:
                status_str += f" (Topic: `{current_thread}`)"
            text = (
                "⚙️ *إعداد قروب الطلبات الخاص*\n\n"
                f"• القروب الحالي: {status_str}\n\n"
                "📌 *طريقة التعيين:*\n"
                "1. أضف البوت إلى القروب المخصص للطلبات.\n"
                "2. اكتب داخل ذلك القروب الأمر: `/setgroup`\n\n"
                "أو اكتب في الخاص: `/setgroup -100xxxxxxxxx`\n"
                "ولإلغاء الربط اكتب: `/delgroup`"
            )
            bot.send_message(message.chat.id, text, parse_mode='Markdown')

@bot.message_handler(commands=['delgroup', 'unsetgroup'])
def unset_requests_group_cmd(message):
    """إلغاء ربط قروب الطلبات"""
    user_id = message.from_user.id
    username = message.from_user.username
    if not is_admin(user_id, username):
        return
    db.delete_setting("requests_group_id")
    db.delete_setting("requests_thread_id")
    try:
        bot.send_message(message.chat.id, "✅ تم إلغاء ربط قروب الطلبات. ستصل الطلبات في الخاص للمشرفين.")
    except Exception:
        pass

def show_blacklist_menu(chat_id: int, message_id: int = None):
    blocked_list = db.get_blacklist()
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    text = (
        "<blockquote>\n"
        "🚫 <b>قائمة الحظر الشاملة (Blacklist)</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
    )
    
    if not blocked_list:
        text += "📭 <b>لا يوجد أي مستخدم أو قناة في قائمة الحظر حالياً.</b>\n"
    else:
        text += f"📊 <b>إجمالي المحظورين:</b> <b>{len(blocked_list)}</b>\n\n"
        for item in blocked_list[:20]:  # عرض حتى 20 عنصر
            _b_id, t_type, t_id, reason, blocked_by, created_at = item
            icon = "👤 <b>مستخدم:</b>" if t_type == "user" else "📢 <b>قناة:</b>"
            safe_tid = html.escape(str(t_id))
            safe_reason = html.escape(str(reason or 'بدون سبب'))
            text += f"• {icon} <code>{safe_tid}</code>\n  📝 <b>السبب:</b> <b>{safe_reason}</b>\n"
            markup.add(
                types.InlineKeyboardButton(f"🗑️ فك حظر {t_id}", callback_data=f"unban_{t_id}")
            )
            
    text += (
        "━━━━━━━━━━━━━━━━━━\n"
        "</blockquote>\n\n"
        "👨‍💻 <b>إدارة المنصة:</b> @NEXUS_IMTIAZ"
    )
    
    markup.add(
        types.InlineKeyboardButton("➕ حظر يدوي (مستخدم / قناة)", callback_data="ban_manual_prompt"),
        types.InlineKeyboardButton("🔙 رجوع للقائمة الرئيسية", callback_data="back_main_menu")
    )
    
    try:
        if message_id:
            bot.edit_message_text(text, chat_id, message_id, reply_markup=markup, parse_mode='HTML')
        else:
            bot.send_message(chat_id, text, reply_markup=markup, parse_mode='HTML')
    except Exception:
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode='HTML')

def show_main_menu(chat_id: int, user_id: int = None):
    welcome_text = (
        "<blockquote>\n"
        "🏡 <b>لوحة تحكم المشرفين الرئيسية 👨‍💻</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "👋 <b>مرحباً بك يا المشرف في منصة إدارة الدعم!</b>\n"
        "👇 <b>اختر العملية التي ترغب في تنفيذها من الأزرار أدناه:</b>\n"
        "</blockquote>\n\n"
        "👨‍💻 <b>إدارة المنصة:</b> @NEXUS_IMTIAZ"
    )
    markup = types.InlineKeyboardMarkup(row_width=2)
    buttons = [
        ("➕ إضافة قناة", "add_channel"),
        ("📋 عرض القنوات", "show_channels"),
        ("🗑️ حذف قناة", "delete_channel"),
        ("📤 إرسال رسالة للقنوات", "send_message"),
        ("🔁 تحويل رسالة للقنوات", "forward_message"),
        ("❌ حذف رسائل منشورة", "delete_messages"),
        ("🚫 قائمة الحظر", "manage_blacklist")
    ]
    # إضافة خيارات الإدارة لمالك البوت
    if user_id is not None:
        is_owner_result = is_owner(user_id)
        if is_owner_result:
            buttons.append(("👥 إدارة المشرفين", "manage_admins"))
            buttons.append(("⚙️ قروب الطلبات", "manage_req_group"))
    
    for text_btn, callback in buttons:
        btn = types.InlineKeyboardButton(text_btn, callback_data=callback)
        markup.add(btn)
    bot.send_message(chat_id, welcome_text, reply_markup=markup, parse_mode='HTML')

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    username = call.from_user.username
    user_id = call.from_user.id
    data = call.data or ""
    logger.info(f"طلب callback من user_id: {user_id}, username: {username}, callback_data: {data}")

    if data.startswith("u_"):
        handle_user_callback(call)
        return

    if not is_admin(user_id, username):
        logger.warning(f"تم رفض callback من user_id: {user_id}, username: {username} - ليس مشرفاً")
        try:
            bot.answer_callback_query(call.id, "❌ ليس لديك صلاحية", show_alert=True)
        except Exception:
            pass
        return

    try:
        bot.answer_callback_query(call.id)
    except:
        pass

    # معالجة قبول أو رفض ومراسلة طلبات القنوات من طرف الأدمن
    if data.startswith("adm_approve_"):
        request_id = int(data.replace("adm_approve_", ""))
        row = db.get_listing_request(request_id)
        if not row:
            bot.send_message(call.message.chat.id, "❌ لم يتم العثور على الطلب.")
            return
        _id, req_user_id, _un, _fn, channel_id, channel_title, _mc, status, _reason, *_rest = row
        
        db.add_channel(channel_id)
        db.update_listing_status(request_id, "approved")
        
        admin_tag = f"@{username}" if username else f"ID: {user_id}"
        safe_channel = html.escape(channel_id)
        safe_title = html.escape(channel_title or channel_id)
        safe_admin = html.escape(admin_tag)
        try:
            bot.edit_message_text(
                f"✅ <b>تم قبول الطلب #{request_id} بواسطة {safe_admin}!</b>\n\n"
                f"📢 القناة: <code>{safe_channel}</code> ({safe_title})\n"
                "👤 تمت إضافتها بنجاح إلى قائمة المجلد القادم 🚀",
                call.message.chat.id,
                call.message.message_id,
                parse_mode='HTML'
            )
        except Exception:
            pass
        
        try:
            bot.send_message(
                req_user_id,
                f"🎉 <b>مبروك! تم قبول قناتك ({safe_channel}) في المجلد القادم.</b>\n\n"
                "🚀 البوت راح يتكفل بنشر المجلد أوتوماتيكياً في الوقت المحدد.",
                parse_mode='HTML'
            )
        except Exception as e:
            logger.warning(f"فشل إشعار المستخدم {req_user_id}: {e}")
        return

    # فتح قائمة أسباب الرفض
    elif data.startswith("adm_rej_menu_"):
        request_id = int(data.replace("adm_rej_menu_", ""))
        row = db.get_listing_request(request_id)
        if not row:
            bot.send_message(call.message.chat.id, "❌ لم يتم العثور على الطلب.")
            return
        _id, req_user_id, _un, _fn, channel_id, channel_title, _mc, status, _reason, *_rest = row
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("🔓 قناة تسريبات / محتوى مقرصن", callback_data=f"adm_rej_{request_id}_leaks"),
            types.InlineKeyboardButton("🔒 مشاركة بمجلد آخر (ازدواجية)", callback_data=f"adm_rej_{request_id}_multi"),
            types.InlineKeyboardButton("👥 مشتركين وهميين / رشق بدون تفاعل", callback_data=f"adm_rej_{request_id}_fake"),
            types.InlineKeyboardButton("🚫 محتوى غير مناسب", callback_data=f"adm_rej_{request_id}_content"),
            types.InlineKeyboardButton("📉 القناة ضعيفة / تفاعل ضعيف", callback_data=f"adm_rej_{request_id}_weak"),
            types.InlineKeyboardButton("🤖 البوت ليس أدمن (أو بدون نشر)", callback_data=f"adm_rej_{request_id}_notadmin"),
            types.InlineKeyboardButton("✍️ كتابة سبب مخصص", callback_data=f"adm_rej_{request_id}_custom"),
            types.InlineKeyboardButton("🔙 إلغاء والعودة للبطاقة", callback_data=f"adm_rej_{request_id}_back")
        )
        try:
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=markup)
        except Exception:
            pass
        return

    # معالجة قرار الرفض أو العودة للبطاقة
    elif data.startswith("adm_rej_"):
        parts = data.split("_")
        if len(parts) < 4:
            return
        request_id = int(parts[2])
        reason_key = parts[3]
        
        row = db.get_listing_request(request_id)
        if not row:
            bot.send_message(call.message.chat.id, "❌ لم يتم العثور على الطلب.")
            return
        _id, req_user_id, _un, _fn, channel_id, channel_title, _mc, status, _reason, *_rest = row
        
        if reason_key == "back":
            orig_markup = make_request_card_markup(request_id, channel_id)
            try:
                bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=orig_markup)
            except Exception:
                pass
            return
            
        elif reason_key == "custom":
            safe_channel = html.escape(channel_id)
            msg = bot.send_message(
                call.message.chat.id,
                f"✍️ اكتب سبب رفض الطلب #{request_id} للقناة <code>{safe_channel}</code> ليتم إرساله للمستخدم:",
                parse_mode='HTML'
            )
            clear_chat_step_handlers(call.message.chat.id)
            bot.register_next_step_handler(
                msg,
                lambda m: process_custom_reject(m, request_id, req_user_id, channel_id, channel_title, call.message.message_id, call.message.chat.id)
            )
            return
            
        elif reason_key in REJECTION_REASONS:
            reason_text = REJECTION_REASONS[reason_key]
            db.update_listing_status(request_id, "rejected", reject_reason=reason_text)
            admin_tag = f"@{username}" if username else f"ID: {user_id}"
            safe_channel = html.escape(channel_id)
            safe_admin = html.escape(admin_tag)
            safe_reason = html.escape(reason_text)
            
            try:
                bot.edit_message_text(
                    f"❌ <b>تم رفض الطلب #{request_id} للقناة <code>{safe_channel}</code> بواسطة {safe_admin}</b>\n\n"
                    f"📝 <b>السبب:</b> {safe_reason}",
                    call.message.chat.id,
                    call.message.message_id,
                    parse_mode='HTML'
                )
            except Exception:
                pass
            
            try:
                user_reject_msg = (
                    f"❌ <b>نعتذر منك، تم رفض طلب إضافة قناتك ({safe_channel}).</b>\n\n"
                    f"📝 <b>سبب الرفض:</b>\n{safe_reason}\n\n"
                    "💡 يمكنك تصحيح المشكلة وتقديم طلب جديد في أي وقت!"
                )
                bot.send_message(req_user_id, user_reject_msg, parse_mode='HTML')
            except Exception as e:
                logger.warning(f"فشل إشعار المستخدم {req_user_id}: {e}")
            return

    # مراسلة صاحب القناة
    elif data.startswith("adm_contact_"):
        request_id = int(data.replace("adm_contact_", ""))
        row = db.get_listing_request(request_id)
        if not row:
            bot.send_message(call.message.chat.id, "❌ لم يتم العثور على الطلب.")
            return
        _id, req_user_id, _un, _fn, channel_id, channel_title, _mc, status, _reason, *_rest = row
        
        msg = bot.send_message(
            call.message.chat.id,
            f"💬 أرسل الرسالة التي تريد توجيهها لصاحب القناة `{channel_id}`:\n(سيتم إرسالها باسم إدارة البوت)"
        )
        clear_chat_step_handlers(call.message.chat.id)
        bot.register_next_step_handler(msg, lambda m: process_admin_contact_user(m, req_user_id, channel_id, request_id))
        return

    # حظر المستخدم من بطاقة الطلب
    elif data.startswith("adm_ban_user_"):
        request_id = int(data.replace("adm_ban_user_", ""))
        row = db.get_listing_request(request_id)
        if not row:
            bot.send_message(call.message.chat.id, "❌ لم يتم العثور على الطلب.")
            return
        _id, req_user_id, _un, _fn, channel_id, channel_title, _mc, status, _reason, *_rest = row
        admin_tag = f"@{username}" if username else f"ID: {user_id}"
        
        db.add_to_blacklist("user", str(req_user_id), reason="حظر مباشر من بطاقة الطلب (سبام/مخالفة)", blocked_by=admin_tag)
        db.update_listing_status(request_id, "rejected", reject_reason="تم حظر المستخدم من البوت.")
        
        safe_admin = html.escape(admin_tag)
        try:
            bot.edit_message_text(
                f"🚫 <b>تم حظر المستخدم ({req_user_id}) وإلغاء الطلب بواسطة {safe_admin}!</b>\n\n"
                "لن يتمكن هذا المستخدم من إرسال أي طلبات جديدة في البوت.",
                call.message.chat.id,
                call.message.message_id,
                parse_mode='HTML'
            )
        except Exception:
            pass
        try:
            bot.send_message(req_user_id, "🚫 تم حظرك من تقديم أي طلبات في هذا البوت لمخالفة القوانين والشروط.")
        except Exception:
            pass
        return

    # حظر القناة من إشعار النشاط
    elif data.startswith("adm_ban_chan_ref_"):
        target_ch = data.replace("adm_ban_chan_ref_", "")
        admin_tag = f"@{username}" if username else f"ID: {user_id}"
        db.add_to_blacklist("channel", str(target_ch), reason="حظر من إشعار نشاط البوت", blocked_by=admin_tag)
        bot.send_message(call.message.chat.id, f"🚫 <b>تم حظر القناة <code>{html.escape(target_ch)}</code> بنجاح!</b>", parse_mode='HTML')
        return

    # حظر القناة من بطاقة الطلب
    elif data.startswith("adm_ban_chan_"):
        request_id = int(data.replace("adm_ban_chan_", ""))
        row = db.get_listing_request(request_id)
        if not row:
            bot.send_message(call.message.chat.id, "❌ لم يتم العثور على الطلب.")
            return
        _id, req_user_id, _un, _fn, channel_id, channel_title, _mc, status, _reason, *_rest = row
        admin_tag = f"@{username}" if username else f"ID: {user_id}"
        
        db.add_to_blacklist("channel", channel_id, reason="قناة محظورة / سبام", blocked_by=admin_tag)
        db.update_listing_status(request_id, "rejected", reject_reason="تم حظر القناة لمخالفة الشروط.")
        
        safe_chan = html.escape(channel_id)
        safe_admin = html.escape(admin_tag)
        try:
            bot.edit_message_text(
                f"🚫 <b>تم حظر القناة (<code>{safe_chan}</code>) وإلغاء الطلب بواسطة {safe_admin}!</b>\n\n"
                "لن يتمكن أي شخص من تقديم هذه القناة في المجلد مجدداً.",
                call.message.chat.id,
                call.message.message_id,
                parse_mode='HTML'
            )
        except Exception:
            pass
        try:
            bot.send_message(req_user_id, f"🚫 نعتذر منك، تم رفض طلبك وإدراج القناة ({channel_id}) في قائمة الحظر لمخالفة الشروط.")
        except Exception:
            pass
        return

    # إضافة القناة مباشرة للمجلد من إشعار النشاط
    elif data.startswith("adm_direct_add_"):
        chan_to_add = data.replace("adm_direct_add_", "")
        if db.add_channel(chan_to_add):
            bot.send_message(call.message.chat.id, f"✅ <b>تمت إضافة القناة <code>{html.escape(chan_to_add)}</code> بنجاح إلى قائمة المجلد! 🚀</b>", parse_mode='HTML')
        else:
            bot.send_message(call.message.chat.id, f"ℹ️ <b>القناة <code>{html.escape(chan_to_add)}</code> موجودة مسبقاً في المجلد.</b>", parse_mode='HTML')
        return

    # مراسلة الفاعل من إشعار النشاط
    elif data.startswith("adm_contact_actor_"):
        target_act_id = int(data.replace("adm_contact_actor_", ""))
        msg = bot.send_message(
            call.message.chat.id,
            f"💬 <b>أرسل الآن نص الرسالة التي تريد توجيهها للمستخدم (ID: <code>{target_act_id}</code>):</b>",
            parse_mode='HTML'
        )
        clear_chat_step_handlers(call.message.chat.id)
        bot.register_next_step_handler(msg, lambda m: process_admin_contact_direct_user(m, target_act_id))
        return

    # حظر المستخدم من إشعار النشاط
    elif data.startswith("adm_ban_actor_"):
        target_act_id = data.replace("adm_ban_actor_", "")
        admin_tag = f"@{username}" if username else f"ID: {user_id}"
        db.add_to_blacklist("user", str(target_act_id), reason="حظر من إشعار نشاط البوت", blocked_by=admin_tag)
        bot.send_message(call.message.chat.id, f"🚫 <b>تم حظر المستخدم <code>{target_act_id}</code> بنجاح من استخدام البوت!</b>", parse_mode='HTML')
        return

    # نفي واستبعاد القناة وحظرها نهائياً عند 5 إنذارات
    elif data.startswith("adm_ban_strike_channel_"):
        chan_to_ban = data.replace("adm_ban_strike_channel_", "")
        chan_ref = f"@{chan_to_ban}" if not chan_to_ban.startswith('@') and not chan_to_ban.startswith('-') else chan_to_ban
        admin_tag = f"@{username}" if username else f"ID: {user_id}"
        
        # حذف من قائمة القنوات المعتمدة
        db.delete_channel(chan_ref)
        # إضافة لقائمة الحظر الدائم
        db.add_to_blacklist("channel", chan_ref, reason="نفي واستبعاد بسبب بلوغ 5 إنذارات لحذف منشور الدعم مبكراً", blocked_by=admin_tag)
        
        # إشعار صاحب القناة في الخاص
        owner_id = db.get_channel_owner_id(chan_ref)
        if owner_id:
            try:
                bot.send_message(
                    owner_id,
                    "<blockquote>\n"
                    "⛔ <b>إشعار استبعاد ونفي القناة نهائياً!</b>\n"
                    "━━━━━━━━━━━━━━━━━━\n"
                    f"📢 <b>القناة:</b> <code>{html.escape(chan_ref)}</code>\n"
                    "⚠️ <b>السبب:</b> <b>بلوغ الحد الأقصى من المخالفات (5 إنذارات) بحذف منشورات المجلد قبل موعدها.</b>\n\n"
                    "🚫 <b>تم حذف قناتك من المجلد وإدراجها في قائمة الحظر الدائم.</b>\n"
                    "</blockquote>\n\n"
                    "👨‍💻 <b>إدارة المنصة:</b> @NEXUS_IMTIAZ",
                    parse_mode='HTML'
                )
            except Exception:
                pass
                
        bot.send_message(
            call.message.chat.id,
            f"⛔ <b>تم بنجاح نفي واستبعاد القناة <code>{html.escape(chan_ref)}</code> وحظرها نهائياً من المجلد!</b>",
            parse_mode='HTML'
        )
        return

    # تصفير الإنذارات للقناة
    elif data.startswith("adm_reset_strikes_"):
        chan_to_reset = data.replace("adm_reset_strikes_", "")
        chan_ref = f"@{chan_to_reset}" if not chan_to_reset.startswith('@') and not chan_to_reset.startswith('-') else chan_to_reset
        db.reset_channel_strikes(chan_ref)
        bot.send_message(
            call.message.chat.id,
            f"🔄 <b>تم تصفير إنذارات القناة <code>{html.escape(chan_ref)}</code> بنجاح وأصبحت 0/5.</b>",
            parse_mode='HTML'
        )
        return

    # الرد على رسالة دعم فني للمستخدم
    elif data.startswith("adm_reply_support_"):
        target_uid = int(data.replace("adm_reply_support_", ""))
        msg = bot.send_message(
            call.message.chat.id,
            f"💬 <b>أرسل الآن نص الرد الذي ترغب في إرساله للمستخدم (ID: <code>{target_uid}</code>):</b>\n(سيصل الرد مباشرة في خاص المستخدم باسم إدارة المنصة)",
            parse_mode='HTML'
        )
        clear_chat_step_handlers(call.message.chat.id)
        bot.register_next_step_handler(msg, lambda m: process_admin_support_reply(m, target_uid))
        return

    # إدارة قائمة الحظر
    elif data == "manage_blacklist":
        show_blacklist_menu(call.message.chat.id, call.message.message_id)
        return

    # فك الحظر
    elif data.startswith("unban_"):
        target_id = data.replace("unban_", "", 1)
        db.remove_from_blacklist(target_id)
        try:
            bot.answer_callback_query(call.id, f"✅ تم فك الحظر عن {target_id}")
        except Exception:
            pass
        show_blacklist_menu(call.message.chat.id, call.message.message_id)
        return

    # طلب الحظر اليدوي
    elif data == "ban_manual_prompt":
        msg = bot.send_message(
            call.message.chat.id,
            "✍️ أرسل <b>معرف المستخدم (User ID)</b> أو <b>يوزر القناة (@channel)</b> لحظره يدوياً من البوت:",
            parse_mode='HTML'
        )
        clear_chat_step_handlers(call.message.chat.id)
        bot.register_next_step_handler(msg, process_manual_ban)
        return

    elif call.data == "manage_req_group":
        if not is_owner(user_id):
            bot.answer_callback_query(call.id, "❌ ليس لديك صلاحية للوصول إلى هذه الخيارات", show_alert=True)
            return
        
        current_group = db.get_setting("requests_group_id")
        if current_group:
            status_text = f"✅ مربوط بالمعرف: `{current_group}`"
        else:
            status_text = "❌ غير محدد (تصل الطلبات في الخاص للمشرفين)"
        
        markup = types.InlineKeyboardMarkup()
        if current_group:
            markup.add(types.InlineKeyboardButton("🗑️ إلغاء ربط القروب", callback_data="unlink_req_group"))
        markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="back_main_menu"))
        
        text = (
            "⚙️ *إدارة قروب طلبات القنوات*\n\n"
            f"• الحالة: {status_text}\n\n"
            "📌 *كيفية ربط القروب:*\n"
            "1. أضف البوت إلى القروب المخصص للطلبات.\n"
            "2. اكتب داخل ذلك القروب الأمر: `/setgroup`\n\n"
            "أو أرسل في الخاص: `/setgroup -100xxxxxxxxx`"
        )
        bot.send_message(call.message.chat.id, text, reply_markup=markup, parse_mode='Markdown')

    elif call.data == "unlink_req_group":
        if not is_owner(user_id):
            bot.answer_callback_query(call.id, "❌ ليس لديك صلاحية", show_alert=True)
            return
        db.delete_setting("requests_group_id")
        db.delete_setting("requests_thread_id")
        bot.edit_message_text(
            "✅ تم إلغاء ربط القروب بنجاح. ستصل الطلبات الجديدة في الخاص للمشرفين.",
            call.message.chat.id,
            call.message.message_id
        )

    elif call.data == "back_main_menu":
        show_main_menu(call.message.chat.id, user_id)

    elif call.data == "add_channel":
        msg = bot.send_message(call.message.chat.id, "📌 أرسل معرف القناة:\n- بصيغة: @username\n- أو رابط: https://t.me/username")
        clear_chat_step_handlers(call.message.chat.id)
        bot.register_next_step_handler(msg, process_add_channel)

    elif call.data == "show_channels":
        channels = db.get_all_channels()
        logger.info(f"طلب عرض القنوات - عدد القنوات: {len(channels)}")
        if channels:
            response = "*📊 القنوات المضافة:*\n\n"
            for ch_id, ch_name in channels:
                response += f"• `{ch_id}`\n"
            bot.send_message(call.message.chat.id, response, parse_mode="Markdown")
        else:
            logger.warning("لا توجد قنوات مضافة في قاعدة البيانات")
            bot.send_message(call.message.chat.id, "📭 لا توجد قنوات مضافة.")

    elif call.data == "delete_channel":
        channels = db.get_all_channels()
        if channels:
            markup = types.InlineKeyboardMarkup()
            for ch_id, ch_name in channels:
                markup.add(types.InlineKeyboardButton(f"🗑️ {ch_name}", callback_data=f"delete_channel_{ch_id}"))
            bot.send_message(call.message.chat.id, "اختر القناة للحذف:", reply_markup=markup)
        else:
            bot.send_message(call.message.chat.id, "📭 لا توجد قنوات.")

    elif call.data == "send_message":
        msg = bot.send_message(call.message.chat.id, "📤 أرسل الرسالة للنشر")
        clear_chat_step_handlers(call.message.chat.id)
        bot.register_next_step_handler(msg, process_direct_message)

    elif call.data == "forward_message":
        msg = bot.send_message(call.message.chat.id, "🔄 قم بتوجيه رسالة للبوت لتحويلها")
        clear_chat_step_handlers(call.message.chat.id)
        bot.register_next_step_handler(msg, process_forward_message)

    elif call.data == "manage_admins":
        # التحقق من أن المستخدم هو المشرف الأساسي فقط
        if not is_owner(user_id):
            bot.answer_callback_query(call.id, "❌ ليس لديك صلاحية للوصول إلى هذه الخيارات", show_alert=True)
            return
        
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("➕ إضافة مشرف", callback_data="add_admin"),
            types.InlineKeyboardButton("📋 عرض المشرفين", callback_data="list_admins"),
            types.InlineKeyboardButton("🗑️ حذف مشرف", callback_data="delete_admin")
        )
        bot.send_message(call.message.chat.id, "👥 إدارة المشرفين:", reply_markup=markup)

    elif call.data == "delete_messages":
        show_recent_messages(call.message.chat.id)

    elif call.data.startswith("delete_channel_"):
        channel_id = call.data.replace("delete_channel_", "", 1)
        if db.delete_channel(channel_id):
            bot.edit_message_text(f"✅ تم حذف القناة `{channel_id}`", call.message.chat.id, call.message.message_id, parse_mode='Markdown')
        else:
            bot.edit_message_text("❌ فشل الحذف", call.message.chat.id, call.message.message_id, parse_mode='Markdown')

    elif call.data == "add_admin":
        # التحقق من أن المستخدم هو المشرف الأساسي فقط
        if not is_owner(user_id):
            bot.answer_callback_query(call.id, "❌ ليس لديك صلاحية للوصول إلى هذه الخيارات", show_alert=True)
            return
        msg = bot.send_message(call.message.chat.id, "👤 أرسل معرف المستخدم (رقم) أو اليوزرنيم (@username) لإضافته كمشرف")
        clear_chat_step_handlers(call.message.chat.id)
        bot.register_next_step_handler(msg, process_add_admin)

    elif call.data == "list_admins":
        # التحقق من أن المستخدم هو المشرف الأساسي فقط
        if not is_owner(user_id):
            bot.answer_callback_query(call.id, "❌ ليس لديك صلاحية للوصول إلى هذه الخيارات", show_alert=True)
            return
        
        # الحصول على جميع المشرفين من قاعدة البيانات
        admins = db.execute_query('SELECT user_id, username FROM admins ORDER BY id', fetch=True) or []
        logger.info(f"تم جلب {len(admins)} مشرف من قاعدة البيانات")
        
        if admins:
            response = "👥 *المشرفون:*\n\n"
            admin_count = 0
            markup = types.InlineKeyboardMarkup()
            for uid, uname in admins:
                admin_count += 1
                # عدم عرض خيار حذف المشرف الأساسي
                if uid == ADMIN_ID:
                    if uid and uname:
                        response += f"{admin_count}. `@{uname}` (ID: `{uid}`) 👑\n"
                    elif uid:
                        response += f"{admin_count}. ID: `{uid}` 👑\n"
                    elif uname:
                        response += f"{admin_count}. `@{uname}` 👑\n"
                    else:
                        response += f"{admin_count}. مشرف غير محدد 👑\n"
                else:
                    if uid and uname:
                        response += f"{admin_count}. `@{uname}` (ID: `{uid}`)\n"
                        markup.add(types.InlineKeyboardButton(f"🗑️ حذف @{uname}", callback_data=f"delete_admin_{uid}_{uname}"))
                    elif uid:
                        response += f"{admin_count}. ID: `{uid}`\n"
                        markup.add(types.InlineKeyboardButton(f"🗑️ حذف ID: {uid}", callback_data=f"delete_admin_{uid}_"))
                    elif uname:
                        response += f"{admin_count}. `@{uname}` (يوزرنيم فقط)\n"
                        markup.add(types.InlineKeyboardButton(f"🗑️ حذف @{uname}", callback_data=f"delete_admin__{uname}"))
                    else:
                        response += f"{admin_count}. مشرف غير محدد\n"
            response += f"\n📊 *إجمالي المشرفين: {admin_count}*"
            if markup.keyboard:
                bot.send_message(call.message.chat.id, response, reply_markup=markup, parse_mode='Markdown')
            else:
                bot.send_message(call.message.chat.id, response, parse_mode='Markdown')
        else:
            bot.send_message(call.message.chat.id, "📭 لا يوجد مشرفون.")

    elif call.data == "delete_admin":
        # التحقق من أن المستخدم هو المشرف الأساسي فقط
        if not is_owner(user_id):
            bot.answer_callback_query(call.id, "❌ ليس لديك صلاحية للوصول إلى هذه الخيارات", show_alert=True)
            return
        
        # عرض قائمة المشرفين مع خيارات الحذف
        admins = db.execute_query('SELECT user_id, username FROM admins ORDER BY id', fetch=True) or []
        
        if admins:
            markup = types.InlineKeyboardMarkup()
            for uid, uname in admins:
                # عدم عرض خيار حذف المشرف الأساسي
                if uid != ADMIN_ID:
                    if uid and uname:
                        markup.add(types.InlineKeyboardButton(f"🗑️ حذف @{uname}", callback_data=f"delete_admin_{uid}_{uname}"))
                    elif uid:
                        markup.add(types.InlineKeyboardButton(f"🗑️ حذف ID: {uid}", callback_data=f"delete_admin_{uid}_"))
                    elif uname:
                        markup.add(types.InlineKeyboardButton(f"🗑️ حذف @{uname}", callback_data=f"delete_admin__{uname}"))
            
            if markup.keyboard:
                bot.send_message(call.message.chat.id, "اختر المشرف للحذف:", reply_markup=markup)
            else:
                bot.send_message(call.message.chat.id, "📭 لا يوجد مشرفون يمكن حذفهم.")
        else:
            bot.send_message(call.message.chat.id, "📭 لا يوجد مشرفون.")

    elif call.data.startswith("delete_admin_"):
        # التحقق من أن المستخدم هو المشرف الأساسي فقط
        if not is_owner(user_id):
            bot.answer_callback_query(call.id, "❌ ليس لديك صلاحية للوصول إلى هذه الخيارات", show_alert=True)
            return
        
        # استخراج معلومات المشرف من callback_data
        parts = call.data.replace("delete_admin_", "").split("_", 1)
        admin_user_id = None
        admin_username = None
        
        if len(parts) == 2:
            if parts[0] and parts[0] != "":
                try:
                    admin_user_id = int(parts[0])
                except ValueError:
                    pass
            if parts[1] and parts[1] != "":
                admin_username = parts[1]
        elif len(parts) == 1:
            if parts[0].isdigit():
                try:
                    admin_user_id = int(parts[0])
                except ValueError:
                    pass
            else:
                admin_username = parts[0]
        
        # منع حذف المشرف الأساسي
        if admin_user_id == ADMIN_ID:
            bot.answer_callback_query(call.id, "❌ لا يمكن حذف المشرف الأساسي", show_alert=True)
            return
        
        # حذف المشرف
        success = False
        if admin_user_id:
            success = db.execute_query('DELETE FROM admins WHERE user_id = %s', (admin_user_id,))
        elif admin_username:
            success = db.execute_query('DELETE FROM admins WHERE username = %s', (admin_username,))
        
        if success:
            if admin_user_id and admin_username:
                bot.send_message(call.message.chat.id, f"✅ تم حذف المشرف `@{admin_username}` (ID: `{admin_user_id}`)", parse_mode='Markdown')
            elif admin_user_id:
                bot.send_message(call.message.chat.id, f"✅ تم حذف المشرف (ID: `{admin_user_id}`)", parse_mode='Markdown')
            elif admin_username:
                bot.send_message(call.message.chat.id, f"✅ تم حذف المشرف `@{admin_username}`", parse_mode='Markdown')
            logger.info(f"تم حذف مشرف - user_id: {admin_user_id}, username: {admin_username}")
        else:
            bot.send_message(call.message.chat.id, "❌ حدث خطأ أثناء حذف المشرف")

    elif call.data.startswith("del_onech_"):
        channel_id = call.data.replace("del_onech_", "", 1)
        delete_last_post_from_channel(call.message.chat.id, channel_id)

    elif call.data == "del_last_all":
        delete_last_post_from_all_channels(call.message.chat.id, call.message.message_id)

    elif call.data == "delete_all_msgs":
        delete_last_post_from_all_channels(call.message.chat.id, call.message.message_id)

    elif call.data == "cancel_delete":
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.send_message(call.message.chat.id, "✅ تم الإلغاء.")

    elif call.data.startswith("pubch_"):
        parts = call.data.split("_")
        if len(parts) < 3:
            return
        show_publish_confirm(
            call.message.chat.id,
            int(parts[1]),
            call.message.message_id,
            channel_pk=int(parts[2])
        )

    elif call.data.startswith("puball_"):
        pending_id = int(call.data.replace("puball_", "", 1))
        show_publish_confirm(
            call.message.chat.id,
            pending_id,
            call.message.message_id,
            channel_pk=None
        )

    elif call.data.startswith("cancel_sched_"):
        sched_id = int(call.data.replace("cancel_sched_", ""))
        db.cancel_scheduled_deletion(sched_id=sched_id)
        bot.send_message(call.message.chat.id, "✅ <b>تم إلغاء الحذف التلقائي بنجاح! سيظل المنشور دائماً في القنوات.</b>", parse_mode='HTML')
        return

    elif call.data.startswith("pubokall_"):
        parts = call.data.split("_")
        pending_id = int(parts[1])
        hours = int(parts[2]) if len(parts) > 2 else 0
        channels = db.get_all_channels()
        publish_pending_to_channels(
            call.message.chat.id,
            pending_id,
            [ch_id for ch_id, _ in channels],
            call.message.message_id,
            auto_delete_hours=hours
        )

    elif call.data.startswith("pubok_"):
        parts = call.data.split("_")
        if len(parts) < 3:
            return
        pending_id = int(parts[1])
        channel_row = db.get_channel_by_pk(int(parts[2]))
        hours = int(parts[3]) if len(parts) > 3 else 0
        if not channel_row:
            bot.send_message(call.message.chat.id, "❌ القناة غير موجودة")
            return
        _, channel_id, _ = channel_row
        publish_pending_to_channels(
            call.message.chat.id,
            pending_id,
            [channel_id],
            call.message.message_id,
            auto_delete_hours=hours
        )

    elif call.data.startswith("pubback_"):
        pending_id = int(call.data.replace("pubback_", "", 1))
        show_publish_targets(
            call.message.chat.id,
            pending_id,
            menu_msg_id=call.message.message_id
        )

    elif call.data.startswith("preview_confirm_"):
        pending_id = int(call.data.replace("preview_confirm_", ""))
        show_publish_targets(
            call.message.chat.id,
            pending_id,
            menu_msg_id=call.message.message_id
        )

    elif call.data.startswith("preview_edit_"):
        pending_id = int(call.data.replace("preview_edit_", ""))
        msg = bot.send_message(call.message.chat.id, "✏️ أرسل الرسالة المعدلة:")
        clear_chat_step_handlers(call.message.chat.id)
        bot.register_next_step_handler(msg, lambda m: process_edit_message(m, pending_id))

    elif call.data.startswith("preview_cancel_"):
        pending_id = int(call.data.replace("preview_cancel_", ""))
        db.delete_pending_message(pending_id)
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.send_message(call.message.chat.id, "❌ تم إلغاء النشر")

# === معالجة الأوامر والطلبات ===

def process_custom_reject(message, request_id: int, target_user_id: int, channel_id: str, channel_title: str, card_msg_id: int, card_chat_id: int):
    username = message.from_user.username
    user_id = message.from_user.id
    if not is_admin(user_id, username):
        return
    
    custom_reason = message.text.strip() if message.text else "لم يتم تحديد سبب مخصص."
    db.update_listing_status(request_id, "rejected", reject_reason=custom_reason)
    admin_tag = f"@{username}" if username else f"ID: {user_id}"
    safe_channel = html.escape(channel_id)
    safe_admin = html.escape(admin_tag)
    safe_reason = html.escape(custom_reason)
    
    try:
        bot.edit_message_text(
            f"❌ <b>تم رفض الطلب #{request_id} للقناة <code>{safe_channel}</code> بواسطة {safe_admin}</b>\n\n"
            f"📝 <b>السبب:</b> {safe_reason}",
            card_chat_id,
            card_msg_id,
            parse_mode='HTML'
        )
    except Exception:
        pass
    
    try:
        user_reject_msg = (
            "<blockquote>\n"
            f"❌ <b>نعتذر منك، تم رفض طلب إضافة قناتك (<code>{safe_channel}</code>).</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            f"📝 <b>سبب الرفض:</b> <b>{safe_reason}</b>\n\n"
            "💡 <b>يمكنك تصحيح المشكلة وتقديم طلب جديد في أي وقت!</b>\n"
            "</blockquote>\n\n"
            "👨‍💻 <b>إدارة المنصة:</b> @NEXUS_IMTIAZ"
        )
        bot.send_message(target_user_id, user_reject_msg, parse_mode='HTML')
        bot.send_message(message.chat.id, f"✅ تم رفض الطلب #{request_id} وإشعار صاحب القناة بالسبب المخصص!")
    except Exception as e:
        bot.send_message(message.chat.id, f"⚠️ تم تحديث حالة الطلب ولكن تعذر إشعار المستخدم في الخاص: {e}")

def process_admin_contact_user(message, target_user_id: int, channel_id: str, request_id: int):
    username = message.from_user.username
    user_id = message.from_user.id
    if not is_admin(user_id, username):
        return
    
    if not message.text and not message.caption:
        bot.send_message(message.chat.id, "❌ تم إلغاء الإرسال، يرجى إرسال رسالة نصية.")
        return
        
    text_content = message.text or message.caption
    safe_channel = html.escape(channel_id)
    safe_content = html.escape(text_content)
    user_msg = (
        "<blockquote>\n"
        f"📩 <b>رسالة واردة من إدارة المنصة بخصوص طلبك #{request_id} (<code>{safe_channel}</code>):</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"💬 <b>نص الرسالة:</b>\n{safe_content}\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "</blockquote>\n\n"
        "👨‍💻 <b>إدارة المنصة:</b> @NEXUS_IMTIAZ"
    )
    try:
        bot.send_message(target_user_id, user_msg, parse_mode='HTML')
        bot.send_message(message.chat.id, f"✅ تم إرسال رسالتك بنجاح لصاحب القناة (<code>{safe_channel}</code>)!")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ تعذر إرسال الرسالة للمستخدم في الخاص: {e}")

def process_admin_contact_direct_user(message, target_user_id: int):
    username = message.from_user.username
    user_id = message.from_user.id
    if not is_admin(user_id, username):
        return
    
    if not message.text and not message.caption:
        bot.send_message(message.chat.id, "❌ تم إلغاء الإرسال، يرجى إرسال رسالة نصية.")
        return
        
    text_content = message.text or message.caption
    safe_content = html.escape(text_content)
    user_msg = (
        "<blockquote>\n"
        "📩 <b>رسالة واردة من إدارة المنصة:</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"💬 <b>نص الرسالة:</b>\n{safe_content}\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "</blockquote>\n\n"
        "👨‍💻 <b>إدارة المنصة:</b> @NEXUS_IMTIAZ"
    )
    try:
        bot.send_message(target_user_id, user_msg, parse_mode='HTML')
        bot.send_message(message.chat.id, f"✅ <b>تم إرسال رسالتك بنجاح للمستخدم (<code>{target_user_id}</code>)!</b>", parse_mode='HTML')
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ تعذر إرسال الرسالة للمستخدم في الخاص: {e}")

def process_admin_support_reply(message, target_user_id: int):
    username = message.from_user.username
    user_id = message.from_user.id
    if not is_admin(user_id, username):
        return
    
    if not message.text and not message.caption:
        bot.send_message(message.chat.id, "❌ تم إلغاء الإرسال، يرجى إرسال نص للرد.")
        return
        
    admin_reply_text = (message.text or message.caption).strip()
    safe_reply = html.escape(admin_reply_text)
    
    user_msg = (
        "<blockquote>\n"
        "📩 <b>رد جديد من إدارة منصة امتياز (@NEXUS_IMTIAZ) 👨‍💻</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"💬 <b>نص الرد:</b>\n\n<b>{safe_reply}</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "💡 <b>يمكنك مراسلتنا والتواصل معنا في أي وقت عبر قسم الدعم الفني!</b>\n"
        "</blockquote>"
    )
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("💬 الرد على الإدارة", callback_data="u_support"),
        types.InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="u_main_menu")
    )
    
    try:
        if message.photo:
            bot.send_photo(target_user_id, message.photo[-1].file_id, caption=user_msg, reply_markup=markup, parse_mode='HTML')
        else:
            bot.send_message(target_user_id, user_msg, reply_markup=markup, parse_mode='HTML')
        bot.send_message(message.chat.id, f"✅ <b>تم إرسال الرد بنجاح إلى المستخدم (ID: <code>{target_user_id}</code>)!</b>", parse_mode='HTML')
        logger.info(f"✅ تم إرسال رد الدعم إلى {target_user_id}")
    except Exception as e:
        logger.error(f"فشل إرسال الرد للمستخدم {target_user_id}: {e}")
        bot.send_message(message.chat.id, f"❌ تعذر إرسال الرد للمستخدم ({e})، قد يكون قام بحظر البوت.")

def process_manual_ban(message):
    username = message.from_user.username
    user_id = message.from_user.id
    if not is_admin(user_id, username):
        return
    if not message.text:
        bot.send_message(message.chat.id, "❌ تم الإلغاء، يرجى إرسال معرف صالح.")
        return
    
    raw = message.text.strip()
    admin_tag = f"@{username}" if username else f"ID: {user_id}"
    
    if raw.isdigit():
        db.add_to_blacklist("user", raw, reason="حظر يدوي من الإدارة", blocked_by=admin_tag)
        bot.send_message(message.chat.id, f"✅ تم حظر المستخدم ذو الآيدي <code>{raw}</code> بنجاح!", parse_mode='HTML')
    else:
        chan_ref = parse_channel_ref(raw) or raw
        if not chan_ref.startswith('@') and not chan_ref.startswith('-'):
            chan_ref = f"@{chan_ref}"
        db.add_to_blacklist("channel", chan_ref, reason="حظر يدوي من الإدارة", blocked_by=admin_tag)
        bot.send_message(message.chat.id, f"✅ تم حظر القناة <code>{html.escape(chan_ref)}</code> بنجاح!", parse_mode='HTML')

def process_add_channel(message):
    username = message.from_user.username
    if not is_admin(message.from_user.id, username):
        return

    raw_input = message.text.strip()

    # استخراج اليوزر من الرابط أو المعرف
    if raw_input.startswith('https://t.me/') or raw_input.startswith('t.me/'):
        username = raw_input.split('/')[-1]
    elif raw_input.startswith('@'):
        username = raw_input
    else:
        bot.send_message(message.chat.id, "❌ يجب أن تكون على شكل:\n@username أو https://t.me/username")
        return

    # التحقق من الصيغة: @ + 1-32 حرف/رقم/_/-
    if not re.match(r'^@[a-zA-Z0-9][a-zA-Z0-9_-]{0,31}$', username):
        bot.send_message(message.chat.id, "❌ اليوزر غير صحيح. يجب أن يكون مثل:\n@my_channel أو @bac2025_combat")
        return

    if db.add_channel(username):
        bot.send_message(message.chat.id, f"✅ تم إضافة القناة `{username}` بنجاح", parse_mode='Markdown')
    else:
        bot.send_message(message.chat.id, "❌ هذه القناة موجودة مسبقاً")

def process_direct_message(message):
    username = message.from_user.username
    if not is_admin(message.from_user.id, username):
        return
    channels = db.get_all_channels()
    if not channels:
        bot.send_message(message.chat.id, "📭 لا توجد قنوات مضافة.")
        return
    
    # حفظ الرسالة مؤقتاً
    content = message.text or (message.caption or "محتوى")
    pending_id = db.save_pending_message(
        message.from_user.id,
        message.message_id,
        message.chat.id,
        "text",
        content
    )
    
    if pending_id:
        try:
            bot.copy_message(message.chat.id, message.chat.id, message.message_id)
            show_publish_targets(message.chat.id, pending_id)
        except Exception as e:
            logger.error(f"خطأ في عرض المعاينة: {e}")
            bot.send_message(message.chat.id, "❌ حدث خطأ في عرض المعاينة")
    else:
        bot.send_message(message.chat.id, "❌ حدث خطأ في حفظ الرسالة")

def process_forward_message(message):
    username = message.from_user.username
    if not is_admin(message.from_user.id, username):
        return
    if not (message.forward_from_chat or message.forward_from):
        bot.send_message(message.chat.id, "❌ يجب توجيه رسالة")
        return
    channels = db.get_all_channels()
    if not channels:
        bot.send_message(message.chat.id, "📭 لا توجد قنوات.")
        return
    
    # حفظ الرسالة مؤقتاً
    content = message.text or (message.caption or "رسالة محولة")
    pending_id = db.save_pending_message(
        message.from_user.id,
        message.message_id,
        message.chat.id,
        "forward",
        content
    )
    
    if pending_id:
        try:
            bot.forward_message(message.chat.id, message.chat.id, message.message_id)
            show_publish_targets(message.chat.id, pending_id)
        except Exception as e:
            logger.error(f"خطأ في عرض المعاينة: {e}")
            bot.send_message(message.chat.id, "❌ حدث خطأ في عرض المعاينة")
    else:
        bot.send_message(message.chat.id, "❌ حدث خطأ في حفظ الرسالة")

def process_add_admin(message):
    username = message.from_user.username
    user_id = message.from_user.id
    
    # التحقق من أن المستخدم هو المشرف الأساسي فقط
    if not is_owner(user_id):
        logger.warning(f"محاولة إضافة مشرف من مستخدم غير مصرح - user_id: {user_id}")
        bot.send_message(message.chat.id, "❌ ليس لديك صلاحية لإضافة مشرفين")
        return
    
    input_text = message.text.strip()
    user_id = None
    username_to_add = None
    
    # التحقق إذا كان المدخل رقم (معرف المستخدم)
    try:
        user_id = int(input_text)
        # محاولة الحصول على معلومات المستخدم
        try:
            user_info = bot.get_chat(user_id)
            username_to_add = user_info.username
            logger.info(f"تم الحصول على معلومات المستخدم - user_id: {user_id}, username: {username_to_add}")
        except Exception as e:
            logger.warning(f"لم يتم الحصول على معلومات المستخدم للـ user_id {user_id}: {e}")
            username_to_add = None
    except ValueError:
        # إذا لم يكن رقم، التحقق إذا كان يوزرنيم
        if input_text.startswith('@'):
            username_input = input_text
            username_to_add = username_input.lstrip('@')
            # محاولة الحصول على معلومات المستخدم من اليوزرنيم (اختياري)
            try:
                user_info = bot.get_chat(username_input)
                user_id = user_info.id
                username_to_add = user_info.username or username_to_add
                logger.info(f"تم الحصول على معلومات المستخدم من اليوزرنيم - user_id: {user_id}, username: {username_to_add}")
            except Exception as e:
                # إذا فشل الحصول على user_id، نضيف باليوزرنيم فقط
                logger.info(f"لم يتم الحصول على user_id لليوزرنيم {username_input}، سيتم إضافته باليوزرنيم فقط: {e}")
                user_id = None
        else:
            bot.send_message(message.chat.id, "❌ يجب أن يكون المعرف رقمًا أو يوزرنيم بصيغة @username")
            return
    
    # إضافة الأدمن
    if user_id or username_to_add:
        logger.info(f"محاولة إضافة مشرف - user_id: {user_id}, username: {username_to_add}")
        if db.add_admin(user_id, username_to_add):
            if user_id and username_to_add:
                bot.send_message(message.chat.id, f"✅ تم إضافة `@{username_to_add}` (ID: `{user_id}`) كمشرف", parse_mode='Markdown')
            elif user_id:
                bot.send_message(message.chat.id, f"✅ تم إضافة المشرف (ID: `{user_id}`) كمشرف", parse_mode='Markdown')
            else:
                bot.send_message(message.chat.id, f"✅ تم إضافة `@{username_to_add}` كمشرف (باليوزرنيم فقط)", parse_mode='Markdown')
        else:
            bot.send_message(message.chat.id, "⚠️ المشرف موجود مسبقاً أو حدث خطأ في الإضافة")
    else:
        bot.send_message(message.chat.id, "❌ يجب إدخال معرف المستخدم أو اليوزرنيم")

def show_publish_targets(chat_id: int, pending_id: int, menu_msg_id: int = None):
    pending = db.get_pending_message(pending_id)
    if not pending:
        bot.send_message(chat_id, "❌ لم يتم العثور على الرسالة")
        return

    message_type = pending[3]
    channels = db.get_channels_with_ids()
    if not channels:
        bot.send_message(chat_id, "📭 لا توجد قنوات مضافة.")
        return

    markup = types.InlineKeyboardMarkup()
    for pk, ch_id, ch_name in channels:
        markup.add(
            types.InlineKeyboardButton(
                _channel_button_label(ch_id, ch_name),
                callback_data=f"pubch_{pending_id}_{pk}"
            )
        )
    markup.add(
        types.InlineKeyboardButton(
            "📤 نشر في جميع القنوات",
            callback_data=f"puball_{pending_id}"
        )
    )
    if message_type == "text":
        markup.add(types.InlineKeyboardButton("✏️ تعديل", callback_data=f"preview_edit_{pending_id}"))
    markup.add(types.InlineKeyboardButton("❌ إلغاء", callback_data=f"preview_cancel_{pending_id}"))

    text = (
        "📤 *اختر وجهة النشر*\n\n"
        "اضغط اسم القناة للنشر فيها فقط، أو انشر في جميع القنوات.\n"
        "سيتم طلب التأكيد قبل الإرسال."
    )
    if menu_msg_id:
        try:
            bot.edit_message_text(text, chat_id, menu_msg_id, reply_markup=markup, parse_mode='Markdown')
            return
        except Exception as e:
            logger.warning(f"تعذر تعديل قائمة النشر: {e}")
    bot.send_message(chat_id, text, reply_markup=markup, parse_mode='Markdown')


def show_publish_confirm(chat_id: int, pending_id: int, menu_msg_id: int, channel_pk: int = None):
    markup = types.InlineKeyboardMarkup(row_width=1)
    if channel_pk is None:
        count = len(db.get_channels_with_ids())
        text = (
            "<blockquote>\n"
            "⏱️ <b>إعدادات ومدة نشر المنشور في القنوات</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            f"📢 <b>الوجهة:</b> <b>جميع القنوات المشاركة ({count} قناة)</b>\n\n"
            "👇 <b>حدد خيار النشر ومدة بقاء المنشور قبل حذفه تلقائياً:</b>\n"
            "</blockquote>\n\n"
            "👨‍💻 <b>إدارة المنصة:</b> @NEXUS_IMTIAZ"
        )
        markup.add(
            types.InlineKeyboardButton("⏱️ نشر مع حذف بعد 3 ساعات", callback_data=f"pubokall_{pending_id}_3"),
            types.InlineKeyboardButton("⏱️ نشر مع حذف بعد 6 ساعات", callback_data=f"pubokall_{pending_id}_6"),
            types.InlineKeyboardButton("⏱️ نشر مع حذف بعد 12 ساعة", callback_data=f"pubokall_{pending_id}_12"),
            types.InlineKeyboardButton("⏱️ نشر مع حذف بعد 24 ساعة", callback_data=f"pubokall_{pending_id}_24"),
            types.InlineKeyboardButton("🚀 نشر دائم (بدون حذف تلقائي)", callback_data=f"pubokall_{pending_id}_0"),
        )
    else:
        row = db.get_channel_by_pk(channel_pk)
        if not row:
            bot.send_message(chat_id, "❌ لم يتم العثور على القناة")
            return
        _, ch_id, ch_name = row
        label = _channel_button_label(ch_id, ch_name)
        text = (
            "<blockquote>\n"
            "⏱️ <b>إعدادات ومدة النشر</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            f"📢 <b>الوجهة:</b> <b>{label}</b>\n\n"
            "👇 <b>حدد خيار النشر ومدة بقاء المنشور:</b>\n"
            "</blockquote>\n\n"
            "👨‍💻 <b>إدارة المنصة:</b> @NEXUS_IMTIAZ"
        )
        markup.add(
            types.InlineKeyboardButton("⏱️ نشر مع حذف بعد 3 ساعات", callback_data=f"pubok_{pending_id}_{channel_pk}_3"),
            types.InlineKeyboardButton("⏱️ نشر مع حذف بعد 6 ساعات", callback_data=f"pubok_{pending_id}_{channel_pk}_6"),
            types.InlineKeyboardButton("⏱️ نشر مع حذف بعد 12 ساعة", callback_data=f"pubok_{pending_id}_{channel_pk}_12"),
            types.InlineKeyboardButton("⏱️ نشر مع حذف بعد 24 ساعة", callback_data=f"pubok_{pending_id}_{channel_pk}_24"),
            types.InlineKeyboardButton("🚀 نشر دائم (بدون حذف تلقائي)", callback_data=f"pubok_{pending_id}_{channel_pk}_0"),
        )

    markup.add(
        types.InlineKeyboardButton("🔙 رجوع لاختيار القنوات", callback_data=f"pubback_{pending_id}"),
        types.InlineKeyboardButton("❌ إلغاء العملية", callback_data=f"preview_cancel_{pending_id}")
    )

    try:
        bot.edit_message_text(text, chat_id, menu_msg_id, reply_markup=markup, parse_mode='HTML')
    except Exception as e:
        logger.warning(f"تعذر تعديل رسالة التأكيد: {e}")
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode='HTML')


def _channel_button_label(channel_id: str, channel_name: str = None) -> str:
    name = (channel_name or "").strip()
    if not name or name == channel_id:
        name = channel_id.lstrip('@') if channel_id else "قناة"
    if len(name) > 40:
        name = name[:37] + "..."
    return f"📢 {name}"


def show_recent_messages(chat_id: int, message_id: int = None):
    channels = db.get_all_channels()
    if not channels:
        bot.send_message(chat_id, "📭 لا توجد قنوات مضافة.")
        return

    active_sched = db.get_active_scheduled_deletion()
    sched_info = ""
    if active_sched:
        _sid, s_batch, s_del_at, s_hours, s_total, _s_cr = active_sched
        rem_sec = max(0, s_del_at - int(time.time()))
        rem_h = rem_sec // 3600
        rem_m = (rem_sec % 3600) // 60
        sched_info = (
            f"⏳ <b>هناك حذف تلقائي مجدول بعد:</b> <b>{rem_h} ساعة و {rem_m} دقيقة</b>\n"
            f"📢 <b>يشمل:</b> <b>{s_total} قناة</b> (المدة الكلية: {s_hours} ساعة)\n"
            "━━━━━━━━━━━━━━━━━━\n"
        )

    markup = types.InlineKeyboardMarkup(row_width=1)
    if active_sched:
        markup.add(
            types.InlineKeyboardButton("🛑 إلغاء الحذف التلقائي (إبقاؤه دائماً)", callback_data=f"cancel_sched_{active_sched[0]}")
        )
    
    markup.add(
        types.InlineKeyboardButton("🗑️ حذف المنشور الأخير الآن من جميع القنوات", callback_data="del_last_all")
    )
    
    for ch_id, ch_name in channels[:10]:
        markup.add(
            types.InlineKeyboardButton(
                f"🗑️ حذف من {ch_name or ch_id}",
                callback_data=f"del_onech_{ch_id}"
            )
        )
    markup.add(types.InlineKeyboardButton("❌ إلغاء", callback_data="cancel_delete"))
    
    text = (
        "<blockquote>\n"
        "🗑️ <b>إدارة وحذف المنشورات المنشورة في القنوات</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"{sched_info}"
        "👇 <b>اختر الإجراء المطلوب تنفيذه:</b>\n"
        "</blockquote>\n\n"
        "👨‍💻 <b>إدارة المنصة:</b> @NEXUS_IMTIAZ"
    )
    bot.send_message(chat_id, text, reply_markup=markup, parse_mode='HTML')


def delete_last_post_from_channel(chat_id, channel_id: str):
    row = db.get_latest_sent_for_channel(channel_id)
    if not row:
        bot.send_message(chat_id, f"📭 لا يوجد منشور لحذفه في <code>{html.escape(channel_id)}</code>", parse_mode='HTML')
        return

    row_id, mid, ch_id = row
    ok = delete_message_from_channel(ch_id, mid)
    db.delete_message_from_db(row_id)
    if ok:
        bot.send_message(chat_id, f"✅ تم حذف المنشور من <code>{html.escape(ch_id)}</code>", parse_mode='HTML')
    else:
        bot.send_message(
            chat_id,
            f"⚠️ تعذر حذف المنشور من القناة، وتمت إزالته من السجل: <code>{html.escape(ch_id)}</code>",
            parse_mode='HTML'
        )


def delete_last_post_from_all_channels(chat_id, menu_msg_id):
    batch_id = db.get_latest_batch_id()
    if batch_id is None:
        bot.send_message(chat_id, "📭 لا يوجد منشور لحذفه.")
        return

    rows = db.get_broadcast_rows(batch_id)
    if not rows:
        bot.send_message(chat_id, "📭 لا يوجد منشور لحذفه.")
        return

    deleted = 0
    failed = 0
    for row_id, mid, ch_id, _name in rows:
        if delete_message_from_channel(ch_id, mid):
            deleted += 1
        else:
            failed += 1
        db.delete_message_from_db(row_id)

    try:
        bot.delete_message(chat_id, menu_msg_id)
    except Exception:
        pass

    result_text = f"✅ تم حذف المنشور من <b>{deleted}</b> قناة"
    if failed:
        result_text += f"\n⚠️ فشل الحذف من <b>{failed}</b> قناة"
    bot.send_message(chat_id, result_text, parse_mode='HTML')


def publish_pending_to_channels(chat_id: int, pending_id: int, channel_ids: List[str], preview_msg_id: int = None, auto_delete_hours: int = 0):
    pending = db.get_pending_message(pending_id)
    if not pending:
        bot.send_message(chat_id, "❌ لم يتم العثور على الرسالة")
        return

    _user_id, message_id, original_chat_id, message_type, content = pending[:5]
    if not channel_ids:
        bot.send_message(chat_id, "📭 لا توجد قنوات مضافة.")
        db.delete_pending_message(pending_id)
        return

    success = 0
    failed = 0
    batch_id = db.new_broadcast_batch_id()

    for ch_id in channel_ids:
        try:
            if message_type == "forward":
                sent = bot.forward_message(ch_id, original_chat_id, message_id)
                db.save_sent_message(sent.message_id, ch_id, ch_id, "forward", "رسالة محولة", batch_id)
            else:
                sent = bot.copy_message(ch_id, original_chat_id, message_id)
                db.save_sent_message(sent.message_id, ch_id, original_chat_id, "text", content, batch_id)
            success += 1
        except Exception as e:
            logger.error(f"فشل في {ch_id}: {e}")
            failed += 1
        time.sleep(0.05)

    db.delete_pending_message(pending_id)
    if preview_msg_id:
        try:
            bot.delete_message(chat_id, preview_msg_id)
        except Exception:
            pass

    # إذا تم تحديد مؤقت حذف تلقائي
    if auto_delete_hours > 0 and success > 0:
        delete_at = int(time.time()) + (auto_delete_hours * 3600)
        db.save_scheduled_deletion(batch_id, delete_at, auto_delete_hours, success)
        
        from datetime import datetime, timedelta
        del_dt = datetime.now() + timedelta(hours=auto_delete_hours)
        del_time_str = del_dt.strftime("%H:%M")
        del_date_str = del_dt.strftime("%Y-%m-%d")

        result_text = (
            "<blockquote>\n"
            "🎉 <b>تم النشر بنجاح وتفعيل الجدولة التلقائية! 🚀</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            f"• ✅ <b>تم النشر في:</b> <b>{success} قناة</b>\n"
        )
        if failed > 0:
            result_text += f"• ⚠️ <b>فشل في:</b> <b>{failed} قناة</b>\n"
        result_text += (
            "━━━━━━━━━━━━━━━━━━\n"
            f"⏱️ <b>مؤقت الحذف التلقائي:</b> <b>{auto_delete_hours} ساعة</b>\n"
            f"📅 <b>موعد الحذف المبرمج:</b> <b>{del_date_str} عند الساعة {del_time_str}</b>\n"
            "💡 <b>سيتكفل البوت بحذف المنشور أوتوماتيكياً في الموعد وإشعارك فور اكتماله!</b>\n"
            "</blockquote>\n\n"
            "👨‍💻 <b>إدارة المنصة:</b> @NEXUS_IMTIAZ"
        )
    else:
        result_text = (
            "<blockquote>\n"
            "✅ <b>تم النشر الدائم بنجاح! 🚀</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            f"• ✅ <b>تم النشر في:</b> <b>{success} قناة</b>\n"
        )
        if failed > 0:
            result_text += f"• ⚠️ <b>فشل في:</b> <b>{failed} قناة</b>\n"
        result_text += (
            "━━━━━━━━━━━━━━━━━━\n"
            "📌 <b>المنشور دائم ولن يتم حذفه تلقائياً.</b>\n"
            "</blockquote>\n\n"
            "👨‍💻 <b>إدارة المنصة:</b> @NEXUS_IMTIAZ"
        )
    bot.send_message(chat_id, result_text, parse_mode='HTML')


def confirm_and_send_message(chat_id: int, pending_id: int, preview_msg_id: int):
    channels = db.get_all_channels()
    publish_pending_to_channels(
        chat_id,
        pending_id,
        [ch_id for ch_id, _ in channels],
        preview_msg_id
    )

def process_edit_message(message, pending_id: int):
    """معالجة الرسالة المعدلة"""
    username = message.from_user.username
    if not is_admin(message.from_user.id, username):
        return
    
    # حذف الرسالة المؤقتة القديمة
    db.delete_pending_message(pending_id)
    
    # حفظ الرسالة الجديدة مؤقتاً
    channels = db.get_all_channels()
    if not channels:
        bot.send_message(message.chat.id, "📭 لا توجد قنوات مضافة.")
        return
    
    content = message.text or (message.caption or "محتوى")
    new_pending_id = db.save_pending_message(
        message.from_user.id,
        message.message_id,
        message.chat.id,
        "text",
        content
    )
    
    if new_pending_id:
        try:
            bot.copy_message(message.chat.id, message.chat.id, message.message_id)
            show_publish_targets(message.chat.id, new_pending_id)
        except Exception as e:
            logger.error(f"خطأ في عرض المعاينة: {e}")
            bot.send_message(message.chat.id, "❌ حدث خطأ في عرض المعاينة")
    else:
        bot.send_message(message.chat.id, "❌ حدث خطأ في حفظ الرسالة")

# تشغيل البوت وخادم ويب Flask للاستضافة 24/7
def start_bot_polling():
    logger.info("✅ البوت يعمل بنجاح (في خيط منفصل)...")
    try:
        threading.Thread(target=run_milestones_checker_loop, daemon=True).start()
        logger.info("🚀 تم تشغيل خيط الخلفية (الحذف التلقائي للمنشورات + فحص إنجازات النمو).")
    except Exception as e:
        logger.warning(f"تعذر تشغيل خيط الخلفية: {e}")

    while True:
        try:
            bot.infinity_polling(timeout=20, long_polling_timeout=20, restart_on_change=False)
        except Exception as e:
            logger.warning(f"⚠️ إعادة محاولة اتصال تلقائية مع خوادم التيليجرام: {e}")
            time.sleep(3)

# إذا كانت Flask متوفرة ونعمل على خادم (أو تحت Gunicorn)
if HAS_FLASK:
    # بدء تشغيل خيوط البوت تلقائياً عند تحميل الكود لضمان عمله تحت Gunicorn
    bot_thread = threading.Thread(target=start_bot_polling, daemon=True)
    bot_thread.start()
else:
    bot_thread = None

if __name__ == "__main__":
    if HAS_FLASK and app:
        port = int(os.environ.get("PORT", 5000))
        try:
            app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
        except Exception as e:
            logger.warning(f"⚠️ تعذر تشغيل خادم Flask (المنفذ {port} مشغول أو غير متاح): {e}")
            logger.info("🔄 سيتم إبقاء البوت يعمل بشكل طبيعي محلياً...")
        
        # إبقاء خيط البوت الرئيسي نشطاً ومنع إغلاق التيرمينال
        if bot_thread and bot_thread.is_alive():
            bot_thread.join()
    else:
        # تشغيل البوت بشكل مباشر (Blocking) في حال عدم تنصيب Flask محلياً
        start_bot_polling()
  
    
