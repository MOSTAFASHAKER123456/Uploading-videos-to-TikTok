import os
import time
import random
import json
import hashlib
import requests
import shutil
from datetime import datetime
from patchright.sync_api import sync_playwright

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ⚙️ إعدادات التحكم — عدّل هنا بس
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

TIKTOK_USERNAME    = "@moshaker89"
MAX_VIDEOS         = 10

TELEGRAM_BOT_TOKEN = "8507544252:AAE_JXek3Q3YWuI_1k-xrg1zZukWiIOLX7s"
TELEGRAM_CHAT_ID   = "1902127631"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)

LOG_DIR = os.path.join(BASE_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)

REPLIED_FILE = os.path.join(BASE_DIR, "replied_comments.json")

WRAPPER = '[class*="DivCommentItemWrapper"]'


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🔧 وظائف مساعدة
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def send_telegram_message(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            print("📨 تم إرسال رسالة تيليجرام")
        else:
            print(f"⚠️ فشل إرسال تيليجرام: {response.text}")
    except Exception as e:
        print(f"❌ خطأ في تيليجرام: {e}")


def log_error(step, error, page=None):
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_file = os.path.join(LOG_DIR, f"error_{timestamp}.txt")
    with open(log_file, "w", encoding="utf-8") as f:
        f.write(f"STEP: {step}\n")
        f.write(str(error) + "\n")
    if page:
        try:
            page.screenshot(
                path=os.path.join(LOG_DIR, f"error_{timestamp}.png"),
                full_page=True
            )
        except:
            pass


def load_replied():
    if os.path.exists(REPLIED_FILE):
        with open(REPLIED_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()


def save_replied(replied_set):
    with open(REPLIED_FILE, "w", encoding="utf-8") as f:
        json.dump(list(replied_set), f, ensure_ascii=False)


def get_random_reply():
    replies_file = os.path.join(BASE_DIR, "replies.txt")
    with open(replies_file, "r", encoding="utf-8") as f:
        replies = [line.strip() for line in f if line.strip()]
    return random.choice(replies)


def clean_browser_cache():
    profile_path = os.path.join(BASE_DIR, "tiktok_profile")
    for folder in ["Default/Cache", "Default/Code Cache", "Default/IndexedDB"]:
        full_path = os.path.join(profile_path, folder)
        if os.path.exists(full_path):
            shutil.rmtree(full_path)
            print(f"🗑️ تم مسح {folder}")
    print("✅ تم تنظيف الكاش")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🔑 استخراج comment_id ثابت ومرتبط بالفيديو
#
# القاعدة الأساسية:
#   video_id دايمًا جزء من الـ ID
#   ← نفس الشخص في فيديو تاني = ID مختلف = هيترد عليه ✓
#   ← نفس التعليق في نفس الفيديو = ID ثابت = مش هيترد تاني ✓
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def get_stable_comment_id(wrapper, video_url, index):
    # استخراج video_id من الـ URL
    # مثال: https://www.tiktok.com/@x/video/7123456789 → "7123456789"
    video_id = video_url.rstrip("/").split("/")[-1].split("?")[0]

    # محاولة 1: video_id + data-comment-id
    try:
        cid = wrapper.get_attribute("data-comment-id")
        if cid:
            return f"v{video_id}_c{cid}"
    except:
        pass

    # محاولة 2: video_id + id attribute
    try:
        elem_id = wrapper.get_attribute("id")
        if elem_id:
            return f"v{video_id}_id{elem_id}"
    except:
        pass

    # محاولة 3: fallback — video_id + author + أول 20 حرف من النص
    author = ""
    text_prefix = ""
    try:
        author_el = wrapper.locator('a[data-e2e^="comment-username"]').first
        if author_el.count() > 0:
            author = author_el.inner_text().strip()
    except:
        pass

    try:
        text_el = wrapper.locator('p[data-e2e^="comment-level"]').first
        if text_el.count() > 0:
            text_prefix = text_el.inner_text().strip()[:20]
    except:
        pass

    unique_str = f"{video_id}_{author}_{text_prefix}"
    return f"v{video_id}_hash{hashlib.md5(unique_str.encode()).hexdigest()}"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🔒 إغلاق أي reply input مفتوح
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def close_open_inputs(page):
    for attempt in range(10):
        count = page.locator('div[contenteditable="true"]').count()
        if count <= 1:
            print(f"   ✅ inputs مقفولة (متبقي: {count})")
            return True
        print(f"   📌 inputs متبقية: {count} — محاولة إغلاق {attempt+1}")
        page.keyboard.press("Escape")
        page.wait_for_timeout(300)
        page.mouse.click(400, 80)
        page.wait_for_timeout(300)
        page.mouse.wheel(0, -100)
        page.wait_for_timeout(300)

    print("   ⚠️ فضل input مفتوح — هنكمل برغم ده")
    return False


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 📋 جلب الفيديوهات من البروفايل
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def get_videos(page, profile_url, max_videos):
    print(f"🔍 بنجيب آخر {max_videos} فيديوهات من: {profile_url}")
    page.goto(profile_url)
    page.wait_for_timeout(4000)

    scroll_times = max(3, max_videos // 2)
    for _ in range(scroll_times):
        page.mouse.wheel(0, 2000)
        page.wait_for_timeout(800)

    video_links = []
    seen = set()

    for anchor in page.locator('a[href*="/video/"]').all():
        href = anchor.get_attribute("href")
        if href and "/video/" in href:
            if href.startswith("/"):
                href = "https://www.tiktok.com" + href
            if href not in seen:
                seen.add(href)
                video_links.append(href)
        if len(video_links) >= max_videos:
            break

    print(f"✅ لقينا {len(video_links)} فيديو")
    for i, link in enumerate(video_links):
        print(f"   {i+1}. {link}")

    return video_links


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ❤️ لايك على تعليق
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def like_comment(page, wrapper):
    try:
        like_btn = wrapper.locator('div[aria-label^="Like video"][role="button"]').first

        if like_btn.count() == 0:
            print("   ⚠️ مش لاقي زرار اللايك")
            return False

        try:
            is_liked = like_btn.get_attribute("aria-pressed")
            if is_liked == "true":
                print("   ❤️ اتعمله لايك قبل كده — هنعدى")
                return False
        except:
            pass

        like_btn.scroll_into_view_if_needed()
        like_btn.click(force=True)
        print("   ❤️ تم اللايك ✓")
        page.wait_for_timeout(500)
        return True

    except Exception as e:
        print(f"   ⚠️ فشل اللايك: {e}")
        return False


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🔍 هل الـ wrapper ده رد (level-2)؟
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def is_reply_wrapper(wrapper):
    try:
        e2e = wrapper.get_attribute("data-e2e") or ""
        if "level-2" in e2e:
            return True
        if wrapper.locator('p[data-e2e="comment-level-2"]').count() > 0:
            return True
        class_attr = wrapper.get_attribute("class") or ""
        if "reply" in class_attr.lower() or "Reply" in class_attr:
            return True
    except:
        pass
    return False


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 💬 الرد على تعليقات فيديو واحد + لايك
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def reply_to_video_comments(page, video_url, replied):
    print(f"\n🎬 فتح الفيديو: {video_url}")

    if "?" not in video_url:
        video_url += "?is_from_webapp=1"

    page.goto(video_url)
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(3000)

    new_replies_count = 0

    # =========================
    # 1) فتح التعليقات
    # =========================
    try:
        opened = False
        for selector in ['[data-e2e="comment-icon"]', '[data-e2e="browse-comment-icon"]']:
            icon = page.locator(selector).first
            if icon.count() > 0:
                icon.wait_for(state="visible", timeout=8000)
                icon.click()
                opened = True
                print("💬 تم فتح التعليقات")
                break
        if not opened:
            print("⚠️ مش لاقي أيقونة التعليقات")
            return 0
        page.wait_for_timeout(2500)
    except Exception as e:
        print(f"⚠️ فشل فتح التعليقات: {e}")
        return 0

    # =========================
    # 2) انتظار تحميل التعليقات
    # =========================
    try:
        page.wait_for_selector(WRAPPER, timeout=12000)
        print("✅ التعليقات اتحملت")
    except:
        print("⚠️ مفيش تعليقات")
        return 0

    for _ in range(3):
        try:
            comment_panel = page.locator('[class*="DivCommentListContainer"]').first
            comment_panel.evaluate("el => el.scrollBy(0, 800)")
        except:
            page.mouse.wheel(0, 800)
        page.wait_for_timeout(900)

    # =========================
    # 3) Snapshot للـ IDs قبل ما نبدأ
    #
    # ✅ الإصلاحان معاً هنا:
    #
    # إصلاح 1 — مش بيرد على نفس الشخص في فيديو تاني:
    #   الـ ID بيبدأ دايمًا بـ video_id
    #   ← نفس الشخص في فيديو مختلف = video_id مختلف = ID مختلف = هيترد ✓
    #
    # إصلاح 2 — بيرد على ناس اترد عليهم فعلاً:
    #   الـ ID ثابت لنفس التعليق في نفس الفيديو
    #   ← لو موجود في replied = يعدّيه بدون رد ✓
    # =========================
    all_wrappers = page.locator(WRAPPER).all()
    original_comment_ids = []

    for idx, w in enumerate(all_wrappers):
        if is_reply_wrapper(w):
            continue
        cid = get_stable_comment_id(w, video_url, idx)
        original_comment_ids.append(cid)

    total_original = len(original_comment_ids)
    print(f"📝 تعليقات أصلية (level-1): {total_original}")

    if total_original == 0:
        print("⚠️ مش لاقي تعليقات أصلية")
        return 0

    # =========================
    # 4) Loop على الـ IDs مش على index رقمي
    # =========================
    for comment_num, comment_id in enumerate(original_comment_ids):

        if comment_id in replied:
            print(f"⏭️ [{comment_num+1}/{total_original}] اترد عليه قبل كده — هنعدى")
            continue

        # إعادة جمع الـ wrappers بعد كل رد لأن الـ DOM اتغير
        current_wrappers = page.locator(WRAPPER).all()

        target_wrapper = None
        for idx, w in enumerate(current_wrappers):
            if is_reply_wrapper(w):
                continue
            wid = get_stable_comment_id(w, video_url, idx)
            if wid == comment_id:
                target_wrapper = w
                break

        if target_wrapper is None:
            print(f"⚠️ [{comment_num+1}/{total_original}] مش لاقي الـ wrapper — ID: {comment_id[:30]}")
            continue

        # استخراج النص واسم الكاتب للطباعة
        text   = ""
        author = ""
        try:
            text_el = target_wrapper.locator('p[data-e2e^="comment-level"]').first
            if text_el.count() > 0:
                text = text_el.inner_text().strip()
        except:
            pass

        try:
            author_el = target_wrapper.locator('a[data-e2e^="comment-username"]').first
            if author_el.count() > 0:
                author = author_el.inner_text().strip()
        except:
            pass

        if not text:
            text = f"(no_text_{comment_num})"

        print(f"\n💬 [{comment_num+1}/{total_original}] @{author}: {text[:50]}")

        target_wrapper.scroll_into_view_if_needed()
        page.wait_for_timeout(400)

        close_open_inputs(page)
        target_wrapper.hover()
        page.wait_for_timeout(600)

        # =========================
        # 5) ❤️ لايك
        # =========================
        like_comment(page, target_wrapper)

        # =========================
        # 6) زر الرد
        # =========================
        reply_btn = target_wrapper.locator('p[role="button"][aria-label="Reply"]').first
        if reply_btn.count() == 0:
            reply_btn = target_wrapper.locator('[data-e2e^="comment-reply"]').first

        try:
            reply_btn.wait_for(state="visible", timeout=4000)
            reply_btn.click(force=True)
            print("👉 تم الضغط على رد")
            page.wait_for_timeout(1200)
        except Exception as e:
            print(f"❌ زر الرد مش ظاهر: {e}")
            continue

        # =========================
        # 7) إيجاد الـ reply input
        # =========================
        reply_text  = get_random_reply()
        reply_input = None

        page.wait_for_timeout(800)

        for inp in page.locator('div[contenteditable="true"]').all():
            try:
                describedby = inp.get_attribute("aria-describedby") or ""
                if describedby:
                    placeholder_el = page.locator(f"#{describedby}")
                    if placeholder_el.count() > 0:
                        placeholder_text = placeholder_el.inner_text()
                        print(f"   placeholder: '{placeholder_text}'")
                        if "reply" in placeholder_text.lower() or "رد" in placeholder_text:
                            reply_input = inp
                            print("✅ لقينا reply input")
                            break
            except:
                continue

        if reply_input is None:
            print("⚠️ fallback: هناخد آخر input")
            reply_input = page.locator('div[contenteditable="true"]').last

        # =========================
        # 8) الكتابة والإرسال
        # =========================
        try:
            reply_input.click(force=True)
            page.wait_for_timeout(400)

            print(f"📌 النص الحالي: '{reply_input.inner_text().strip()[:50]}'")

            for char in reply_text:
                page.keyboard.type(char)
                time.sleep(0.02)

            page.wait_for_timeout(600)
            page.keyboard.press("Enter")
            print(f"✅ تم الرد: {reply_text}")

            page.wait_for_timeout(1500)

            close_open_inputs(page)

            # ✅ حفظ الـ ID — مرتبط بالفيديو ده بالتحديد
            replied.add(comment_id)
            save_replied(replied)
            new_replies_count += 1

            time.sleep(random.uniform(3, 5))

        except Exception as e:
            print(f"⚠️ فشل الكتابة: {e}")
            close_open_inputs(page)

    return new_replies_count


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🚀 الدالة الرئيسية
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def run_comment_bot():
    PROFILE_URL = f"https://www.tiktok.com/{TIKTOK_USERNAME}"

    print("=" * 50)
    print("🤖 اسكربت الرد على التعليقات - اسكربت إسراء")
    print(f"📹 عدد الفيديوهات: {MAX_VIDEOS}")
    print("=" * 50)

    replied = load_replied()
    print(f"📂 تعليقات محفوظة (اترد عليها قبل كده): {len(replied)}")

    total_replies = 0

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context("tiktok_profile", headless=False)
        page = context.new_page()

        try:
            video_urls = get_videos(page, PROFILE_URL, MAX_VIDEOS)

            if not video_urls:
                print("❌ مش لاقي فيديوهات!")
                send_telegram_message("❌ <b>اسكربت التعليقات:</b> مش لاقي فيديوهات في البروفايل")
                return

            for video_url in video_urls:
                count = reply_to_video_comments(page, video_url, replied)
                total_replies += count
                print(f"📊 ردود على الفيديو ده: {count}")
                time.sleep(random.uniform(3, 6))

        except Exception as e:
            print(f"❌ خطأ عام: {e}")
            log_error("GENERAL_ERROR", e, page)
            send_telegram_message(f"❌ <b>اسكربت التعليقات وقع!</b>\n{str(e)[:200]}")

        finally:
            page.wait_for_timeout(3000)
            context.close()
            clean_browser_cache()

    print(f"\n✅ خلصنا! إجمالي الردود الجديدة: {total_replies}")
    send_telegram_message(
        f"من اسكربت إسراء\n"
        f"✅ <b>اسكربت التعليقات خلص!</b>\n"
        f"💬 <b>إجمالي ردود جديدة:</b> {total_replies}\n"
        f"🎬 <b>عدد الفيديوهات:</b> {MAX_VIDEOS}"
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
run_comment_bot()
