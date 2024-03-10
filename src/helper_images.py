import logging
from PIL import Image, ImageDraw, ImageFilter, ImageOps, ImageFont

TINT_COLOR = (255, 0, 0)  # RED
TRANSPARENCY = 0.35  # Degree of transparency, 0-100%
OPACITY = int(255 * TRANSPARENCY)

border_size = 24
border_fill = "black"
reference_color = "red"
font_file = "Pillow/Tests/fonts/DejaVuSans.ttf"
font_color = (255, 255, 255)


logger = logging.getLogger(__name__)

async def generate_reference(
        image_path,
        output_path,
        original_filename,
        original_extension,
        api_response
        ) -> str:

    counter = 1
    image = Image.open(image_path)
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
        
    new_file_name=f"{output_path}/{original_filename}-reference.{original_extension}"
    img_with_border = ImageOps.expand(image, border=border_size, fill=border_fill)
    img_with_border.save(new_file_name)

    return new_file_name
