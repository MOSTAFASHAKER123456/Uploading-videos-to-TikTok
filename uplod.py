import os
import time
from datetime import datetime
from patchright.sync_api import sync_playwright
import random
import sys
import re
import requests
import subprocess


def extract_number(filename):
    numbers = re.findall(r'\d+', filename)
    return int(numbers[0]) if numbers else float('inf')

# ✅ إعدادات تيليجرام
TELEGRAM_BOT_TOKEN = "8507544252:AAE_JXek3Q3YWuI_1k-xrg1zZukWiIOLX7s"
TELEGRAM_CHAT_ID = "1902127631"

def send_telegram_message(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML"
        }
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            print("📨 تم إرسال رسالة تيليجرام")
        else:
            print(f"⚠️ فشل إرسال تيليجرام: {response.text}")
    except Exception as e:
        print(f"❌ خطأ في تيليجرام: {e}")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)

LOG_DIR = os.path.join(BASE_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)

def log_error(step, error, page=None):
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_file = os.path.join(LOG_DIR, f"error_{timestamp}.txt")
    with open(log_file, "w", encoding="utf-8") as f:
        f.write(f"STEP: {step}\n")
        f.write(str(error) + "\n")
    if page:
        try:
            screenshot_path = os.path.join(LOG_DIR, f"error_{timestamp}.png")
            page.screenshot(path=screenshot_path, full_page=True)
        except:
            pass

DONE_FOLDER = os.path.join(BASE_DIR, "done")
os.makedirs(DONE_FOLDER, exist_ok=True)
VIDEO_FOLDER = os.path.join(BASE_DIR, "Videos")


def upload_video():
    videos = sorted(
        [f for f in os.listdir(VIDEO_FOLDER) if f.endswith(".mp4")],
        key=extract_number
    )

    if not videos:
        print("❌ مفيش فيديوهات، هنشغل الـ exe")

        exe_path = os.path.join(VIDEO_FOLDER, "Script repeat 24.exe")

        # تشغيل exe مع argument (غيره حسب احتياجك)
        subprocess.run([exe_path],input='1\n',text=True)
        print("✅ الـ exe خلص، بنعيد الفحص...")

        # نعيد قراءة الفولدر تاني بعد ما الـ exe يخلص
        videos = sorted(
            [f for f in os.listdir(VIDEO_FOLDER) if f.endswith(".mp4")],
            key=extract_number
        )

        if not videos:
            print("❌ لسه مفيش فيديوهات، هنقفل")
            sys.exit(0)

    # هنا كده فيه فيديوهات خلاص
    first_video = videos[0]
    VIDEO_PATH = os.path.join(VIDEO_FOLDER, first_video)

    print("🎬 الفيديو المستخدم:", first_video)

    should_repeat = True

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            "tiktok_profile",
            headless=False
        )
        page = context.new_page()

        try:
            page.goto("https://www.tiktok.com/tiktokstudio/upload")
            page.wait_for_timeout(8000)

            try:
                page.set_input_files('input[type="file"]', VIDEO_PATH)
                print("📤 تم رفع الفيديو")
            except Exception as e:
                print("❌ فشل رفع الفيديو")
                log_error("UPLOAD_VIDEO", e, page)

            try:
                caption = page.locator('div[contenteditable="true"]').first
                caption.click()
                page.keyboard.press("Home")

                with open("title.txt", "r", encoding="utf-8") as f:
                    captions = [line.strip() for line in f if line.strip()]

                random_caption = random.choice(captions)
                page.keyboard.type(random_caption + " ")
                print("✍️ تم كتابة الكابشن")

                time.sleep(20)
                for _ in range(6):
                    page.mouse.wheel(0, 3000)
                    page.wait_for_timeout(300)

            except Exception as e:
                print("⚠️ مشكلة في الكابشن")
                log_error("CAPTION", e, page)

            should_post = False

            try:
                page.wait_for_function("""
                () => {
                    const success = document.querySelector('.status-success[data-show="true"]');
                    const restricted = document.body.innerText.includes('Content may be restricted');
                    return success || restricted;
                }
                """, timeout=300000)

                if page.locator('.status-success[data-show="true"]').count() > 0:
                    print("✅ انتهى فحص المحتوى - الفيديو سليم")
                    should_post = True

                elif "Content may be restricted" in page.content():
                    print("⚠️ الفيديو مقيد - هيتنقل وهيبدأ الفيديو اللي بعده")
                    log_error("CONTENT_RESTRICTED", "Video flagged as restricted", page)
                    should_post = False

                else:
                    print("⏳ الفحص لم يكتمل - سيتم تخطي النشر")
                    log_error("CONTENT_UNKNOWN", "No clear status after wait", page)
                    should_post = False

            except Exception as e:
                print("❌ خطأ في الفحص")
                log_error("CONTENT_CHECK", e, page)
                should_post = False

            posted_successfully = False

            if should_post:
                try:
                    post_btn = page.locator('[data-e2e="post_video_button"]')
                    post_btn.wait_for(state="visible", timeout=500000)

                    page.wait_for_function("""
                    () => {
                        const btn = document.querySelector('[data-e2e="post_video_button"]');
                        if (!btn) return false;
                        const style = window.getComputedStyle(btn);
                        return !btn.disabled && style.pointerEvents !== 'none';
                    }
                    """, timeout=500000)

                    post_btn.click()
                    print("🚀 تم نشر الفيديو بنجاح")
                    posted_successfully = True

                except Exception as e:
                    print("❌ فشل النشر")
                    log_error("POST_BUTTON", e, page)

            # ✅ نقل الفيديو بره أي try/except
            if posted_successfully or not should_post:
                dest_path = os.path.join(DONE_FOLDER, first_video)
                try:
                    if os.path.exists(dest_path):
                        os.remove(VIDEO_PATH)
                        print("📁 الفيديو موجود في done مسبقاً - تم حذفه من Videos")
                    else:
                        os.rename(VIDEO_PATH, dest_path)
                        print("📁 تم نقل الفيديو لـ done")
                except Exception as e:
                    print(f"⚠️ خطأ في نقل الفيديو: {e}")

                if posted_successfully:
                    send_telegram_message(
                        f"✅ <b>تم نشر الفيديو بنجاح!</b>\n"
                        f"📹 <b>اسم الفيديو:</b> {first_video}"
                    )

                should_repeat = False

        except Exception as e:
            log_error("GENERAL_ERROR", e, page)

        finally:
            page.wait_for_timeout(5000)
            context.close()

    if should_repeat:
        print("🔄 جاري المحاولة مع الفيديو التالي...")
        upload_video()
    else:
        if not posted_successfully:
            print("🔄 جاري تجربة الفيديو التالي...")
            upload_video()
        else:
            print("✅ البرنامج خلص بنجاح")
            sys.exit(0)


upload_video()
