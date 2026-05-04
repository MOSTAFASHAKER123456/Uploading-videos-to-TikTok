import os
import time
from datetime import datetime
from patchright.sync_api import sync_playwright
import random
import sys  # ← زود السطر ده


import re

def extract_number(filename):
    numbers = re.findall(r'\d+', filename)
    return int(numbers[0]) if numbers else float('inf')


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
        print("✅ مفيش فيديوهات، البرنامج خلص")
        sys.exit(0)

    first_video = videos[0]
    VIDEO_PATH = os.path.join(VIDEO_FOLDER, first_video)
    print("🎬 الفيديو المستخدم:", first_video)

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

                    # ✅ ننقل الفيديو وبعدين نقفل
                    os.rename(VIDEO_PATH, os.path.join(DONE_FOLDER, first_video))
                    print("📁 تم نقل الفيديو لـ done")

                    page.wait_for_timeout(5000)
                    context.close()

                    print("✅ البرنامج خلص بنجاح")
                    sys.exit(0)  # ← يقفل البرنامج

                except Exception as e:
                    print("❌ فشل النشر")
                    log_error("POST_BUTTON", e, page)

            else:
                # ⚠️ مقيد أو مش واضح - ننقل ونكرر
                os.rename(VIDEO_PATH, os.path.join(DONE_FOLDER, first_video))
                print("📁 تم نقل الفيديو المقيد لـ done")

        except Exception as e:
            log_error("GENERAL_ERROR", e, page)

        finally:
            page.wait_for_timeout(5000)
            context.close()

    # 🔄 كرر مع الفيديو اللي بعده
    print("🔄 جاري المحاولة مع الفيديو التالي...")
    upload_video()


# ▶️ ابدأ
upload_video()
