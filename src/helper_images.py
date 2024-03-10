from PIL import Image, ImageDraw, ImageFilter, ImageOps, ImageFont

TINT_COLOR = (255, 0, 0)  # RED
TRANSPARENCY = 0.35  # Degree of transparency, 0-100%
OPACITY = int(255 * TRANSPARENCY)

reference_color = "red"
font_file = "Pillow/Tests/fonts/DejaVuSans.ttf"
font_color = (255, 255, 255)


async def generate_reference(image, api_response):
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
    imgWidth, imgHeight = image.size

    for faceDetail in api_response["FaceDetails"]:
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
        name="reference.png",
    )

    return f"reference{extension}"


def save_image(stream, path, name):
    """

    :param stream:
    :param path:
    :param name:
    :param footer_text:
    :return:
    """

    img_with_border = ImageOps.expand(stream, border=border_size, fill=border_fill)
    img_with_border.save("{}/{}".format(path, name))
