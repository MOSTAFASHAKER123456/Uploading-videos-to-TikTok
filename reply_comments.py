import os, time, random, json, hashlib, requests, shutil
from datetime import datetime
from patchright.sync_api import sync_playwright

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ⚙️  إعدادات — عدّل هنا فقط
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

TIKTOK_USERNAME    = "@moshaker89"   # اسم الأكاونت
MAX_VIDEOS         = 10              # عدد الفيديوهات

TELEGRAM_TOKEN     = "."
TELEGRAM_CHAT_ID   = "."

# تأخيرات (ثواني) — عدّلها لو عايز تسرّع أو تبطّئ
DELAY_BETWEEN_COMMENTS = (3, 5)     # بين كل رد وتاني
DELAY_BETWEEN_VIDEOS   = (4, 7)     # بين كل فيديو وتاني

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)
LOGS_DIR     = os.path.join(BASE_DIR, "logs");  os.makedirs(LOGS_DIR, exist_ok=True)
REPLIED_FILE = os.path.join(BASE_DIR, "replied_comments.json")
PROFILE_DIR  = os.path.join(BASE_DIR, "tiktok_profile")

# السيليكتورات — مأخوذة من الـ HTML الفعلي
SEL_COMMENT_PANEL   = '[data-e2e="search-comment-container"]'
SEL_COMMENT_ITEM    = '[class*="DivCommentItem"]'
SEL_COMMENT_TEXT    = 'p[data-e2e="comment-level-1"]'
SEL_COMMENT_AUTHOR  = '[data-e2e="comment-username-1"]'
SEL_REPLY_BTN       = 'span[aria-label="رد"][role="button"], [data-e2e="comment-reply-1"]'
SEL_LIKE_BTN        = 'div[aria-label^="الإعجاب بفيديو"][role="button"], div[aria-label^="Like video"][role="button"]'
SEL_REPLY_INPUT     = 'div[contenteditable="true"]'


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🔧  أدوات مساعدة
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def log(msg):
    print(msg)

def notify(msg):
    """إرسال إشعار تيليجرام."""
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"},
            timeout=10
        )
    except Exception as e:
        log(f"⚠️ تيليجرام: {e}")

def load_replied():
    if os.path.exists(REPLIED_FILE):
        with open(REPLIED_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()

def save_replied(replied):
    with open(REPLIED_FILE, "w", encoding="utf-8") as f:
        json.dump(list(replied), f, ensure_ascii=False)

def get_reply_text():
    path = os.path.join(BASE_DIR, "replies.txt")
    with open(path, "r", encoding="utf-8") as f:
        lines = [l.strip() for l in f if l.strip()]
    return random.choice(lines)

def clear_cache():
    time.sleep(2)  # ← استنى الـ browser يقفل خالص
    for folder in ["Default/Cache", "Default/Code Cache", "Default/IndexedDB"]:
        p = os.path.join(PROFILE_DIR, folder)
        if os.path.exists(p):
            try:
                shutil.rmtree(p)
            except PermissionError:
                log(f"⚠️ مش قادر يمسح {folder} — هنعدي")
def comment_id(video_url, wrapper):
    """
    ID فريد وثابت لكل تعليق.
    الأولوية: id attribute الرقمي ← data-comment-id ← hash من النص والكاتب.
    مرتبط دايمًا بالـ video_url عشان نفس الشخص في فيديو تاني يتعامل معاه كتعليق جديد.
    """
    vid = video_url.rstrip("/").split("/")[-1].split("?")[0]

    for attr in ["id", "data-comment-id"]:
        try:
            val = wrapper.get_attribute(attr)
            if val and val.strip():
                return f"{vid}_{val.strip()}"
        except:
            pass

    author = text = ""
    try:
        el = wrapper.locator(SEL_COMMENT_AUTHOR).first
        if el.count(): author = el.inner_text().strip()
    except: pass
    try:
        el = wrapper.locator(SEL_COMMENT_TEXT).first
        if el.count(): text = el.inner_text().strip()[:40]
    except: pass

    return f"{vid}_{hashlib.md5(f'{author}_{text}'.encode()).hexdigest()[:12]}"

def is_sub_reply(wrapper):
    """هل الـ wrapper ده رد على تعليق (level-2) مش تعليق أصلي؟"""
    try:
        if wrapper.locator('p[data-e2e="comment-level-2"]').count(): return True
        cls = wrapper.get_attribute("class") or ""
        if "reply" in cls.lower(): return True
    except: pass
    return False


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 📋  جلب روابط الفيديوهات
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def fetch_video_urls(page, max_videos):
    url = f"https://www.tiktok.com/{TIKTOK_USERNAME}"
    log(f"\n🔍 فتح البروفايل: {url}")
    page.goto(url, wait_until="domcontentloaded")
    page.wait_for_timeout(3000)

    # scroll لتحميل الفيديوهات
    for _ in range(max(4, max_videos // 2)):
        page.mouse.wheel(0, 2000)
        page.wait_for_timeout(700)

    seen, links = set(), []
    for a in page.locator('a[href*="/video/"]').all():
        href = a.get_attribute("href") or ""
        if "/video/" not in href: continue
        if not href.startswith("http"): href = "https://www.tiktok.com" + href
        if href not in seen:
            seen.add(href)
            links.append(href)
        if len(links) >= max_videos: break

    log(f"✅ {len(links)} فيديو")
    for i, l in enumerate(links, 1): log(f"   {i}. {l}")
    return links


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 📜  تحميل كل التعليقات بـ scroll داخل الـ panel
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def load_all_comments(page):
    """
    الـ scroll بيتعمل على الـ window نفسه لما الـ cursor يكون
    فوق منطقة التعليقات على اليمين.
    """
    log("📜 تحميل التعليقات...")

    # نجيب الـ bounding box بتاع الـ comment panel مرة واحدة
    # عشان نحط الـ cursor فوقه في كل جولة
    panel_x = panel_y = None
    try:
        panel = page.locator('[data-e2e="search-comment-container"]').first
        if panel.count():
            box = panel.bounding_box()
            if box:
                panel_x = box["x"] + box["width"] / 2
                panel_y = box["y"] + box["height"] / 2
                log(f"   📍 comment panel at x={panel_x:.0f}, y={panel_y:.0f}")
    except:
        pass

    # لو مش لاقي الـ panel، نحط الـ cursor على اليمين من الشاشة
    if panel_x is None:
        viewport = page.viewport_size or {"width": 1280, "height": 720}
        panel_x  = viewport["width"] * 0.75
        panel_y  = viewport["height"] * 0.5
        log(f"   📍 fallback position x={panel_x:.0f}, y={panel_y:.0f}")

    # نحرك الـ cursor فوق التعليقات مرة واحدة
    page.mouse.move(panel_x, panel_y)
    page.wait_for_timeout(300)

    prev, streak = 0, 0
    for rnd in range(80):
        count = sum(
            1 for w in page.locator(SEL_COMMENT_ITEM).all()
            if not is_sub_reply(w)
        )
        log(f"   🔄 جولة {rnd+1}: {count} تعليق")

        if count == prev:
            streak += 1
            limit = 3 if count < 30 else 8
            if streak >= limit:
                log("   ✅ خلصوا")
                break
        else:
            streak = 0
        prev = count

        # 3 wheels في كل جولة عشان ننزل أكتر
        page.mouse.wheel(0, 800)
        page.wait_for_timeout(300)
        page.mouse.wheel(0, 800)
        page.wait_for_timeout(300)
        page.mouse.wheel(0, 800)
        page.wait_for_timeout(2000)

    total = page.locator(SEL_COMMENT_ITEM).count()
    log(f"📝 إجمالي الـ wrappers: {total}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🔍  التحقق الذكي من وجود رد سابق على TikTok
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def already_replied_on_tiktok(page, wrapper, my_username):
    """
    بيشوف لو إنت ردّيت على التعليق ده فعلاً على TikTok.
    الخطوات:
      1. يفتح الردود الموجودة (لو في زرار "View X replies")
      2. يدور على أي link يحتوي على اسمك جوا الـ replies
    يرجع True لو لقى ردك.
    """
    username = my_username.lstrip("@").lower()
    try:
        # فتح الردود لو في زرار "View X replies"
        for btn_sel in [
            'p[data-e2e^="view-more-replies"]',
            'span[data-e2e^="view-more-replies"]',
            '[class*="SpanViewReply"]',
            'p[data-e2e^="comment-reply-count"]',
        ]:
            btn = wrapper.locator(btn_sel).first
            if btn.count():
                btn.click()
                page.wait_for_timeout(1000)
                break

        # ✅ طريقة 1: دور على username في ردود المستوى التاني
        # ردودك بتظهر كـ data-e2e="comment-username-2"
        for sel in ['[data-e2e^="comment-username-2"]', '[data-e2e^="comment-username"]']:
            for el in wrapper.locator(sel).all():
                name = (el.inner_text() or "").strip().lower()
                if name == username or name == my_username.lower():
                    return True

        # ✅ طريقة 2: دور على links باسمك جوا الـ wrapper
        for link in wrapper.locator('a[href*="/@"]').all():
            href = (link.get_attribute("href") or "").lower()
            if f"/@{username}" in href:
                return True

    except:
        pass
    return False


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ❤️  لايك على تعليق
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def do_like(page, wrapper):
    try:
        btn = wrapper.locator(SEL_LIKE_BTN).first
        if btn.count() == 0:
            log("   ⚠️ زرار اللايك مش موجود")
            return
        if btn.get_attribute("aria-pressed") == "true":
            log("   ❤️ عمله لايك قبل كده")
            return
        btn.scroll_into_view_if_needed()
        btn.click(force=True)
        log("   ❤️ لايك ✓")
        page.wait_for_timeout(400)
    except Exception as e:
        log(f"   ⚠️ فشل اللايك: {e}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 💬  الرد على تعليق
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def do_reply(page, wrapper, reply_text):
    """
    يرد على تعليق معين.
    الخطوات: hover ← زرار الرد ← إيجاد input الرد ← كتابة ← Enter.
    يرجع True لو نجح.
    """

    # 1) hover عشان تظهر الأزرار
    try:
        wrapper.scroll_into_view_if_needed()
        page.wait_for_timeout(300)
        wrapper.hover()
        page.wait_for_timeout(500)
    except: pass

    # 2) زرار الرد
    reply_btn = None
    for sel in SEL_REPLY_BTN.split(", "):
        btn = wrapper.locator(sel.strip()).first
        if btn.count():
            reply_btn = btn
            break

    if reply_btn is None:
        log("   ❌ مش لاقي زرار الرد")
        return False

    try:
        reply_btn.wait_for(state="visible", timeout=4000)
        reply_btn.click(force=True)
        page.wait_for_timeout(1000)
    except Exception as e:
        log(f"   ❌ فشل الضغط على رد: {e}")
        return False

    # 3) إيجاد الـ reply input
    # بنعد الـ inputs قبل وبعد الضغط عشان نعرف الجديد
    page.wait_for_timeout(600)
    reply_input = None

    all_inputs = page.locator(SEL_REPLY_INPUT).all()
    for inp in all_inputs:
        try:
            described = inp.get_attribute("aria-describedby") or ""
            if described:
                ph = page.locator(f"#{described}")
                if ph.count():
                    ph_text = ph.inner_text().lower()
                    if "reply" in ph_text or "رد" in ph_text or "add a reply" in ph_text:
                        reply_input = inp
                        break
        except: continue

    # fallback: آخر input ظهر
    if reply_input is None:
        reply_input = page.locator(SEL_REPLY_INPUT).last

    # 4) كتابة الرد
    try:
        reply_input.click(force=True)
        page.wait_for_timeout(300)

        # مسح أي نص موجود
        reply_input.evaluate("el => el.innerText = ''")
        page.wait_for_timeout(200)

        for char in reply_text:
            page.keyboard.type(char)
            time.sleep(0.018)

        page.wait_for_timeout(500)
        page.keyboard.press("Enter")
        log(f"   ✅ رد: {reply_text}")
        page.wait_for_timeout(1200)
        return True

    except Exception as e:
        log(f"   ❌ فشل الكتابة: {e}")
        return False


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🔒  إغلاق reply input لو فضل مفتوح
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def close_reply_box(page):
    """
    بعد كل رد، بنتأكد إن الـ reply box اتقفل.
    الـ minimum الطبيعي = 1 input (صندوق التعليق الرئيسي).
    لو في أكتر من 1 يبقى الـ reply box لسه مفتوح.
    """
    for _ in range(6):
        if page.locator(SEL_REPLY_INPUT).count() <= 1:
            break
        page.keyboard.press("Escape")
        page.wait_for_timeout(250)
        page.mouse.click(600, 200)
        page.wait_for_timeout(250)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🎬  معالجة فيديو واحد
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def process_video(page, video_url, replied):
    log(f"\n{'━'*50}")
    log(f"🎬 {video_url}")

    # فتح الفيديو — networkidle عشان TikTok يحمل الـ JS كامل
    page.goto(video_url, wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(2000)

    # انتظار ظهور أيقونة التعليقات — بنجرب كل الـ selectors المعروفة
    icon = None
    for sel in [
        '[data-e2e="browse-comment-icon"]',
        '[data-e2e="comment-icon"]',
        'button[aria-label*="comment"]',
        'button[aria-label*="تعليق"]',
    ]:
        try:
            el = page.locator(sel).first
            el.wait_for(state="visible", timeout=8000)
            icon = el
            log(f"💬 لقينا أيقونة التعليقات: {sel}")
            break
        except:
            continue

    if icon is None:
        log("⚠️ مش لاقي أيقونة التعليقات — هنعدي")
        return 0

    # ضغط على الأيقونة وانتظار ظهور أول تعليق فعلاً
    icon.click()

    found = False
    for sel in ['[class*="DivCommentItem"]']:
        try:
            page.wait_for_selector(sel, timeout=10000)
            found = True
            log("✅ التعليقات اتحملت")
            break
        except:
            continue

    if not found:
        # ممكن الأيقونة تكون اتضغطت بس التعليقات فاضية
        log("⚠️ مفيش تعليقات في الفيديو ده")
        return 0

    # تحميل كل التعليقات
    load_all_comments(page)

    # جمع الـ IDs قبل ما نبدأ
    all_items    = page.locator(SEL_COMMENT_ITEM).all()
    comment_ids  = []
    seen_ids     = set()

    for idx, w in enumerate(all_items):
        if is_sub_reply(w): continue
        cid = comment_id(video_url, w)
        if cid not in seen_ids:
            seen_ids.add(cid)
            comment_ids.append(cid)

    total = len(comment_ids)
    log(f"📋 {total} تعليق أصلي")

    replied_count = 0

    for num, cid in enumerate(comment_ids, 1):

        # Check 1: محفوظ محلياً (سريع)
        if cid in replied:
            log(f"⏭️  [{num}/{total}] محفوظ محلياً — هنعدي")
            continue

        # إيجاد الـ wrapper الحالي بالـ ID
        target = None
        for idx, w in enumerate(page.locator(SEL_COMMENT_ITEM).all()):
            if is_sub_reply(w): continue
            if comment_id(video_url, w) == cid:
                target = w
                break

        if target is None:
            log(f"⚠️  [{num}/{total}] مش لاقي التعليق في الـ DOM")
            continue

        # طباعة معلومات التعليق
        author = text = ""
        try:
            el = target.locator(SEL_COMMENT_AUTHOR).first
            if el.count(): author = el.inner_text().strip()
        except: pass
        try:
            el = target.locator(SEL_COMMENT_TEXT).first
            if el.count(): text = el.inner_text().strip()
        except: pass

        log(f"\n💬 [{num}/{total}] @{author or '?'}: {text[:45] or '(sticker)'}")

        # Check 2: رد موجود على TikTok فعلاً (يشمل الردود اليدوية)
        if already_replied_on_tiktok(page, target, TIKTOK_USERNAME):
            log(f"   ✅ رد موجود على TikTok — هنحفظه ونعدي")
            replied.add(cid)
            save_replied(replied)
            continue

        # إغلاق أي reply box مفتوح من قبل
        close_reply_box(page)

        # لايك
        do_like(page, target)

        # رد
        reply_text = get_reply_text()
        success    = do_reply(page, target, reply_text)

        # إغلاق الـ reply box بعد الرد
        close_reply_box(page)

        if success:
            replied.add(cid)
            save_replied(replied)
            replied_count += 1
            time.sleep(random.uniform(*DELAY_BETWEEN_COMMENTS))
        else:
            log("   ⚠️ فشل الرد — هنكمل على التاني")

    log(f"\n📊 ردود على الفيديو ده: {replied_count}/{total}")
    return replied_count


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🚀  الدالة الرئيسية
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def main():
    log("=" * 50)
    log("🤖 اسكربت إسراء — الرد على التعليقات")
    log(f"📹 فيديوهات: {MAX_VIDEOS}")
    log("=" * 50)

    replied = load_replied()
    log(f"📂 ردود محفوظة: {len(replied)}")

    total_new = 0

    with sync_playwright() as pw:
        ctx  = pw.chromium.launch_persistent_context(
            PROFILE_DIR,
            headless=False,
            args=["--disable-blink-features=AutomationControlled"]
        )
        page = ctx.new_page()

        try:
            videos = fetch_video_urls(page, MAX_VIDEOS)

            if not videos:
                log("❌ مش لاقي فيديوهات")
                notify("❌ <b>اسكربت إسراء:</b> مش لاقي فيديوهات")
                return

            for i, url in enumerate(videos, 1):
                log(f"\n{'='*50}")
                log(f"▶️  فيديو {i}/{len(videos)}")
                count    = process_video(page, url, replied)
                total_new += count
                if i < len(videos):
                    time.sleep(random.uniform(*DELAY_BETWEEN_VIDEOS))

        except Exception as e:
            log(f"❌ خطأ عام: {e}")
            notify(f"❌ <b>اسكربت إسراء وقع!</b>\n{str(e)[:200]}")

        finally:
            ctx.close()
            time.sleep(3)
            clear_cache()

    log(f"\n✅ خلصنا! إجمالي ردود جديدة: {total_new}")
    notify(
        f"✅ <b>اسكربت إسراء خلص</b>\n"
        f"💬 ردود جديدة: <b>{total_new}</b>\n"
        f"🎬 فيديوهات: <b>{MAX_VIDEOS}</b>"
    )


if __name__ == "__main__":
    main()
