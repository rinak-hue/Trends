import asyncio
import json
import os
from datetime import datetime
import httpx
from bs4 import BeautifulSoup

# ============================================================
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN_TRENDS", "ВСТАВЬ_СВОЙ_ТОКЕН")
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
TELEGRAM_CHAT_IDS = ["248752467"]

NICHE_TOPICS = [
    # Русские
    "путешествия с ребенком",
    "мама в путешествии",
    "зимовка с малышом",
    "материнство за границей",
    "жизнь в Сербии",
    "материнство в европе",
    "жизнь в азии с семьей",
    "мама мальчика",
    "it мама",
    # Английские
    "travel with baby",
    "mom travel",
    "expat mom",
    "traveling with infant",
    "it mother",
    "mother of boy",
]

# Хэштеги на основе ниши
NICHE_HASHTAGS = [
    "#travelwithbaby", "#momtravel", "#babytravel",
    "#expatlife", "#digitalnomadmom", "#travelingmom",
    "#babytravels", "#familytravel", "#momabroad",
    "#путешествиясребенком", "#материнство", "#жизньзаграницей",
    "#мамавпутешествии", "#зимовкасмалышом", "#материнствозаграницей",
    "#жизньвсербии", "#итмама", "#mamablogger",
    "#motherofboy", "#mamaboy", "#expatmom",
]

SEND_HOUR_UTC = 7  # 09:00 Белград = 07:00 UTC
# ============================================================

async def send_telegram(text: str, chat_id: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    async with httpx.AsyncClient(timeout=15) as client:
        try:
            await client.post(url, json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True
            })
        except Exception as e:
            print(f"Ошибка отправки: {e}")

async def send_all(text: str):
    for chat_id in TELEGRAM_CHAT_IDS:
        await send_telegram(text, chat_id)
        await asyncio.sleep(0.3)

async def call_claude(prompt: str, max_tokens: int = 1000) -> str:
    """Универсальный вызов Claude API"""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            },
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}]
            }
        )
        data = resp.json()
        return data["content"][0]["text"]

# ──────────────────────────────────────────────
# 1. GOOGLE TRENDS — через веб-поиск
# ──────────────────────────────────────────────
async def fetch_google_trends() -> list:
    """Трендовые темы через поиск Google Trends RSS"""
    trends = []
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            # Google Trends RSS — работает без API ключа
            for geo in ["RU", "US"]:
                resp = await client.get(
                    f"https://trends.google.com/trends/trendingsearches/daily/rss?geo={geo}",
                    headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
                )
                soup = BeautifulSoup(resp.text, "lxml-xml")
                items = soup.find_all("item")
                for item in items[:5]:
                    title = item.find("title")
                    traffic = item.find("ht:approx_traffic")
                    if title:
                        t = title.get_text(strip=True)
                        tr = traffic.get_text(strip=True) if traffic else ""
                        trends.append(f"{t} {tr}".strip())
                await asyncio.sleep(0.5)
    except Exception as e:
        print(f"Ошибка Google Trends RSS: {e}")

    return trends[:8]

# ──────────────────────────────────────────────
# 2. YOUTUBE
# ──────────────────────────────────────────────
async def fetch_youtube_trends() -> list:
    if not YOUTUBE_API_KEY:
        return []
    videos = []

    # Ротация тем по дню недели — каждый день разные запросы
    day_of_week = datetime.now().weekday()  # 0=пн, 6=вс
    topic_groups = [
        ["путешествия с ребенком", "travel with baby", "baby travel tips"],
        ["мама в путешествии", "mom travel vlog", "traveling mom"],
        ["зимовка с малышом", "expat mom life", "living abroad baby"],
        ["материнство за границей", "digital nomad mom", "expat family"],
        ["жизнь в Сербии", "life in Serbia expat", "Belgrade family"],
        ["it мама", "it mother remote work", "work from home mom baby"],
        ["мама мальчика", "mother of boy", "boy mom travel"],
    ]
    todays_topics = topic_groups[day_of_week % len(topic_groups)]

    # Последние 14 дней — свежие видео
    from datetime import timedelta
    published_after = (datetime.utcnow() - timedelta(days=14)).strftime("%Y-%m-%dT00:00:00Z")

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            for topic in todays_topics:
                for order in ["date", "viewCount"]:
                    params = {
                        "part": "snippet",
                        "q": topic,
                        "type": "video",
                        "order": order,
                        "publishedAfter": published_after,
                        "maxResults": 2,
                        "key": YOUTUBE_API_KEY,
                        "videoDuration": "short",  # короткие видео = рилсы
                    }
                    resp = await client.get(
                        "https://www.googleapis.com/youtube/v3/search",
                        params=params
                    )
                    data = resp.json()
                    for item in data.get("items", []):
                        title = item.get("snippet", {}).get("title", "")
                        video_id = item.get("id", {}).get("videoId", "")
                        channel = item.get("snippet", {}).get("channelTitle", "")
                        published = item.get("snippet", {}).get("publishedAt", "")[:10]
                        if title and video_id:
                            videos.append({
                                "title": title,
                                "url": f"https://youtu.be/{video_id}",
                                "channel": channel,
                                "published": published,
                                "topic": topic,
                            })
                    await asyncio.sleep(0.3)
    except Exception as e:
        print(f"Ошибка YouTube: {e}")

    seen, unique = set(), []
    for v in videos:
        if v["url"] not in seen:
            seen.add(v["url"])
            unique.append(v)
    return unique[:8]

# ──────────────────────────────────────────────
# 3. ХЭШТЕГИ — фиксированные + AI обновление
# ──────────────────────────────────────────────
async def fetch_hashtags() -> list:
    base = NICHE_HASHTAGS

    if not ANTHROPIC_API_KEY:
        return base

    try:
        today = datetime.now().strftime("%B %Y")
        result = await call_claude(
            f"Какие 5 трендовых Instagram хэштегов сейчас ({today}) для блогера в нише: путешествия с ребёнком, IT-мама, мама мальчика, материнство за границей (Сербия, Азия, Европа), зимовка с малышом? "
            f"Ответь ТОЛЬКО списком хэштегов через пробел, без объяснений. Пример: #tag1 #tag2 #tag3",
            max_tokens=100
        )
        ai_tags = [t.strip() for t in result.split() if t.startswith("#")]
        return ai_tags + base[:6] if ai_tags else base
    except Exception as e:
        print(f"Ошибка hashtags AI: {e}")
        return base

# ──────────────────────────────────────────────
# 4. PINTEREST — через Claude AI
# ──────────────────────────────────────────────
async def fetch_pinterest_trends() -> list:
    month = datetime.now().month
    season = {12:"зима",1:"зима",2:"зима",3:"весна",4:"весна",5:"весна",
               6:"лето",7:"лето",8:"лето",9:"осень",10:"осень",11:"осень"}.get(month,"весна")

    if not ANTHROPIC_API_KEY:
        return [
            {"category": "✈️ Путешествия", "ideas": ["Baby travel essentials", "Flying with infant", "Travel with stroller"]},
            {"category": "👶 Материнство", "ideas": ["Mom life abroad", "Baby milestones", "Expat family"]},
            {"category": "🎨 Визуал", "ideas": ["Soft aesthetic reels", "Golden hour baby", "Pastel tones content"]},
        ]

    try:
        result = await call_claude(
            f"Сейчас {season} 2026. Блогер: путешествия + материнство + Сербия, малыш 9 месяцев.\n"
            f"Дай 9 трендовых Pinterest-тем для её контента. JSON без markdown:\n"
            f'{{\"travel\": [\"тема1\", \"тема2\", \"тема3\"], \"motherhood\": [\"тема1\", \"тема2\", \"тема3\"], \"aesthetic\": [\"тема1\", \"тема2\", \"тема3\"]}}',
            max_tokens=300
        )
        text = result.strip()
        if "```" in text:
            text = text.split("```")[1].replace("json", "").strip()
        parsed = json.loads(text)
        return [
            {"category": "✈️ Путешествия", "ideas": parsed.get("travel", [])},
            {"category": "👶 Материнство", "ideas": parsed.get("motherhood", [])},
            {"category": "🎨 Визуал", "ideas": parsed.get("aesthetic", [])},
        ]
    except Exception as e:
        print(f"Ошибка Pinterest AI: {e}")
        return [
            {"category": "✈️ Путешествия", "ideas": ["Baby travel essentials", "Flying with infant", "Travel with stroller"]},
            {"category": "👶 Материнство", "ideas": ["Mom life abroad", "Baby milestones travel", "Expat mom life"]},
            {"category": "🎨 Визуал", "ideas": ["Soft aesthetic content", "Golden hour reels", "Pastel spring tones"]},
        ]

# ──────────────────────────────────────────────
# 5. ИДЕИ ДЛЯ РИЛСОВ через Claude
# ──────────────────────────────────────────────
async def generate_reels_ideas(videos: list, trends: list, pinterest: list) -> str:
    if not ANTHROPIC_API_KEY:
        return (
            "1. 🎬 Эмоциональный контраст\n"
            "Начало: «9 месяцев я боялась путешествовать...»\n\n"
            "2. 🎬 Практичный совет\n"
            "Начало: «3 вещи в самолёт с ребёнком»\n\n"
            "3. 🎬 День из жизни\n"
            "Начало: «Утро в Белграде с малышом»\n\n"
            "4. 🎬 Вопрос-ответ\n"
            "Начало: «Как я путешествую с ребёнком одна?»\n\n"
            "5. 🎬 Лайфхак\n"
            "Начало: «Как уложить малыша в незнакомом месте»"
        )

    today = datetime.now().strftime("%d %B %Y")
    yt = "\n".join([f"- {v['title'][:60]}" for v in videos[:4]]) or "нет данных"
    tr = "\n".join([f"- {t}" for t in trends[:5]]) or "нет данных"
    pin = "\n".join([f"- {p['category']}: {', '.join(p['ideas'][:2])}" for p in pinterest]) or "нет данных"

    try:
        result = await call_claude(
            f"Сегодня {today}. Помоги блогеру @katekorostyleva придумать 5 идей для рилсов.\n\n"
            f"Ниша: путешествия + материнство + жизнь в Сербии. Малыш 9 месяцев.\n\n"
            f"YouTube тренды:\n{yt}\n\n"
            f"Google тренды:\n{tr}\n\n"
            f"Pinterest темы:\n{pin}\n\n"
            f"Для каждой идеи напиши:\n"
            f"- Цепляющее начало (первые 2 секунды)\n"
            f"- Формат\n"
            f"- Хук для описания\n\n"
            f"Идеи должны быть разными каждый день и учитывать актуальные тренды выше. Пиши на русском.",
            max_tokens=1000
        )
        return result
    except Exception as e:
        print(f"Ошибка ideas AI: {e}")
        return "Идеи временно недоступны — проверь ANTHROPIC_API_KEY"

# ──────────────────────────────────────────────
# СБОРКА ДАЙДЖЕСТА
# ──────────────────────────────────────────────
async def send_digest():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Собираю дайджест...")

    trends, videos, hashtags, pinterest = await asyncio.gather(
        fetch_google_trends(),
        fetch_youtube_trends(),
        fetch_hashtags(),
        fetch_pinterest_trends(),
    )

    print(f"Trends:{len(trends)} YT:{len(videos)} Tags:{len(hashtags)} Pin:{len(pinterest)}")

    ideas = await generate_reels_ideas(videos, trends, pinterest)

    today = datetime.now().strftime("%d.%m.%Y")
    msg = f"🌅 <b>Утренний дайджест — {today}</b>\n\n"

    msg += "📈 <b>Google Trends:</b>\n"
    msg += ("\n".join(f"• {t}" for t in trends[:5])) if trends else "• Данные недоступны"
    msg += "\n\n"

    msg += "📺 <b>YouTube в нише:</b>\n"
    msg += ("\n".join(f"• <a href='{v['url']}'>{v['title'][:55]}...</a>" for v in videos[:4])) if videos else "• Данные недоступны"
    msg += "\n\n"

    msg += "🎵 <b>Хэштеги:</b>\n"
    msg += " ".join(hashtags[:10])
    msg += "\n\n"

    msg += "📌 <b>Pinterest тренды:</b>\n"
    for p in pinterest:
        msg += f"<b>{p['category']}</b>: {' · '.join(p['ideas'])}\n"

    await send_all(msg)
    await asyncio.sleep(1)
    await send_all(f"💡 <b>5 идей для рилсов на {today}:</b>\n\n{ideas}")
    print("Дайджест отправлен!")

# ──────────────────────────────────────────────
# КОМАНДЫ И ПЛАНИРОВЩИК
# ──────────────────────────────────────────────
async def poll_commands():
    offset = None
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
    async with httpx.AsyncClient(timeout=30) as client:
        while True:
            try:
                params = {"timeout": 10}
                if offset:
                    params["offset"] = offset
                resp = await client.get(url, params=params)
                for update in resp.json().get("result", []):
                    offset = update["update_id"] + 1
                    msg = update.get("message", {})
                    chat_id = str(msg.get("chat", {}).get("id", ""))
                    text = msg.get("text", "").strip()
                    if chat_id not in TELEGRAM_CHAT_IDS:
                        continue
                    if text == "/digest":
                        await send_telegram("🔄 Собираю дайджест...", chat_id)
                        asyncio.create_task(send_digest())
                    elif text == "/status":
                        await send_telegram(
                            f"⚙️ <b>Trends Bot</b>\n"
                            f"Дайджест: каждый день в 09:00 (Белград)\n"
                            f"Google Trends: ✅\n"
                            f"YouTube: {'✅' if YOUTUBE_API_KEY else '❌ нет ключа'}\n"
                            f"Pinterest AI: {'✅' if ANTHROPIC_API_KEY else '❌ нет ключа'}\n"
                            f"Идеи AI: {'✅' if ANTHROPIC_API_KEY else '❌ нет ключа'}\n\n"
                            f"/digest — дайджест прямо сейчас\n"
                            f"/status — этот экран",
                            chat_id
                        )
            except Exception as e:
                print(f"Ошибка polling: {e}")
                await asyncio.sleep(5)

async def main():
    await send_all(
        "✅ <b>Trends Bot v2 запущен!</b>\n"
        "Каждое утро в 09:00 (Белград):\n\n"
        "📈 Google Trends\n"
        "📺 YouTube топ в нише\n"
        "🎵 Трендовые хэштеги\n"
        "📌 Pinterest тренды (AI)\n"
        "💡 5 уникальных идей для рилсов (AI)\n\n"
        "/digest — получить прямо сейчас\n"
        "/status — статус"
    )

    async def scheduler():
        while True:
            now = datetime.utcnow()
            if now.hour == SEND_HOUR_UTC and now.minute == 0:
                await send_digest()
                await asyncio.sleep(61)
            await asyncio.sleep(30)

    await asyncio.gather(scheduler(), poll_commands())

if __name__ == "__main__":
    asyncio.run(main())


