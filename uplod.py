import os
import time
from datetime import datetime
from patchright.sync_api import sync_playwright
import random




# 📁 نفس فولدر السكربت
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)

# 📁 فولدر اللوجات
LOG_DIR = os.path.join(BASE_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)

def log_error(step, error, page=None):
    """يسجل الخطأ + screenshot"""
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    # ملف النص
    log_file = os.path.join(LOG_DIR, f"error_{timestamp}.txt")
    with open(log_file, "w", encoding="utf-8") as f:
        f.write(f"STEP: {step}\n")
        f.write(str(error) + "\n")

    # screenshot لو الصفحة موجودة
    if page:
        try:
            screenshot_path = os.path.join(LOG_DIR, f"error_{timestamp}.png")
            page.screenshot(path=screenshot_path)
        except:
            pass


# 🎬 مسار الفيديو

VIDEO_FOLDER = os.path.join(BASE_DIR, "scrapit esraa") #الفولد اللى فيه الفديوها 
videos = [f for f in os.listdir(VIDEO_FOLDER) if f.endswith(".mp4")]

if not videos:
    raise Exception("❌ مفيش فيديوهات في الفولدر")

first_video = videos[0]

VIDEO_PATH = os.path.join(VIDEO_FOLDER, first_video)
print("🎬 الفيديو المستخدم:", first_video)
# VIDEO_PATH = os.path.abspath("__$$161$$__(love) $sarsora$.mp4") هنا كنت بختار يدوى اللى فوق بشكل اتوماتك


with sync_playwright() as p:

    context = p.chromium.launch_persistent_context(
        "tiktok_profile",
        headless=False
    )

    page = context.new_page()

    try:
        # 1️⃣ فتح الصفحة
        page.goto("https://www.tiktok.com/tiktokstudio/upload")
        page.wait_for_timeout(8000)

        # 2️⃣ رفع الفيديو
        try:
            page.set_input_files('input[type="file"]', VIDEO_PATH)
            print("📤 تم رفع الفيديو")
        except Exception as e:
            print("❌ فشل رفع الفيديو")
            log_error("UPLOAD_VIDEO", e, page)

        # 3️⃣ كتابة الكابشن
        try:
            caption = page.locator('div[contenteditable="true"]').first
            caption.click()
            page.keyboard.press("Home")

            #كتابة عنوان بشكل عشوائى من ملف التكست
            with open("title.txt", "r", encoding="utf-8") as f:
                captions = [line.strip() for line in f if line.strip()]

            
            random_caption = random.choice(captions)

            page.keyboard.type(random_caption + " ")
            print("✍️ تم كتابة الكابشن")
        except Exception as e:
            print("⚠️ مشكلة في الكابشن")
            log_error("CAPTION", e, page)

        # 4️⃣ انتظار فحص المحتوى
        try:
            page.locator('.status-success').wait_for(state="visible", timeout=500000)
            print("✅ انتهى فحص المحتوى")
        except Exception as e:
            print("⚠️ الفحص لم يكتمل")
            log_error("CONTENT_CHECK", e, page)

        # 5️⃣ زر النشر
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

            print("✅ زر النشر جاهز")

        except Exception as e:
            print("⚠️ زر النشر غير جاهز")
            log_error("POST_BUTTON_READY", e, page)

        # 6️⃣ النشر
        try:
            post_btn.click()
            print("🚀 تم الضغط على زر النشر")
        except Exception as e:
            print("❌ مشكلة في النشر")
            log_error("POST_CLICK", e, page)

        # ⏳ انتظار بعد النشر
        page.wait_for_timeout(15000)



        DONE_FOLDER = os.path.join(BASE_DIR, "done")
        os.makedirs(DONE_FOLDER, exist_ok=True)

        os.rename(VIDEO_PATH, os.path.join(DONE_FOLDER, first_video))
    except Exception as e:
        log_error("GENERAL_ERROR", e, page)

    finally:
        context.close()