import os
import io
import logging
from PIL import Image
from colorthief import ColorThief
import telebot
from telebot.types import Message
import requests
import colorsys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN environment variable not set")

bot = telebot.TeleBot(BOT_TOKEN)


# ── helpers ──────────────────────────────────────────────────────────────────

def rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return "#{:02X}{:02X}{:02X}".format(*rgb)


def rgb_to_hsl(rgb: tuple[int, int, int]) -> tuple[int, int, int]:
    r, g, b = (x / 255 for x in rgb)
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    return round(h * 360), round(s * 100), round(l * 100)


def color_name_hint(rgb: tuple[int, int, int]) -> str:
    """Return a rough human-readable label based on hue + lightness."""
    r, g, b = rgb
    h, s, l = rgb_to_hsl(rgb)

    if s < 10:
        if l < 20:  return "Black"
        if l > 80:  return "White"
        return "Gray"

    if   h < 15:   label = "Red"
    elif h < 40:   label = "Orange"
    elif h < 65:   label = "Yellow"
    elif h < 150:  label = "Green"
    elif h < 195:  label = "Cyan"
    elif h < 260:  label = "Blue"
    elif h < 290:  label = "Purple"
    elif h < 330:  label = "Pink"
    else:           label = "Red"

    if l < 25:  label = "Dark " + label
    elif l > 75: label = "Light " + label

    return label


def build_palette_message(colors: list[tuple[int, int, int]]) -> str:
    lines = ["🎨 *Colour Palette*\n"]
    for i, rgb in enumerate(colors, 1):
        hex_code = rgb_to_hex(rgb)
        h, s, l  = rgb_to_hsl(rgb)
        name     = color_name_hint(rgb)
        lines.append(
            f"*{i}. {name}*\n"
            f"   `{hex_code}` • RGB({rgb[0]}, {rgb[1]}, {rgb[2]})\n"
            f"   HSL({h}°, {s}%, {l}%)\n"
        )
    lines.append("\n_Send another image to extract a new palette._")
    return "\n".join(lines)


def create_palette_image(colors: list[tuple[int, int, int]]) -> io.BytesIO:
    """Draw a horizontal swatch strip and return it as a BytesIO PNG."""
    swatch_w, swatch_h = 120, 120
    total_w = swatch_w * len(colors)

    img = Image.new("RGB", (total_w, swatch_h))
    for idx, color in enumerate(colors):
        swatch = Image.new("RGB", (swatch_w, swatch_h), color)
        img.paste(swatch, (idx * swatch_w, 0))

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


def extract_palette(file_bytes: bytes, color_count: int = 6) -> list[tuple[int, int, int]]:
    """Extract dominant colours from raw image bytes."""
    img_buf = io.BytesIO(file_bytes)
    ct = ColorThief(img_buf)
    palette = ct.get_palette(color_count=color_count, quality=1)
    return palette


# ── bot handlers ─────────────────────────────────────────────────────────────

@bot.message_handler(commands=["start", "help"])
def send_welcome(message: Message):
    text = (
        "👋 *Colour Palette Extractor Bot*\n\n"
        "Send me any image and I'll extract its dominant colour palette — "
        "complete with HEX, RGB, and HSL values.\n\n"
        "Just drop a photo below to get started! 🖼️"
    )
    bot.send_message(message.chat.id, text, parse_mode="Markdown")


@bot.message_handler(content_types=["photo"])
def handle_photo(message: Message):
    chat_id = message.chat.id
    processing_msg = bot.send_message(chat_id, "⏳ Analysing your image…")

    try:
        # Grab the highest-resolution photo Telegram provides
        file_info = bot.get_file(message.photo[-1].file_id)
        file_url  = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_info.file_path}"
        response  = requests.get(file_url, timeout=20)
        response.raise_for_status()
        file_bytes = response.content

        colors = extract_palette(file_bytes, color_count=6)

        # Send the swatch image first
        swatch_buf = create_palette_image(colors)
        bot.send_photo(
            chat_id,
            swatch_buf,
            caption="Here's your colour palette 👇",
        )

        # Then send the detailed text breakdown
        palette_text = build_palette_message(colors)
        bot.send_message(chat_id, palette_text, parse_mode="Markdown")

    except Exception as exc:
        logger.exception("Failed to process image: %s", exc)
        bot.send_message(
            chat_id,
            "❌ Sorry, I couldn't process that image. Please try another one.",
        )
    finally:
        try:
            bot.delete_message(chat_id, processing_msg.message_id)
        except Exception:
            pass


@bot.message_handler(content_types=["document"])
def handle_document(message: Message):
    """Accept images sent as files (uncompressed)."""
    doc = message.document
    if not doc.mime_type or not doc.mime_type.startswith("image/"):
        bot.send_message(
            message.chat.id,
            "Please send an *image* file (JPEG, PNG, WEBP, etc.).",
            parse_mode="Markdown",
        )
        return
    # Re-use the photo handler by faking a photo message path
    chat_id = message.chat.id
    processing_msg = bot.send_message(chat_id, "⏳ Analysing your image…")
    try:
        file_info  = bot.get_file(doc.file_id)
        file_url   = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_info.file_path}"
        response   = requests.get(file_url, timeout=20)
        response.raise_for_status()
        colors     = extract_palette(response.content, color_count=6)
        swatch_buf = create_palette_image(colors)
        bot.send_photo(chat_id, swatch_buf, caption="Here's your colour palette 👇")
        bot.send_message(chat_id, build_palette_message(colors), parse_mode="Markdown")
    except Exception as exc:
        logger.exception("Failed to process document image: %s", exc)
        bot.send_message(chat_id, "❌ Couldn't process that image. Please try another.")
    finally:
        try:
            bot.delete_message(chat_id, processing_msg.message_id)
        except Exception:
            pass


@bot.message_handler(func=lambda m: True)
def handle_other(message: Message):
    bot.send_message(
        message.chat.id,
        "🖼️ Please send me an *image* to extract its colour palette!\n"
        "Use /help for more info.",
        parse_mode="Markdown",
    )


# ── entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logger.info("Bot started — polling…")
    bot.infinity_polling(timeout=30, long_polling_timeout=25)
