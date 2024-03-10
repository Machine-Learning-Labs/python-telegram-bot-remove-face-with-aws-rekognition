#!/usr/bin/env python
# pylint: disable=unused-argument, wrong-import-position
# This program is dedicated to the public domain under the CC0 license.

import os
import boto3
import logging

from helpers import create_folder_if_not_exists, get_file_extension
from dotenv import load_dotenv
from telegram import __version__ as TG_VER
from telegram import ForceReply, Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, CallbackContext, MessageHandler, filters

# Load environment variables from .env file
load_dotenv()

# Initialize the DynamoDB client
dynamodb = boto3.resource('dynamodb')
table_name = os.getenv('BOT_TABLE')
table = dynamodb.Table(table_name)

# Enable logging
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# create temp folder
temporary_folder = os.getenv('TMP_FOLDER')
create_folder_if_not_exists(temporary_folder)


# Define a few command handlers. These usually take the two arguments update and
# context.
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    user = update.effective_user
    await update.message.reply_html(
        rf"Hi {user.mention_html()}!",
        reply_markup=ForceReply(selective=True),
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    await update.message.reply_text("Help is still not defined :)")


async def handle_image2(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Stores the photo and asks for a location."""
    
    
    user = update.message.from_user
    user_id = update.effective_user.id
    file_id = update.message.photo[-1].file_id
    
    photo_file = await update.message.photo[-1].get_file()
    extension_file = get_file_extension(photo_file.file_path)
    path_file = f"{temporary_folder}/{user_id}"
    full_file = f"{path_file}/{file_id}.{extension_file}"
    create_folder_if_not_exists(path_file)
    
    await photo_file.download_to_drive(full_file)
    logger.info("Photo of %s: %s", user.first_name, full_file)


async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Echo the user message."""
    await update.message.reply_text(update.message.text)


def main() -> None:
    """Start the bot."""
    
    # Create the Application and pass it your bot's token.
    bot_token = os.getenv('BOT_TOKEN')

    if bot_token is None:
        print("Bot token not found in environment variable.")
        return
    
    application = Application.builder().token(bot_token).build()

    # on different commands - answer in Telegram
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.PHOTO, handle_image2))

    # on non command i.e message - echo the message on Telegram
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

    # Run the bot until the user presses Ctrl-C
    application.run_polling()

if __name__ == "__main__":
    main()
    