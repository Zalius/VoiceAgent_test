import psycopg2
from psycopg2.extras import RealDictCursor
import os
import logging
import json
from datetime import datetime

logger = logging.getLogger("db-manager")
logger.setLevel(logging.INFO)


class DatabaseManager:
    """مدیریت اتصال و عملیات پایگاه داده PostgreSQL"""

    def __init__(self):
        self.connection_params = {
            'host': os.getenv('DB_HOST', 'localhost'),
            'port': os.getenv('DB_PORT', '5432'),
            'database': os.getenv('DB_NAME', 'interview_db'),
            'user': os.getenv('DB_USER', 'postgres'),
            'password': os.getenv('DB_PASSWORD', '')
        }
        logger.info("✅ DatabaseManager initialized")

    def get_connection(self):
        """ایجاد اتصال جدید به پایگاه داده"""
        try:
            conn = psycopg2.connect(**self.connection_params)
            return conn
        except Exception as e:
            logger.error(f"❌ خطا در اتصال به DB: {e}")
            raise

    def execute_query(self, query: str, params: tuple = None, fetch_one: bool = False):
        """اجرای یک query و بازگشت نتیجه"""
        conn = None
        try:
            conn = self.get_connection()
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(query, params)
                
                if query.strip().upper().startswith('SELECT'):
                    if fetch_one:
                        return cursor.fetchone()
                    return cursor.fetchall()
                else:
                    conn.commit()
                    return True
                    
        except Exception as e:
            logger.error(f"❌ خطا در اجرای query: {e}")
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                conn.close()

    def get_interview_settings(self, settings_id: int = 1) -> dict:
        """
        دریافت تنظیمات مصاحبه از DB با استفاده از id
        
        Args:
            settings_id: ID ردیف تنظیمات (معمولاً 1)
        
        Returns:
            دیکشنری شامل تمام تنظیمات + سوالات
        """
        try:
            # دریافت تنظیمات اصلی
            settings_query = """
                SELECT 
                    company_id,
                    interview_field,
                    include_hr,
                    include_technical,
                    voice,
                    language,
                    strictness_level,
                    conversation_flow
                FROM interview_settings
                WHERE id = %s
            """
            
            result = self.execute_query(settings_query, (settings_id,), fetch_one=True)
            
            if not result:
                logger.warning(f"⚠️ تنظیماتی با ID={settings_id} پیدا نشد.")
                return self._get_default_settings()
            
            company_id = result['company_id']
            interview_field = result['interview_field']  # 🔥 فیلد مصاحبه
            
            # 🔥 دریافت سوالات HR (فقط سوالاتی که ask=True و field مطابق باشد)
            hr_questions = []
            if result['include_hr']:
                hr_query = """
                    SELECT question_text 
                    FROM custom_hr_questions 
                    WHERE company_id = %s 
                    AND ask = TRUE
                    AND (field = %s OR field IS NULL OR field = '')
                    ORDER BY order_index
                """
                hr_results = self.execute_query(hr_query, (company_id, interview_field))
                hr_questions = [row['question_text'] for row in hr_results]
            
            # 🔥 دریافت سوالات فنی (فقط سوالاتی که ask=True و field مطابق باشد)
            tech_questions = []
            if result['include_technical']:
                tech_query = """
                    SELECT question_text 
                    FROM custom_technical_questions 
                    WHERE company_id = %s 
                    AND ask = TRUE
                    AND (field = %s OR field IS NULL OR field = '')
                    ORDER BY order_index
                """
                tech_results = self.execute_query(tech_query, (company_id, interview_field))
                tech_questions = [row['question_text'] for row in tech_results]
            
            settings = {
                'company_id': company_id,
                'company_name': company_id.title(),
                'interview_field': interview_field,
                'include_hr': result['include_hr'],
                'include_technical': result['include_technical'],
                'voice': result['voice'],
                'language': result['language'],
                'strictness_level': result['strictness_level'],
                'conversation_flow': result['conversation_flow'],
                'hr_questions': hr_questions,
                'technical_questions': tech_questions
            }
            
            logger.info(f"✅ تنظیمات بارگذاری شد:")
            logger.info(f"   Company: {company_id}")
            logger.info(f"   Field: {interview_field}")
            logger.info(f"   HR Questions (filtered): {len(hr_questions)}")
            logger.info(f"   Tech Questions (filtered): {len(tech_questions)}")
            
            return settings
            
        except Exception as e:
            logger.error(f"❌ خطا در دریافت تنظیمات: {e}")
            return self._get_default_settings()


    def _get_default_settings(self) -> dict:
        """تنظیمات پیش‌فرض در صورت خطا"""
        return {
            'company_id': 'ontime',
            'company_name': 'OnTime',
            'interview_field': 'Data Science',
            'include_hr': True,
            'include_technical': True,
            'voice': 'alloy',
            'language': 'persian',
            'strictness_level': 'medium',
            'conversation_flow': 'greeting,company_introduction,hr_interview,technical_interview,closing',
            'hr_questions': [
                "چرا می‌خواهید در این شرکت کار کنید؟",
                "نقاط قوت و ضعف خود را توضیح دهید.",
            ],
            'technical_questions': [
                "با چه ابزارهای تحلیل داده آشنایی دارید؟",
                "یک پروژه تحلیل داده که انجام داده‌اید را شرح دهید.",
            ]
        }

    def save_interview_session(
        self, 
        session_id: str,
        settings_id: int,
        candidate_name: str,
        transcript: str,
        evaluation: dict,
        metadata: dict
    ):
        """
        ذخیره نشست مصاحبه در DB
        
        Args:
            session_id: شناسه یکتای جلسه
            settings_id: ID تنظیمات استفاده شده
            candidate_name: نام کاندیدا
            transcript: متن کامل مکالمه (JSON string)
            evaluation: نتیجه ارزیابی (dict)
            metadata: اطلاعات اضافی (dict)
        """
        try:
            query = """
                INSERT INTO interview_sessions 
                (session_id, settings_id, candidate_name, transcript, evaluation, metadata, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            
            params = (
                session_id,
                settings_id,
                candidate_name,
                transcript,  # JSON string
                json.dumps(evaluation, ensure_ascii=False),
                json.dumps(metadata, ensure_ascii=False),
                datetime.now()
            )
            
            self.execute_query(query, params)
            logger.info(f"✅ Session {session_id} ذخیره شد در DB")
            
        except Exception as e:
            logger.error(f"❌ خطا در ذخیره session: {e}")
            # این خطا را raise نکن تا Agent crash نکند
