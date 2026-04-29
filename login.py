import os
os.chdir(os.path.dirname(os.path.abspath(__file__)))
from patchright.sync_api import sync_playwright

# 📁 فولدر حفظ الجلسة
USER_DATA_DIR = "tiktok_profile"

os.makedirs(USER_DATA_DIR, exist_ok=True)

with sync_playwright() as p:
    # 🔥 مهم جدًا: persistent context
    context = p.chromium.launch_persistent_context(
        USER_DATA_DIR,
        headless=False
    )

    page = context.new_page()

    # 🌐 افتح TikTok
    page.goto("https://www.tiktok.com")

    print("👉 سجل دخول يدوي من المتصفح...")

    # ⏱️ سيبك مفتوح وقت كفاية للتسجيل
    page.wait_for_timeout(120000)  # دقيقة

    print("✅ تم حفظ الجلسة في البروفايل")

    context.close()