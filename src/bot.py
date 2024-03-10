#!/usr/bin/env python

import os
import re
import html
import json
import boto3
import logging
import traceback

from dotenv import load_dotenv
from helper_file import create_folder_if_not_exists, get_file_extension
from helper_images import generate_reference, generate_blurred
from helper_aws import detect_faces

from telegram import (
    ForceReply,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    ReplyKeyboardRemove,
    Update,
)
from telegram.constants import ParseMode
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
developer_chat_id = os.getenv("DEVELOPER_CHAT_ID")

AGREE, PHOTO, REQUEST = range(3)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the conversation and asks the user for authorization."""
    reply_keyboard = [["Yes", "No"]]
    
    await update.message.reply_text(
        "Hi! My name is Multi Face Remover Bot.\nI help you to delete faces from photos."
        "I will change the faces you tell me to blurred areas."
        "The photos will be automatically deleted and will only be returned to you in this conversation."
        "You will always be the owner and responsible for the photos you send.\n\n"
        "Send /cancel to stop talking to me.\n\n"
        "Are ok with this? (Yes or No)",
        reply_markup=ReplyKeyboardMarkup(
            reply_keyboard, one_time_keyboard=True, 
            input_field_placeholder="Yes or No?"
        ),
    )

    return AGREE


async def agree(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores the selected gender and asks for a photo."""
    user = update.message.from_user
    
    logger.info(user)
    context.user_data["choice"] = True
    
    logger.info("Authorization given %s: %s", user.first_name, update.message.text)
    await update.message.reply_text(
        "Ok, let's go! Please send me a photo with some faces to work on it",
        reply_markup=ReplyKeyboardRemove(),
    )

    return PHOTO


async def photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores the photo"""

    logger.info("User send a photo.")
    
    if not context.user_data["choice"]:
        await update.message.reply_text(f"No authorization, no party sorry :(")
        return AGREE
    
    user = update.message.from_user
    await update.message.reply_text(f"Image received! Look for faces inside.")

    user = update.message.from_user
    user_id = update.effective_user.id
    file_id = update.message.photo[-1].file_id

    # TODO mover esto a un método
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
    
    context.user_data["full_file"] = full_file
    context.user_data["path_file"] = path_file
    context.user_data["file_id"] = file_id
    context.user_data["extension_file"] = extension_file
    context.user_data["api_response"] = api_response
    context.user_data["faces_count"] = faces_count

    if faces_count == 0:
        return AGREE

    #if faces_count == 1:
    #    await update.message.reply_text(f"This is the photo blurred")
    #    return AGREE

    if faces_count >= 99:
        await update.message.reply_text(f"Too much faces in this photo")
        return AGREE

    await update.message.reply_text(f"This is the reference to specify")

    # generate reference photo
    reference_file, faces_detail = await generate_reference(
        image_path=full_file,
        output_path=path_file,
        original_filename=file_id,
        original_extension=extension_file,
        api_response=api_response
    )
    
    
    # Backup ok data
    context.user_data["reference_file"] = reference_file
    context.user_data["faces_detail"] = faces_detail
    
    await update.message.reply_photo(
        photo=reference_file,
        caption="Use this numbers to receive a copy with the faces blurred"
        )

    return REQUEST


async def request(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    
    logger.info("User ask a request.")
    
    valid_numbers = []
    user = update.message.from_user
    raw_numbers = update.message.text
    candidate_numbers = re.findall(r"[\d']+", update.message.text)
    
    keys = context.user_data["faces_detail"].keys()
    for candidate in candidate_numbers:
        if int(candidate) in keys:
            valid_numbers.append(int(candidate))

    
    if len(valid_numbers):
        await update.message.reply_text(f"The valid references numbers are: {valid_numbers}")

        blurried_photo = await generate_blurred(
            image_path=context.user_data["full_file"],
            output_path=context.user_data["path_file"],
            original_filename=context.user_data["file_id"],
            original_extension=context.user_data["extension_file"],
            faces_detail = context.user_data["faces_detail"],
            ids_requested=valid_numbers
        )
        
        await update.message.reply_photo(
            photo=blurried_photo,
            caption="Your photo with faces removed!"
        )
    
    else:
        await update.message.reply_text("Give a list number like: 1,2,3... and I'll give you a copy of the photo with these faces blurried.")
    
    return REQUEST


async def give_excuse(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    
    if context.user_data and context.user_data["choice"] and context.user_data["reference_file"]:
        await update.message.reply_text("I'm not sure if I understand you")
        return REQUEST

    await cancel(update, context)


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels and ends the conversation."""
    
    context.user_data["choice"] = False
    user = update.message.from_user
    logger.info("User %s canceled the conversation.", user.first_name)
    
    
    await update.message.reply_text(
        "Ok, I'll be around if you need me.\nSimply use /start to start working.",
        reply_markup=ReplyKeyboardRemove(),
    )

    return ConversationHandler.END


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log the error and send a telegram message to notify the developer."""
    # Log the error before we do anything else, so we can see it even if something breaks.
    logger.error("Exception while handling an update:", exc_info=context.error)

    # traceback.format_exception returns the usual python message about an exception, but as a
    # list of strings rather than a single string, so we have to join them together.
    tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
    tb_string = "".join(tb_list)

    # Build the message with some markup and additional information about what happened.
    # You might need to add some logic to deal with messages longer than the 4096 character limit.
    update_str = update.to_dict() if isinstance(update, Update) else str(update)
    message = (
        f"An exception was raised while handling an update\n"
        f"<pre>update = {html.escape(json.dumps(update_str, indent=2, ensure_ascii=False))}"
        "</pre>\n\n"
        f"<pre>context.chat_data = {html.escape(str(context.chat_data))}</pre>\n\n"
        f"<pre>context.user_data = {html.escape(str(context.user_data))}</pre>\n\n"
        f"<pre>{html.escape(tb_string)}</pre>"
    )
    
    # Finally, send the message
    await context.bot.send_message(
        chat_id=developer_chat_id, 
        text=message, 
        parse_mode=ParseMode.HTML
    )

# ##############################################################################


def main() -> None:
    """Start the bot."""

    if bot_token is None:
        logger.error("Bot token not found in environment variable.")
        return

    # Create the Application and pass it your bot's token.
    application = Application.builder().token(bot_token).build()

    random_handler = MessageHandler(filters.TEXT & (~filters.COMMAND), give_excuse)
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            AGREE: [
                MessageHandler(filters.Regex("^(Yes|yes|YES|Y|y)$"), agree),
                MessageHandler(filters.Regex("^(No|NO|no|N|n)$"), cancel),
            ],
            PHOTO: [MessageHandler(filters.PHOTO, photo)],
            REQUEST: [MessageHandler(filters.TEXT & ~filters.COMMAND, request)],
        },
        fallbacks=[
            MessageHandler(filters.PHOTO, photo),
            MessageHandler(filters.TEXT & ~filters.COMMAND, give_excuse),
            CommandHandler("cancel", cancel)
            ],
    )
    
    application.add_handler(conv_handler)
    application.add_handler(random_handler)
    
    # ...and the error handler
    application.add_error_handler(error_handler)

    # Run the bot until the user presses Ctrl-C
    logger.info("Bot initialized")
    application.run_polling()


if __name__ == "__main__":
    main()
