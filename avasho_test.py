import requests
import json
import sys
from playsound3 import playsound
from dotenv import load_dotenv
import os


# ---------------------- ENV SETUP ----------------------
load_dotenv(".env")

API_URL = "https://partai.gw.isahab.ir/avasho/v2/avasho/request"
GATEWAY_TOKEN = os.getenv("AVASHO_GATEWAY_TOKEN")

# Voices:
#  Male: kiani, nourai, dara, parviz, bahman, farhad, shahriyar, ariya 
#  Female: sara, pune, bahar, shahrzad, sheyda, shirin


def generate_tts(text, speaker="shahrzad", speed=1, timestamp=True):
    """ارسال متن به سرویس و دریافت لینک فایل صوتی"""
    payload = {
        "text": text,
        "speaker": speaker,
        "speed": speed,
        "timestamp": timestamp
    }

    headers = {
        "gateway-token": GATEWAY_TOKEN,
        "accept": "application/json",
        "Content-Type": "application/json"
    }

    response = requests.post(API_URL, headers=headers, data=json.dumps(payload))

    if response.status_code == 201:
        result = response.json()
        try:
            url = result["data"]["data"]["aiResponse"]["result"]["filename"]
            print(f"✅ لینک فایل گفتار تولید شد:\n{url}")
            return url
        except KeyError:
            print("❌ خطا در ساختار پاسخ، کلید filename یافت نشد.")
    else:
        print(f"🚫 درخواست ناموفق بود ({response.status_code}):")
        print(response.text)
    return None


def download_and_play(audio_url):
    """دانلود فایل از لینک و پخش در کنسول"""
    r = requests.get(audio_url)
    if r.status_code == 200:
        filename = "avasho_output.mp3"
        with open(filename, "wb") as f:
            f.write(r.content)
        print(f"🎵 فایل با موفقیت ذخیره شد: {filename}")

        # پخش صدا در کنسول (با playsound)
        print("▶️ در حال پخش گفتار...")
        playsound(filename)
    else:
        print(f"⚠️ دانلود ناموفق بود ({r.status_code}): {audio_url}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "console":
        sample_text = "اینشتین از همکاران مؤسسه مطالعات پیشرفته در دانشگاه پرینستون در شهر نیوجرسی بود که تا پایان عمرش در سال ۱۹۵۵ نیز این همکاری را حفظ کرد. او بیش از ۳۰۰ مقاله علمی و ۱۵۰ مقاله غیرعلمی منتشر کرد. دستاوردهای فکری و جدید او موجب شد که نام اینشتین در فرهنگ عامه معادلی برای هوش و نبوغ محسوب شود."

        
        audio_link = generate_tts(sample_text)
        if audio_link:
            download_and_play(audio_link)
    else:
        print("Usage: python avasho.py console")
