#!/usr/bin/env python

import os
import json
import boto3
import logging

from helpers import create_folder_if_not_exists, get_file_extension
from api import detect_faces

from dotenv import load_dotenv
from telegram import ForceReply, ReplyKeyboardMarkup, ReplyKeyboardRemove, ReplyKeyboardRemove, Update
#from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, CallbackContext, MessageHandler, filters
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

# Load environment variables from .env file
load_dotenv()

# create temp folder
temporary_folder = os.getenv('TMP_FOLDER')
create_folder_if_not_exists(temporary_folder)

# Initialize the DynamoDB client
dynamodb = boto3.resource('dynamodb')
table_name = os.getenv('BOT_TABLE')
table = dynamodb.Table(table_name)

# Enable logging
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

EXPLAIN, ANALYZE, PROCESS, DELETE = range(4)


# Define a few command handlers. These usually take the two arguments update and
# context.
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Send a message when the command /start is issued."""
    user = update.effective_user
    user_id = update.effective_user.id
    
    # Store user ID in DynamoDB table
    table.put_item(
        Item={
            'user_id': str(user_id),
            'credits': 10
        }
    )
    
    await update.message.reply_html(
        rf"Hi {user.mention_html()}!",
        reply_markup=ForceReply(selective=True),
    )
    
    return ANALYZE
    

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Send a message when the command /help is issued."""
    await update.message.reply_text("Help is still not defined :)")
    
    return ANALYZE


async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores the photo and asks for a location."""
    
    await update.message.reply_text(f"Image received! Look for faces inside.")
    
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
    
    # Call Amazon Rekognition
    api_response = await detect_faces(full_file)
    
    with open(f"{full_file}.json", 'w') as json_file:
        json.dump(api_response, json_file, indent=4)

    # Reply with the number of detected faces
    faces = api_response['FaceDetails']
    await update.message.reply_text(f"Detected {len(faces)} face(s) in the image.")
    
    return PROCESS


async def send_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Echo the user message."""
    await update.message.reply_text(update.message.text)
    
    return PROCESS


async def delete_last_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Echo the user message."""
    await update.message.reply_text("TODO Delete photo")
    
    return ConversationHandler.END


async def done(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Display the gathered info and end the conversation."""
    user_data = context.user_data
    if "choice" in user_data:
        del user_data["choice"]

    await update.message.reply_text(
        f"I learned these facts about you: {user_data}Until next time!",
        reply_markup=ReplyKeyboardRemove(),
    )

    user_data.clear()
    return ConversationHandler.END

async def error(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log Errors caused by Updates."""
    logger.warning('Update "%s" caused error "%s"', update, context.error)


def main() -> None:
    """Start the bot."""
    
    # Create the Application and pass it your bot's token.
    bot_token = os.getenv('BOT_TOKEN')

    if bot_token is None:
        print("Bot token not found in environment variable.")
        return
    
    application = Application.builder().token(bot_token).build()
    
    # Add conversation handler with the states CHOOSING, TYPING_CHOICE and TYPING_REPLY
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            EXPLAIN:[
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    help_command
                )
            ],
            
            ANALYZE:[
                MessageHandler(filters.PHOTO, handle_image)
            ],
            
            PROCESS:[
                MessageHandler(filters.Regex("^[0-9]$"), send_image),
            ],
            
            DELETE:[
                MessageHandler(
                    filters.TEXT & ~(filters.COMMAND | filters.Regex("^Delete$")), 
                    delete_last_photo)
            ],
        },
        fallbacks=[MessageHandler(filters.Regex("^Done$"), done)],
    )

    # Conversation handlers
    application.add_handler(conv_handler)
    #application.add_handler(CommandHandler("help", help_command))
    #application.add_error_handler(error)

    # Run the bot until the user presses Ctrl-C
    application.run_polling()


if __name__ == "__main__":
    main()
    