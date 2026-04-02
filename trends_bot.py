import asyncio
import json
import os
from datetime import datetime
import httpx
from bs4 import BeautifulSoup

# ============================================================
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN_TRENDS", "ВСТАВЬ_СВОЙ_ТОКЕН")
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY", "ВСТАВЬ_YOUTUBE_КЛЮЧ")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
TELEGRAM_CHAT_IDS = ["248752467"]

# Ниша блогера — темы для поиска трендов
NICHE_TOPICS = [
    "путешествия с ребенком",
    "мама в путешествии",
    "зимовка с малышом",
    "материнство за границей",
    "жизнь в Сербии",
    "travel with baby",
    "mom travel",
    "expat mom",
    "traveling with infant",
    "материнство в грузии",
    "материнство в европе",
    "it мама",
    "it mother",
    "жизнь в азии с семьей",
    "мама мальчика",
    "mother of boy"
]

# Время отправки дайджеста (час по UTC, 9:00 Belgrade = 7:00 UTC)
SEND_HOUR_UTC = 7

# ============================================================

async def send_telegram(text: str, chat_id: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    async with httpx.AsyncClient() as client:
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

async def fetch_google_trends() -> list:
    """Получаем трендовые запросы через pytrends-совместимый endpoint"""
    trends = []
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            # Trending searches Russia/Worldwide
            for geo in ["RU", ""]:
                url = "https://trends.google.com/trends/api/dailytrends"
                params = {"hl": "ru", "tz": -180, "geo": geo, "ns": 15}
                resp = await client.get(url, params=params)
                # Google возвращает с префиксом )]}'\n
                text = resp.text
                if ")]}'" in text:
                    text = text.split(")]}'\n", 1)[1]
                data = json.loads(text)
                items = data.get("default", {}).get("trendingSearchesDays", [])
                for day in items[:1]:
                    for item in day.get("trendingSearches", [])[:5]:
                        title = item.get("title", {}).get("query", "")
                        traffic = item.get("formattedTraffic", "")
                        if title:
                            trends.append(f"{title} ({traffic})")
                await asyncio.sleep(1)
    except Exception as e:
        print(f"Ошибка Google Trends: {e}")

    return trends[:10]

async def fetch_youtube_trends() -> list:
    """Топ видео в нише через YouTube Data API"""
    videos = []
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            for topic in NICHE_TOPICS[:4]:
                params = {
                    "part": "snippet",
                    "q": topic,
                    "type": "video",
                    "order": "viewCount",
                    "publishedAfter": "2026-03-26T00:00:00Z",
                    "maxResults": 3,
                    "key": YOUTUBE_API_KEY,
                    "relevanceLanguage": "ru",
                }
                resp = await client.get(
                    "https://www.googleapis.com/youtube/v3/search",
                    params=params
                )
                data = resp.json()
                for item in data.get("items", []):
                    title = item.get("snippet", {}).get("title", "")
                    channel = item.get("snippet", {}).get("channelTitle", "")
                    video_id = item.get("id", {}).get("videoId", "")
                    if title and video_id:
                        videos.append({
                            "title": title,
                            "channel": channel,
                            "url": f"https://youtu.be/{video_id}",
                            "topic": topic
                        })
                await asyncio.sleep(0.5)
    except Exception as e:
        print(f"Ошибка YouTube: {e}")

    # Дедупликация
    seen = set()
    unique = []
    for v in videos:
        if v["url"] not in seen:
            seen.add(v["url"])
            unique.append(v)
    return unique[:8]

async def fetch_tiktok_trends() -> list:
    """Трендовые хэштеги с TikTok Creative Center"""
    hashtags = []
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            # TikTok Creative Center — публичная страница трендов
            resp = await client.get(
                "https://ads.tiktok.com/business/creativecenter/trends/hashtag/pad/en",
                headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
            )
            soup = BeautifulSoup(resp.text, "html.parser")
            # Ищем хэштеги на странице
            tags = soup.find_all(string=lambda t: t and t.startswith("#"))
            for tag in tags[:15]:
                tag = tag.strip()
                if len(tag) > 2 and tag not in hashtags:
                    hashtags.append(tag)
    except Exception as e:
        print(f"Ошибка TikTok: {e}")

    # Если не нашли — возвращаем популярные хэштеги ниши
    if not hashtags:
        hashtags = [
            "#travelwithbaby", "#momtravel", "#babytravel",
            "#expatlife", "#digitalnomadmom", "#travelingmom",
            "#babytravels", "#familytravel", "#momabroad",
            "#materinstvo", "#путешествиясребенком"
        ]
    return hashtags[:10]

async def fetch_pinterest_trends() -> list:
    """Генерируем Pinterest-style тренды через Claude API или фиксированный список"""
    month = datetime.now().month
    season_map = {
        12: "зима", 1: "зима", 2: "зима",
        3: "весна", 4: "весна", 5: "весна",
        6: "лето", 7: "лето", 8: "лето",
        9: "осень", 10: "осень", 11: "осень",
    }
    season = season_map.get(month, "весна")

    if ANTHROPIC_API_KEY:
        try:
            prompt = f"""Ты эксперт по Pinterest трендам. Сейчас {season}, апрель 2026 года.

Блогер @katekorostyleva: путешествия + материнство + жизнь в Сербии, малыш 9 месяцев.

Назови 9 трендовых Pinterest-тем для её ниши прямо сейчас. Сгруппируй по 3 темы в 3 категории:
1. Путешествия с малышом
2. Материнство и лайфстайл  
3. Эстетика и визуал

Для каждой темы дай короткое название (3-5 слов) на английском как Pinterest-запрос.
Отвечай ТОЛЬКО в формате JSON без markdown:
{{"travel": ["тема1", "тема2", "тема3"], "motherhood": ["тема1", "тема2", "тема3"], "aesthetic": ["тема1", "тема2", "тема3"]}}"""

            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={{
                        "x-api-key": ANTHROPIC_API_KEY,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json"
                    }},
                    json={{
                        "model": "claude-sonnet-4-20250514",
                        "max_tokens": 300,
                        "messages": [{{"role": "user", "content": prompt}}]
                    }}
                )
                data = resp.json()
                text = data["content"][0]["text"].strip()
                parsed = json.loads(text)
                return [
                    {{"query": "✈️ Путешествия с малышом", "ideas": parsed.get("travel", [])}},
                    {{"query": "👶 Материнство и лайфстайл", "ideas": parsed.get("motherhood", [])}},
                    {{"query": "🎨 Эстетика и визуал", "ideas": parsed.get("aesthetic", [])}},
                ]
        except Exception as e:
            print(f"Ошибка Pinterest AI: {{e}}")

    # Fallback — сезонные темы
    seasonal = {{
        "зима": [
            {{"query": "✈️ Путешествия с малышом", "ideas": ["Winter baby travel", "Baby beach holiday", "Warm country with infant"]}},
            {{"query": "👶 Материнство и лайфстайл", "ideas": ["Winter baby activities", "Cozy mom life", "Baby winter outfits"]}},
            {{"query": "🎨 Эстетика и визуал", "ideas": ["Warm tones winter", "Cozy aesthetic reels", "Golden hour baby photos"]}},
        ],
        "весна": [
            {{"query": "✈️ Путешествия с малышом", "ideas": ["Spring travel baby", "Europe with infant", "City walks with stroller"]}},
            {{"query": "👶 Материнство и лайфстайл", "ideas": ["Spring mom outfits", "Baby spring activities", "Outdoor baby play"]}},
            {{"query": "🎨 Эстетика и визуал", "ideas": ["Soft spring aesthetic", "Pastel reels", "Blooming city photos"]}},
        ],
        "лето": [
            {{"query": "✈️ Путешествия с малышом", "ideas": ["Beach baby travel", "Summer family trip", "Pool with infant"]}},
            {{"query": "👶 Материнство и лайфстайл", "ideas": ["Summer mom life", "Baby beach day", "Outdoor dining baby"]}},
            {{"query": "🎨 Эстетика и визуал", "ideas": ["Golden hour summer", "Blue tones aesthetic", "Summer reels vibe"]}},
        ],
        "осень": [
            {{"query": "✈️ Путешествия с малышом", "ideas": ["Autumn city travel", "Fall family trip", "Europe autumn baby"]}},
            {{"query": "👶 Материнство и лайфстайл", "ideas": ["Fall mom outfits", "Baby autumn walk", "Cozy family home"]}},
            {{"query": "🎨 Эстетика и визуал", "ideas": ["Warm autumn tones", "Orange aesthetic reels", "Fall vibes content"]}},
        ],
    }}
    return seasonal.get(season, seasonal["весна"])

async def generate_reels_ideas(youtube_videos: list, trends: list, pinterest: list = []) -> str:
    """Генерируем идеи для рилсов через Claude API"""
    if not ANTHROPIC_API_KEY:
        return generate_ideas_fallback(youtube_trends=youtube_videos, trends=trends)

    try:
        youtube_titles = "\n".join([f"- {v['title']}" for v in youtube_videos[:5]])
        trend_list = "\n".join([f"- {t}" for t in trends[:5]])

        pinterest_str = chr(10).join([f"- {p['query']}: {', '.join(p['ideas'][:2])}" for p in pinterest[:3]])
        prompt = f"""Ты помогаешь Instagram-блогеру @katekorostyleva придумывать идеи для рилсов.

Её ниша: путешествия + материнство + жизнь в Сербии. У неё малыш 9 месяцев. Она много путешествует и живёт за рубежом.

Сегодняшние тренды в YouTube по её теме:
{youtube_titles}

Трендовые поисковые запросы:
{trend_list}

Трендовые идеи с Pinterest:
{pinterest_str}

Придумай 5 конкретных идей для рилсов. Для каждой идеи напиши:
1. Цепляющее начало (первые 2 секунды)
2. Формат (эмоциональный контраст / практичный совет / день из жизни / вопрос-ответ)
3. Хук для описания

Пиши коротко и конкретно. Отвечай на русском."""

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
                    "max_tokens": 1000,
                    "messages": [{"role": "user", "content": prompt}]
                }
            )
            data = resp.json()
            return data["content"][0]["text"]
    except Exception as e:
        print(f"Ошибка Claude API: {e}")
        return generate_ideas_fallback(youtube_videos, trends)

def generate_ideas_fallback(youtube_trends: list, trends: list) -> str:
    """Запасные идеи если Claude API недоступен"""
    return """💡 Идеи для рилсов на сегодня:

1. 🎬 Эмоциональный контраст
Начало: "9 месяцев я боялась путешествовать с малышом..."
Формат: до/после, ожидание vs реальность

2. 🎬 Практичный совет
Начало: "3 вещи которые я беру в самолёт с ребёнком"
Формат: список с демонстрацией

3. 🎬 День из жизни
Начало: "Утро в Белграде с 9-месячным малышом"
Формат: таймлапс дня, честно и с юмором

4. 🎬 Вопрос-ответ
Начало: "Все спрашивают как я путешествую с ребёнком одна"
Формат: отвечаю на топ вопросы

5. 🎬 Лайфхак
Начало: "Как уложить малыша в незнакомом месте"
Формат: конкретный совет за 15 секунд"""

def format_digest(trends: list, videos: list, hashtags: list, pinterest: list, ideas: str) -> str:
    today = datetime.now().strftime("%d.%m.%Y")

    msg = f"🌅 <b>Утренний дайджест трендов — {today}</b>\n\n"

    # Google Trends
    msg += "📈 <b>Google Trends сегодня:</b>\n"
    if trends:
        for t in trends[:5]:
            msg += f"• {t}\n"
    else:
        msg += "• Данные недоступны\n"
    msg += "\n"

    # YouTube
    msg += "📺 <b>Топ YouTube в твоей нише:</b>\n"
    if videos:
        for v in videos[:4]:
            msg += f"• <a href='{v['url']}'>{v['title'][:50]}...</a>\n"
    else:
        msg += "• Данные недоступны\n"
    msg += "\n"

    # TikTok хэштеги
    msg += "🎵 <b>Трендовые хэштеги:</b>\n"
    msg += " ".join(hashtags[:8]) + "\n\n"

    return msg

async def send_digest():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Собираю дайджест...")

    # Собираем данные параллельно
    trends_task = asyncio.create_task(fetch_google_trends())
    youtube_task = asyncio.create_task(fetch_youtube_trends())
    tiktok_task = asyncio.create_task(fetch_tiktok_trends())
    pinterest_task = asyncio.create_task(fetch_pinterest_trends())

    trends = await trends_task
    videos = await youtube_task
    hashtags = await tiktok_task
    pinterest = await pinterest_task

    print(f"Trends: {len(trends)}, Videos: {len(videos)}, Hashtags: {len(hashtags)}, Pinterest: {len(pinterest)}")

    # Генерируем идеи через ИИ
    ideas = await generate_reels_ideas(videos, trends, pinterest)

    # Формируем и отправляем дайджест
    digest = format_digest(trends, videos, hashtags, pinterest, ideas)
    await send_all(digest)

    # Идеи отдельным сообщением
    await asyncio.sleep(1)
    await send_all(f"💡 <b>5 идей для рилсов на сегодня:</b>\n\n{ideas}")

    print("Дайджест отправлен!")

async def poll_commands():
    """Слушаем команды от пользователя"""
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
                        await send_telegram("🔄 Собираю дайджест прямо сейчас...", chat_id)
                        asyncio.create_task(send_digest())

                    elif text == "/status":
                        now = datetime.now()
                        await send_telegram(
                            f"⚙️ <b>Trends Bot</b>\n"
                            f"Время: {now.strftime('%H:%M')} UTC\n"
                            f"Дайджест: каждый день в 09:00 по Белграду\n\n"
                            f"Команды:\n"
                            f"/digest — получить дайджест прямо сейчас\n"
                            f"/status — этот экран",
                            chat_id
                        )

            except Exception as e:
                print(f"Ошибка polling: {e}")
                await asyncio.sleep(5)

async def main():
    await send_all(
        "✅ <b>Trends Bot запущен!</b>\n"
        "Каждое утро в 09:00 (Белград) буду присылать:\n\n"
        "📈 Google Trends по твоей нише\n"
        "📺 Топ YouTube видео\n"
        "🎵 Трендовые хэштеги TikTok\n"
        "💡 5 идей для рилсов от ИИ\n\n"
        "Команды:\n"
        "/digest — получить дайджест прямо сейчас\n"
        "/status — статус бота"
    )

    async def scheduler():
        while True:
            now = datetime.utcnow()
            if now.hour == SEND_HOUR_UTC and now.minute == 0:
                await send_digest()
                await asyncio.sleep(61)  # пропускаем минуту чтобы не отправить дважды
            await asyncio.sleep(30)

    await asyncio.gather(scheduler(), poll_commands())

if __name__ == "__main__":
    asyncio.run(main(

