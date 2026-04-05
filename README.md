# 📰 Multi-Source News → Facebook Auto Poster

Al Jazeera, CNN, BBC, Washington Post, TRT World, Jerusalem Post থেকে
স্বয়ংক্রিয়ভাবে বাংলায় translate করে Facebook Page-এ post করে।

---

## 🚀 Railway-তে Deploy করার ধাপ

### ধাপ ১ — GitHub-এ Repository বানান

1. https://github.com → লগইন করুন
2. **New repository** → নাম দিন: `news-fb-autopost`
3. **Public** বা **Private** যেকোনো একটা বেছে নিন
4. **Create repository** চাপুন

### ধাপ ২ — ফাইলগুলো GitHub-এ upload করুন

এই ৪টি ফাইল upload করুন:
```
✅ main.py
✅ requirements.txt
✅ Procfile
✅ railway.json
```

GitHub-এ গিয়ে **Add file → Upload files** করুন।

### ধাপ ৩ — Railway-তে Deploy করুন

1. https://railway.app → **Login with GitHub**
2. **New Project** → **Deploy from GitHub repo**
3. আপনার `news-fb-autopost` repo বেছে নিন
4. Railway নিজেই build শুরু করবে

### ধাপ ৪ — Environment Variables set করুন ⚠️ সবচেয়ে গুরুত্বপূর্ণ

Railway Dashboard → আপনার project → **Variables** tab → **New Variable**:

| Variable Name | Value | কোথায় পাবেন |
|---------------|-------|-------------|
| `ANTHROPIC_API_KEY` | `sk-ant-...` | https://console.anthropic.com |
| `FB_PAGE_ACCESS_TOKEN` | `EAAG...` | Facebook Developer Console |
| `FB_PAGE_ID` | `123456789` | FB Page → About |
| `POST_INTERVAL_MINUTES` | `60` | (ঐচ্ছিক, default 60) |
| `MAX_POSTS_PER_RUN` | `6` | (ঐচ্ছিক, default 6) |

Variables set করার পর Railway **automatically restart** করবে।

### ধাপ ৫ — Logs দেখুন

Railway Dashboard → **Deployments** → **View Logs**

সফল হলে দেখবেন:
```
✅ সব credentials পাওয়া গেছে।
🚀 Pipeline: 2024-xx-xx xx:xx:xx
📰 Al Jazeera থেকে news নিচ্ছি...
```

---

## ⚙️ Settings পরিবর্তন করতে

Railway Variables-এ value বদলালেই হবে, code edit করতে হবে না:

| Variable | কাজ |
|----------|-----|
| `POST_INTERVAL_MINUTES=30` | ৩০ মিনিট পরপর post |
| `MAX_POSTS_PER_RUN=3` | একসাথে ৩টি post |
| `MAX_PER_SOURCE=1` | প্রতি source থেকে ১টি |

---

## 💰 Railway Free Plan

- প্রতি মাসে **$5 free credit**
- এই bot চালাতে মাসে প্রায় **$0.50–$1** লাগে
- অর্থাৎ free-তেই চলবে ✅

---

## ❓ সমস্যা হলে

| সমস্যা | সমাধান |
|--------|--------|
| Build failed | Logs দেখুন, requirements.txt ঠিক আছে কিনা |
| `ANTHROPIC_API_KEY` error | Variables-এ সঠিকভাবে set করুন |
| FB post হচ্ছে না | Access token মেয়াদ শেষ — নতুন token নিন |
| বাংলা font দেখা যাচ্ছে না | Railway-তে Noto font আপনাআপনি থাকে |
