#!/usr/bin/env python

import os
import json
import boto3
import logging

from dotenv import load_dotenv
from helper_file import create_folder_if_not_exists, get_file_extension
from helper_aws import detect_faces
from telegram import (
    ForceReply,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    ReplyKeyboardRemove,
    Update,
)
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)


# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()
bot_token = os.getenv("BOT_TOKEN")
user_table = os.getenv("BOT_TABLE")
temporary_folder = os.getenv("TMP_FOLDER")

AGREE, PHOTO, REQUEST = range(3)


# ##############################################################################

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the conversation and asks the user for authorization."""
    reply_keyboard = [["Yes", "No"]]

    await update.message.reply_text(
        "Hi! My name is Multi Face Remover Bot.\nI help you to delete faces from photos."
        "I will change the faces you tell me to blurred areas."
        "The photos will be automatically deleted and will only be returned to you in this conversation."
        "You will always be the owner and responsible for the photos you send.\n\n"
        "Send /cancel to stop talking to me.\n\n"
        "Are ok with this?",
        reply_markup=ReplyKeyboardMarkup(
            reply_keyboard, 
            one_time_keyboard=True, 
            input_field_placeholder="Yes or No?"
        ),
    )

    return AGREE
    
async def agree(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores the selected gender and asks for a photo."""
    user = update.message.from_user
    logger.info("Authorization given %s: %s", user.first_name, update.message.text)
    await update.message.reply_text(
        "Ok, let's go! Please send me a photo with some faces to work on it",
        reply_markup=ReplyKeyboardRemove(),
    )

    return PHOTO
    

async def photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores the photo"""
    
    logger.info("User send a photo.")
    
    user = update.message.from_user
    await update.message.reply_text(f"Image received! Look for faces inside.")
    
    user = update.message.from_user
    user_id = update.effective_user.id
    file_id = update.message.photo[-1].file_id
    
    create_folder_if_not_exists(temporary_folder)
    photo_file = await update.message.photo[-1].get_file()
    extension_file = get_file_extension(photo_file.file_path)
    path_file = f"{temporary_folder}/{user_id}"
    full_file = f"{path_file}/{file_id}.{extension_file}"
    create_folder_if_not_exists(path_file)

    await photo_file.download_to_drive(full_file)
    logger.info("Photo of %s: %s", user.first_name, full_file)

    # Call Amazon Rekognition
    api_response = await detect_faces(full_file)

    with open(f"{full_file}.json", "w") as json_file:
        json.dump(api_response, json_file, indent=4)

    # Reply with the number of detected faces
    faces = api_response["FaceDetails"]
    faces_count = len(faces)
    await update.message.reply_text(f"Detected {faces_count} face(s) in the image.")
    
    if faces_count==0:
        return AGREE
    
    if faces_count==1:
        await update.message.reply_text(f"This is the photo blurred")
        return AGREE
    
    if faces_count>=99:
        await update.message.reply_text(f"Too much faces in this photo")
        return AGREE
    
    await update.message.reply_text(f"This is the reference to specify")
    
    return REQUEST


async def request(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    
    logger.info("User send a number.")
    
    user = update.message.from_user
    
    return AGREE


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels and ends the conversation."""
    user = update.message.from_user
    logger.info("User %s canceled the conversation.", user.first_name)
    await update.message.reply_text(
        
        "Ok, I'll be around if you need me.\nSimply use /start to restart.", 
        reply_markup=ReplyKeyboardRemove()
    )

    return ConversationHandler.END


def main() -> None:
    """Start the bot."""

    if bot_token is None:
        logger.error("Bot token not found in environment variable.")
        return

    # Create the Application and pass it your bot's token.
    application = Application.builder().token(bot_token).build()
    
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            AGREE: [
                MessageHandler(filters.Regex("^(Yes|YES|Y|y)$"), agree),
                MessageHandler(filters.Regex("^(No|NO|N|n)$"), cancel),
                ],
            PHOTO: [MessageHandler(filters.PHOTO, photo)],
            REQUEST: [MessageHandler(filters.Regex("^(Yes|YES|Y|y)$"), request)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(conv_handler)
    
    # Run the bot until the user presses Ctrl-C
    logger.info("Bot initialized")
    application.run_polling()


if __name__ == "__main__":
    main()
