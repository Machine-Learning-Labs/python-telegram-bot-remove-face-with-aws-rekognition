#!/usr/bin/env python

import os
import re
import html
import json
import boto3
import random
import logging
import botocore
import traceback

from dotenv import load_dotenv
from datetime import datetime

from helper_file import create_folder_if_not_exists, get_file_extension
from helper_images import generate_reference, generate_blurred
from helper_aws import detect_faces

from telegram import (
    LabeledPrice,
    ShippingOption,
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
    PreCheckoutQueryHandler,
    ShippingQueryHandler,
    filters,
)

# Enable logging
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()
bot_token = os.getenv("BOT_TOKEN")
user_table = os.getenv("BOT_TABLE")
temporary_folder = os.getenv("TMP_FOLDER")
developer_chat_id = os.getenv("DEVELOPER_CHAT_ID")
payment_provider_token = os.getenv("PAYMENT_PROVIDER_TOKEN")
payment_provider_secret = os.getenv("PAYMENT_SECRET")

donation_stripe_link = os.getenv("DONATION_STRIPE_LINK")
donation_buymeacoffe_link = os.getenv("DONATION_BUYMEACOFFE_LINK")

table_name = os.getenv("BOT_TABLE")
table = boto3.resource('dynamodb').Table(table_name)

AGREE, PHOTO, REQUEST = range(3)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the conversation and asks the user for authorization."""
    
    logger.info("start")
    reply_keyboard = [["Yes", "No"]]

    await update.message.reply_text(
        "Hi! My name is @FaceRemoverBot.\n"
        "I help you to delete faces from photos.\n"
        "I will change the faces you tell me to blurred areas.\n\n"
        "The photos will be automatically deleted and will only be returned to you in this conversation."
        "You will always be the owner and responsible for the photos you send.\n\n"
        "Say /start to read this message.\n"
        "Say /cancel to stop talking to me.\n"
        "Say /data to know more about the treatment of data.\n"
        "Say /donate to support with 1 USD to support this bot development.\n"
        "Say /contribute to know other ways to help and avoid limitations or advertising\n\n"
        "Are ok with this? (Reply or press: Yes or No)",
        reply_markup=ReplyKeyboardMarkup(
            reply_keyboard,
            one_time_keyboard=True,
            input_field_placeholder="Yes or No?"
        ),
    )

    return AGREE


async def agree(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores the selected answer and asks for a photo."""
    
    logger.info("agree")
    
    user = update.message.from_user

    logger.info(user)
    context.user_data["choice"] = True
    now = datetime.now()

    Item={
        'user_id': str(user['id']),
        'authorize': True,
        'registration_time': now.strftime("%H:%M:%S"),
        'registration_date': now.strftime("%d/%m/%Y"),
        'count': 0
    }
    
    try:
        table.put_item(
            Item=Item,
            ConditionExpression='attribute_not_exists(user_id)'
        )
    
    # Ignore the ConditionalCheckFailedException, bubble up other exceptions.
    except botocore.exceptions.ClientError as e:
        if e.response['Error']['Code'] != 'ConditionalCheckFailedException':
            raise
    
    if not "counter" in context.user_data:
        context.user_data["counter"] = 0

    logger.info("Authorization given %s: %s", user.first_name, update.message.text)
    await update.message.reply_text(
        "Ok, let's go! Please send me a photo with some faces to work on it",
        reply_markup=ReplyKeyboardRemove(),
    )

    return PHOTO


async def photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores the photo"""

    logger.info("photo")
    logger.info("User send a photo.")
    
    if not "choice" in context.user_data:
        await update.message.reply_text(
            "Sorry I need your EXPLICIT authorization before work on your photos.\nSimply use /start to start again.",
            reply_markup=ReplyKeyboardRemove(),
        )
        
        return ConversationHandler.END

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

    context.user_data["full_file"] = full_file
    context.user_data["path_file"] = path_file
    context.user_data["file_id"] = file_id
    context.user_data["extension_file"] = extension_file
    context.user_data["api_response"] = api_response
    context.user_data["faces_count"] = faces_count

    if faces_count == 0:
        return AGREE

    # if faces_count == 1:
    #    await update.message.reply_text(f"This is the photo blurred")
    #    return AGREE

    if faces_count >= 99:
        await update.message.reply_text(f"Too much faces in this photo")
        return AGREE

    # generate reference photo
    reference_file, faces_detail = await generate_reference(
        image_path=full_file,
        output_path=path_file,
        original_filename=file_id,
        original_extension=extension_file,
        api_response=api_response,
    )

    # Backup ok data
    context.user_data["reference_file"] = reference_file
    context.user_data["faces_detail"] = faces_detail

    await update.message.reply_photo(
        photo=reference_file,
        caption="Use the numbers in the to receive a copy with these faces blurred, or type 'all'",
    )

    return REQUEST


async def request(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    
    logger.info('request')
    logger.info("User ask a request.")
    
    # Parse numbers
    image_path=context.user_data["full_file"]
    if not os.path.exists(image_path):
        await update.message.reply_text(
            "Your photo has been deleted for inactivity, please upload again.\n"
            "All photographs are automatically deleted on a regular basis."
        )
        return REQUEST

    valid_numbers = []
    user = update.message.from_user
    raw_numbers = update.message.text
    candidate_numbers = re.findall(r"[\d']+", update.message.text)

    keys = context.user_data["faces_detail"].keys()
    for candidate in candidate_numbers:
        if int(candidate) in keys:
            valid_numbers.append(int(candidate))

    # Option to use keyword: ALL
    end_number = context.user_data["faces_count"]
    if raw_numbers.upper() == 'ALL':
        valid_numbers = [i for i in range(1, end_number + 1)]

    # Error non valid number
    if not len(valid_numbers):
        await update.message.reply_text(
            "Give a list number like: 1,2,3... and I'll give you a copy of the photo with these faces blurried.\n"
            "You can also type: all"
        )
        
        return REQUEST
    
    # Everything OK => generate images
    await update.message.reply_text(
        f"The valid references numbers are: {str(valid_numbers)[1:-1]}"
    )

    blurried_photo = await generate_blurred(
        image_path=context.user_data["full_file"],
        output_path=context.user_data["path_file"],
        original_filename=context.user_data["file_id"],
        original_extension=context.user_data["extension_file"],
        faces_detail=context.user_data["faces_detail"],
        ids_requested=valid_numbers,
    )

    await update.message.reply_photo(
        photo=blurried_photo,
        caption="Your photo with faces removed!"
    )
    
    context.user_data["counter"] += 1
    table.update_item(
        Key={ 'user_id': str(user['id']), }, 
        UpdateExpression="SET #count = #count + :increment",
		ExpressionAttributeNames={"#count": "count"},
		ExpressionAttributeValues={":increment": 1 }
    )
    
    # A little advertising
    counter = int(context.user_data["counter"])
    if counter > 1:
        await update.message.reply_text(f"Happy to help you with those {counter} photos!\nDo you consider to help me by /donate or /contribute ?")

    return REQUEST


async def give_excuse(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    
    logger.info('give_excuse')
    
    if (
        context.user_data
        and context.user_data["choice"]
        and context.user_data["reference_file"]
    ):
        await update.message.reply_text("I'm not sure if I understand you")
        return REQUEST

    await cancel(update, context)


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels and ends the conversation."""
    
    logger.info('cancel')

    context.user_data["choice"] = False
    user = update.message.from_user
    logger.info("User %s canceled the conversation.", user.first_name)

    await update.message.reply_text(
        "Ok, I'll be around if you need me.\nSimply use /start to start working.",
        reply_markup=ReplyKeyboardRemove(),
    )

    return ConversationHandler.END


# INFO #########################################################################

async def show_data_info(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    
    logger.info('show_data_info')
    await update.message.reply_text(
        "*Notice on image processing*:\n\n"
        "This Telegram bot is designed solely for automatic image processing purposes. We want to assure you that your images are treated with the utmost respect for your privacy and security.\n\n"
        "- *Data Handling:* We do not store, share, or forward any images you send through this bot to any third party or individual. Your images are processed only for the intended analysis and are immediately deleted thereafter.\n"
        "- *Confidentiality:* Your images and any data generated from them are kept confidential and are not used for any purposes other than the automated transformations provided by this bot.\n"
        "- *Data Security:* While we take every possible precaution to safeguard your data, please be aware that no online platform is completely immune to potential security risks. By using this bot, you acknowledge and accept this inherent risk.\n"
        "- *No Guarantees:* While we strive for accurate and reliable image analysis, we cannot guarantee the absolute accuracy or completeness of the results. It is advisable to use this bot's outputs as a reference and not as the sole basis for important decisions.\n\n"
        "By using this Telegram bot, you consent to the terms outlined in this disclaimer. If you have any concerns about your privacy or the handling of your data, please refrain from using the bot. Your trust and privacy are of utmost importance to us.\n",
        parse_mode="markdown"
    )

# ERROR ########################################################################

async def ask_for_permission(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info('ask_for_permission')
    await update.message.reply_text("I need your explicit permission to work, type or press /start")
    

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log the error and send a telegram message to notify the developer."""
    
    logger.info('error_handler')

    now = datetime.now()
    current_time = now.strftime("%H:%M:%S")

    # Log the error before we do anything else, so we can see it even if something breaks.
    logger.error(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")
    logger.error("Exception while handling an update:", exc_info=context.error)
    update_str = update.to_dict() if isinstance(update, Update) else str(update)
    logger.error(json.dumps(update_str, indent=2, ensure_ascii=False))
    logger.error(str(context.chat_data))
    logger.error(str(context.user_data))
    logger.error("<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<")

    # Finally, send the message
    error_message = (
        f"$> Error with user {update_str['message']['chat']['id']} at {current_time}"
    )

    await context.bot.send_message(chat_id=developer_chat_id, text=error_message)


# DONATE #######################################################################

async def mention_other_ways(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    
    logger.info('mention_other_ways')
    chat_id = update.message.chat_id
    
    random_gifs=[
        'https://media1.giphy.com/media/R6gvnAxj2ISzJdbA63/giphy.gif',
        'https://media0.giphy.com/media/aPN2C7ZONEwEe5PNXj/giphy.gif',
        'https://media3.giphy.com/media/1oibnUaGm5czffacN4/giphy.gif',
        'https://media3.giphy.com/media/iaRIvwgdg5qwT40iDL/giphy.gif',
        'https://media1.giphy.com/media/UQOtfc9uIXVv9IidCD/giphy.gif',
        'https://media4.giphy.com/media/lqMxLjlpyAaAjfJ9yj/giphy.gif',
        'https://media4.giphy.com/media/RghVmNiqzUNRDsjw8k/giphy.gif',
        'https://media1.giphy.com/media/3ohzgMvITPaFeQaSfm/giphy.gif',
        'https://media2.giphy.com/media/dBTJJqrcXMBgMhyE0d/giphy.gif',
        'https://media2.giphy.com/media/Wz2hmNYVM2LtGOGTAD/giphy.gif',
    ]
    
    await update.message.reply_text(f"Thanks for considering help!")
    await context.bot.send_document(
        chat_id=chat_id,
        document=random.choice(random_gifs))
    
    await update.message.reply_text(f"By the moment the alternative ways to donate are:")
    await update.message.reply_text(f"Stripe donation link: {donation_stripe_link}")
    await update.message.reply_text(f"BuyMe a Coffe Donation link: {donation_buymeacoffe_link}")


async def start_without_shipping_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Sends an invoice without shipping-payment."""
    logger.info('start_without_shipping_callback')
    
    chat_id = update.message.chat_id
    title = "Multi Face Remover 1 USD Donation"
    description = "Your privacy is our top priority.\n\nWhen you make a donation to support our identity protection bot, you can be confident that your transaction is secure. We've partnered with trusted platforms like Stripe and Telegram to manage your donation securely."

    # select a payload just for you to recognize its the donation from your bot
    payload = payment_provider_secret

    # price in dollars
    currency = "USD"
    price = 1
    
    # price * 100 so as to include 2 decimal points
    prices = [LabeledPrice("Contribution", price * 100)]

    # optionally pass 
    # need_name=True
    # need_phone_number=True,
    # need_email=True
    # need_shipping_address=True
    # is_flexible=True
    await context.bot.send_invoice(
        chat_id,
        title,
        description,
        payload,
        payment_provider_token,
        currency,
        prices
    )


# after (optional) shipping, it's the pre-checkout
async def precheckout_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Answers the PreQecheckoutQuery"""
    logger.info('precheckout_callback')
    
    query = update.pre_checkout_query
    # check the payload, is this from your bot?
    if query.invoice_payload != payment_provider_secret:
        # answer False pre_checkout_query
        await query.answer(ok=False, error_message="Something went wrong...")
    else:
        await query.answer(ok=True)


# finally, after contacting the payment provider...
async def successful_payment_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Confirms the successful payment."""
    logger.info('successful_payment_callback')
    
    # do something after successfully receiving payment?
    await update.message.reply_text("Thank you for your help!")
    context.user_data["counter"] = -99


# ##############################################################################


def main() -> None:
    """Start the bot."""

    if bot_token is None:
        logger.error("Bot token not found in environment variable.")
        return

    # Create the Application and pass it your bot's token.
    application = Application.builder().token(bot_token).build()

    #random_handler = MessageHandler(filters.TEXT & (~filters.COMMAND), give_excuse)
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
            CommandHandler("cancel", cancel),
        ],
    )

    # Business Logic handlers
    application.add_handler(conv_handler)
    application.add_handler(MessageHandler(filters.PHOTO, ask_for_permission))
    application.add_handler(CommandHandler("data", show_data_info))

    # Donation handlers
    application.add_handler(CommandHandler("contribute", mention_other_ways))
    application.add_handler(CommandHandler("donate", start_without_shipping_callback))
    application.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))

    # Generic error handler
    application.add_error_handler(error_handler)

    # Run the bot until the user presses Ctrl-C
    logger.info("Bot initialized")
    application.run_polling()


if __name__ == "__main__":
    main()
