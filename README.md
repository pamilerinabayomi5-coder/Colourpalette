# 🎨 Colour Palette Extractor — Telegram Bot

A Telegram bot that extracts the dominant colour palette from any image you send it, returning:
- A visual **swatch strip**
- **HEX**, **RGB**, and **HSL** values for each colour
- A human-readable colour name hint

---

## Features

| Feature | Detail |
|---|---|
| Colour extraction | Top 6 dominant colours via `colorthief` |
| Formats returned | HEX · RGB · HSL |
| Image types | Photos & uncompressed image files |
| Deployment | Render background worker (free tier) |

---

## Project Structure

```
palette-bot/
├── bot.py            # Main bot logic
├── requirements.txt  # Python dependencies
├── render.yaml       # Render deployment config
├── .gitignore
└── README.md
```

---

## Local Setup

### 1. Clone the repo

```bash
git clone https://github.com/<your-username>/palette-bot.git
cd palette-bot
```

### 2. Create a virtual environment

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Get a Telegram Bot Token

1. Open Telegram and search for **@BotFather**
2. Send `/newbot` and follow the prompts
3. Copy the token you receive (looks like `123456:ABC-DEF...`)

### 5. Set the environment variable

```bash
export TELEGRAM_BOT_TOKEN="your_token_here"
```

### 6. Run the bot

```bash
python bot.py
```

---

## Deploying to GitHub + Render

### Step 1 — Push to GitHub

```bash
git init
git add .
git commit -m "Initial commit: colour palette bot"
git branch -M main
git remote add origin https://github.com/<your-username>/palette-bot.git
git push -u origin main
```

### Step 2 — Create a Render Background Worker

1. Go to [render.com](https://render.com) and sign in
2. Click **New → Background Worker**
3. Connect your **GitHub account** and select the `palette-bot` repository
4. Render will auto-detect `render.yaml` — confirm the settings:
   - **Runtime:** Python
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python bot.py`
5. Scroll to **Environment Variables** and add:
   - Key: `TELEGRAM_BOT_TOKEN`
   - Value: your token from BotFather
6. Click **Create Background Worker**

Render will build and deploy the bot automatically. Every `git push` to `main` triggers a redeploy.

### Step 3 — Verify

Open Telegram, find your bot, and send `/start` followed by any image.

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | ✅ | Token from @BotFather |

---

## Dependencies

| Package | Purpose |
|---|---|
| `pyTelegramBotAPI` | Telegram Bot API wrapper |
| `Pillow` | Image processing & swatch generation |
| `colorthief` | Dominant colour extraction |
| `requests` | Downloading Telegram file URLs |

---

## Commands

| Command | Description |
|---|---|
| `/start` | Welcome message |
| `/help` | Usage instructions |
| _(send photo)_ | Extract colour palette |

---

## License

MIT
