import os
import logging
import tempfile
from pathlib import Path
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
    ConversationHandler,
)
from gif_maker import create_gif_from_images

# Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Conversation states
COLLECTING_IMAGES, WAITING_FOR_OPTIONS = range(2)

# User session storage
user_sessions: dict[int, dict] = {}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a welcome message."""
    await update.message.reply_text(
        "👋 *Welcome to GIF Maker Bot!*\n\n"
        "I can turn your images into animated GIFs.\n\n"
        "📌 *How to use:*\n"
        "1. Send /makegif to start\n"
        "2. Upload your images one by one (2–20 images)\n"
        "3. Send /done when finished\n"
        "4. I'll generate your GIF! 🎉\n\n"
        "Send /help for more info.",
        parse_mode="Markdown",
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send help message."""
    await update.message.reply_text(
        "🛠 *GIF Maker Bot — Help*\n\n"
        "📋 *Commands:*\n"
        "/start — Welcome message\n"
        "/makegif — Start a new GIF session\n"
        "/done — Finalize and create your GIF\n"
        "/cancel — Cancel the current session\n"
        "/help — Show this message\n\n"
        "📌 *Tips:*\n"
        "• Upload images in the order you want them to appear\n"
        "• Supported formats: JPG, PNG, WEBP\n"
        "• Max 20 images per GIF\n"
        "• Images are resized automatically for consistency",
        parse_mode="Markdown",
    )


async def makegif_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start a new GIF creation session."""
    user_id = update.effective_user.id

    # Reset session
    user_sessions[user_id] = {"images": [], "temp_dir": tempfile.mkdtemp()}

    await update.message.reply_text(
        "🖼 *GIF session started!*\n\n"
        "Send me your images one by one.\n"
        "When you're done, send /done to create the GIF.\n"
        "Send /cancel to abort.\n\n"
        "_Tip: Send images as photos or as files (documents) for best quality._",
        parse_mode="Markdown",
    )
    return COLLECTING_IMAGES


async def receive_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle incoming images."""
    user_id = update.effective_user.id

    if user_id not in user_sessions:
        await update.message.reply_text(
            "Please start a session first with /makegif"
        )
        return ConversationHandler.END

    session = user_sessions[user_id]

    if len(session["images"]) >= 20:
        await update.message.reply_text(
            "⚠️ Maximum of 20 images reached. Send /done to create your GIF."
        )
        return COLLECTING_IMAGES

    # Handle photo or document
    file = None
    if update.message.photo:
        file = await update.message.photo[-1].get_file()
    elif update.message.document:
        doc = update.message.document
        if doc.mime_type and doc.mime_type.startswith("image/"):
            file = await doc.get_file()
        else:
            await update.message.reply_text("⚠️ Please send image files only (JPG, PNG, WEBP).")
            return COLLECTING_IMAGES

    if not file:
        await update.message.reply_text("⚠️ Could not process the file. Please try again.")
        return COLLECTING_IMAGES

    # Download image
    img_path = os.path.join(session["temp_dir"], f"image_{len(session['images']):03d}.jpg")
    await file.download_to_drive(img_path)
    session["images"].append(img_path)

    count = len(session["images"])
    await update.message.reply_text(
        f"✅ Image {count} received!\n"
        f"{'Send more images or ' if count < 2 else ''}"
        f"{'Send at least 1 more image, or ' if count == 1 else ''}"
        f"send /done to create the GIF."
        if count >= 2
        else f"✅ Image {count} received! Send at least 1 more image."
    )
    return COLLECTING_IMAGES


async def done_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process images and create the GIF."""
    user_id = update.effective_user.id

    if user_id not in user_sessions:
        await update.message.reply_text("No active session. Send /makegif to start.")
        return ConversationHandler.END

    session = user_sessions[user_id]
    images = session["images"]

    if len(images) < 2:
        await update.message.reply_text(
            f"⚠️ You need at least 2 images to create a GIF. "
            f"You've sent {len(images)}. Keep going!"
        )
        return COLLECTING_IMAGES

    # Show options keyboard
    keyboard = [
        [
            InlineKeyboardButton("🐢 Slow (1s/frame)", callback_data="speed_slow"),
            InlineKeyboardButton("🚶 Normal (0.5s)", callback_data="speed_normal"),
        ],
        [
            InlineKeyboardButton("🏃 Fast (0.2s/frame)", callback_data="speed_fast"),
            InlineKeyboardButton("⚡ Very Fast (0.1s)", callback_data="speed_vfast"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"🎞 *{len(images)} images collected!*\n\nChoose the GIF speed:",
        reply_markup=reply_markup,
        parse_mode="Markdown",
    )
    return WAITING_FOR_OPTIONS


async def speed_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle speed selection and generate GIF."""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id

    speed_map = {
        "speed_slow": (1000, "Slow"),
        "speed_normal": (500, "Normal"),
        "speed_fast": (200, "Fast"),
        "speed_vfast": (100, "Very Fast"),
    }

    duration_ms, label = speed_map.get(query.data, (500, "Normal"))

    await query.edit_message_text(f"⚙️ Creating your GIF at *{label}* speed...", parse_mode="Markdown")

    session = user_sessions.get(user_id)
    if not session:
        await query.edit_message_text("Session expired. Please start again with /makegif")
        return ConversationHandler.END

    try:
        output_path = os.path.join(session["temp_dir"], "output.gif")
        create_gif_from_images(session["images"], output_path, duration_ms=duration_ms)

        await query.edit_message_text("📤 Uploading your GIF...")

        with open(output_path, "rb") as gif_file:
            await context.bot.send_animation(
                chat_id=update.effective_chat.id,
                animation=gif_file,
                caption=f"🎉 Your GIF is ready! ({len(session['images'])} frames · {label} speed)",
            )

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="✅ Done! Send /makegif to create another GIF.",
        )

    except Exception as e:
        logger.error(f"GIF creation error for user {user_id}: {e}")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="❌ Something went wrong while creating the GIF. Please try again with /makegif",
        )
    finally:
        # Cleanup
        _cleanup_session(user_id)

    return ConversationHandler.END


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the current session."""
    user_id = update.effective_user.id
    _cleanup_session(user_id)
    await update.message.reply_text(
        "❌ Session cancelled. Send /makegif to start a new one."
    )
    return ConversationHandler.END


def _cleanup_session(user_id: int) -> None:
    """Clean up user session and temp files."""
    import shutil
    session = user_sessions.pop(user_id, None)
    if session and os.path.isdir(session.get("temp_dir", "")):
        shutil.rmtree(session["temp_dir"], ignore_errors=True)


def main() -> None:
    """Start the bot."""
    logger.info("=== GIF Maker Bot starting up ===")

    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.critical(
            "FATAL: TELEGRAM_BOT_TOKEN environment variable is not set! "
            "Add it in Render Dashboard → Environment."
        )
        raise ValueError("TELEGRAM_BOT_TOKEN environment variable is not set!")

    logger.info("Token found (length=%d). Building application...", len(token))

    app = Application.builder().token(token).build()

    # Conversation handler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("makegif", makegif_command)],
        states={
            COLLECTING_IMAGES: [
                MessageHandler(filters.PHOTO | filters.Document.IMAGE, receive_image),
                CommandHandler("done", done_command),
            ],
            WAITING_FOR_OPTIONS: [
                CallbackQueryHandler(speed_callback, pattern="^speed_"),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_command)],
        allow_reentry=True,
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(conv_handler)

    logger.info("Handlers registered. Starting polling — bot is LIVE ✅")
    app.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,   # ignore queued updates from when bot was offline
    )


if __name__ == "__main__":
    main()
