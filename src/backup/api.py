import io
import os
import uuid
import json
import boto3
import base64
from io import BytesIO
from copy import copy, deepcopy
from datetime import datetime, timedelta
from PIL import Image, ImageDraw, ImageFilter, ImageOps, ImageFont


# Cacheable references
client = boto3.client("rekognition")
rekognition = boto3.client("rekognition")
s3_connection = boto3.resource("s3")
s3_client = boto3.client("s3")

TINT_COLOR = (255, 0, 0)  # RED
TRANSPARENCY = 0.35  # Degree of transparency, 0-100%
OPACITY = int(255 * TRANSPARENCY)

font_file = "GloriaHallelujah-Regular.ttf"
footer = "Made with ♥ by noface.photo"
border_size = 24
font_color = (255, 255, 255)
border_fill = "black"
reference_color = "red"


# Function to call Amazon Rekognition and detect faces in an image
async def detect_faces(image_path):
    """Count the number of faces in one app"""

    with open(image_path, "rb") as image_file:
        image_bytes = image_file.read()

    response = rekognition.detect_faces(
        Image={"Bytes": image_bytes}, Attributes=["ALL"]
    )

    return response


def lambda_handler(event, context):
    """

    :param event:
    :param context:
    :return:
    """

    bucket_name = "noface.photo-photos-upload-eu-west-1"

    image_list = []
    link_list = []
    footer_text = datetime.now().strftime("%d/%m/%Y, %H:%M")
    session_uuid = str(uuid.uuid4().hex)

    output_path = f"/tmp/{session_uuid}"  # AWS lambda
    # output_path = f'../tmp/{session_uuid}'             # local dev
    if not os.path.exists(output_path):
        os.makedirs(output_path)

    # Load image from S3 bucket
    # s3_object = s3_connection.Object(bucket_name, event['photo'])
    # s3_response = s3_object.get()

    # Load image from event
    body = event.get("body")
    imgstring = json.loads(body).get("imageData")
    original_filename = json.loads(body).get("fileName")
    file_name, file_extension = os.path.splitext(original_filename)

    # Save received image to S3
    # imgstring='data:image/png;base64,iVBORw0KGg....output_pathAAACO6E81pD3JlVY+GwAAAABJRU5ErkJggg=='
    imgstring = imgstring.split(",")[1]
    imgdata = base64.b64decode(imgstring)
    with open(f"{output_path}/{original_filename}", "wb") as f:
        f.write(imgdata)

    original = s3_connection.Object(bucket_name, f"{session_uuid}/{original_filename}")
    original.put(Body=imgdata, StorageClass="REDUCED_REDUNDANCY")

    # Save metadata
    metadata = s3_connection.Object(bucket_name, f"{session_uuid}/event.json")
    metadata.put(
        Body=(bytes(json.dumps(event).encode("UTF-8"))),
        StorageClass="REDUCED_REDUNDANCY",
    )

    # Save original photo
    image_bytes_io = BytesIO()  # or io.BytesIO()
    image_bytes_io.write(imgdata)  # store the gif bytes to the IO and open as image
    image = Image.open(image_bytes_io)
    # image = Image.open(io.BytesIO(imgdata))

    imgWidth, imgHeight = image.size
    save_image(
        stream=image,
        path=output_path,
        name="original{}".format(file_extension),
        footer_text=footer_text,
    )

    image_list.append(f"original{file_extension}")

    # Call DetectFaces
    response = client.detect_faces(
        Image={
            "S3Object": {
                "Bucket": bucket_name,
                "Name": f"{session_uuid}/{original_filename}",
            }
        },
        Attributes=["DEFAULT"],
    )

    # generate reference photo
    reference = generate_reference(
        image=image,
        output_path=output_path,
        extension=file_extension,
        response=response,
        imgWidth=imgWidth,
        imgHeight=imgHeight,
        footer_text=footer_text,
    )
    image_list.append(reference)

    # generate n-1 blur photos
    counter = 0
    for face in response["FaceDetails"]:
        id = f"person-{counter+1:03}"

        duplicate = copy(image)
        faces = response["FaceDetails"][:]
        del faces[counter]

        particular = generate_own(
            image=duplicate,
            output_path=output_path,
            extension=file_extension,
            id=id,
            faces=faces,
            imgWidth=imgWidth,
            imgHeight=imgHeight,
            footer_text=footer_text,
        )
        image_list.append(particular)
        counter += 1

    for output in image_list:
        object_name = f"{session_uuid}/{output}"
        generated = s3_connection.Object(bucket_name, object_name)
        result = generated.put(
            Body=open(f"{output_path}/{output}", "rb"),
            StorageClass="REDUCED_REDUNDANCY",
        )

        url_signed = s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket_name, "Key": object_name},
            ExpiresIn=3600,
        )
        link_list.append(url_signed)

    return {
        "statusCode": 200,
        "headers": {
            "Access-Control-Allow-Headers": "Content-Type",
            #'Access-Control-Allow-Origin': 'https://www.noface.photo',
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "OPTIONS,POST",
        },
        "body": json.dumps(link_list),
    }


def save_image(*, stream, path, name, footer_text):
    """

    :param stream:
    :param path:
    :param name:
    :param footer_text:
    :return:
    """

    img_with_border = ImageOps.expand(stream, border=border_size, fill=border_fill)
    w, h = stream.size
    draw = ImageDraw.Draw(img_with_border)
    font = ImageFont.truetype(font_file, (border_size // 2 + 1))
    draw.text((border_size, h + border_size - 2), footer_text, font_color, font=font)
    text_width, text_height = get_text_dimensions(footer, font)
    draw.text(
        (border_size + w - text_width, h + border_size - 2),
        footer,
        font_color,
        font=font,
    )
    img_with_border.save("{}/{}".format(path, name))


def generate_reference(
    *, image, output_path, extension, response, imgWidth, imgHeight, footer_text
):
    """

    :param image:
    :param output_path:
    :param extension:
    :param response:
    :param imgWidth:
    :param imgHeight:
    :return:
    """

    counter = 1
    for faceDetail in response["FaceDetails"]:
        box = faceDetail["BoundingBox"]
        left = imgWidth * box["Left"]
        top = imgHeight * box["Top"]
        width = imgWidth * box["Width"]
        height = imgHeight * box["Height"]

        image = image.convert("RGBA")
        overlay = Image.new("RGBA", image.size, TINT_COLOR + (0,))
        draw = ImageDraw.Draw(overlay)  # Create a context for drawing things on it.
        draw.ellipse(
            [left, top, left + width, top + height],
            outline=reference_color,
            fill=TINT_COLOR + (OPACITY,),
        )
        font = ImageFont.truetype(font_file, int(height * 0.3))
        draw.text(
            (left - width * 0.1, top - height * 0.4),
            str(counter),
            reference_color,
            font,
        )
        image = Image.alpha_composite(image, overlay)
        image = image.convert("RGB")

        counter += 1

    save_image(
        stream=image,
        path=output_path,
        name="reference{}".format(extension),
        footer_text=footer_text,
    )

    return f"reference{extension}"


def generate_own(
    *, image, output_path, extension, id, faces, imgWidth, imgHeight, footer_text
):
    """

    :param image:
    :param output_path:
    :param extension:
    :param id:
    :param faces:
    :param imgWidth:
    :param imgHeight:
    :return:
    """

    for faceDetail in faces:
        # draw = ImageDraw.Draw(image)

        box = faceDetail["BoundingBox"]
        left = imgWidth * box["Left"]
        top = imgHeight * box["Top"]
        width = imgWidth * box["Width"]
        height = imgHeight * box["Height"]

        # Create rounded rectangle mask
        mask = Image.new("L", image.size, 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse([left, top, left + width, top + height], fill=255)

        # Blur image
        blurred = image.filter(ImageFilter.GaussianBlur(20))

        # Paste blurred region and save result
        image.paste(blurred, mask=mask)

    save_image(
        stream=image,
        path=output_path,
        name="{}{}".format(id, extension),
        footer_text=footer_text,
    )
    return f"{id}{extension}"


def get_text_dimensions(text_string, font):
    """
    https://stackoverflow.com/a/46220683/9263761

    :param text_string:
    :param font:
    :return:
    """
    ascent, descent = font.getmetrics()

    text_width = font.getmask(text_string).getbbox()[2]
    text_height = font.getmask(text_string).getbbox()[3] + descent

    return text_width, text_height
