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
        image_path:str,
        output_path:str,
        original_filename:str,
        original_extension:str,
        api_response:dict
        ) -> str:

    counter = 1
    faces = {}
    
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

        faces[counter] = faceDetail["BoundingBox"]
        counter += 1
        
    new_file_name=f"{output_path}/{original_filename}-reference.{original_extension}"
    img_with_border = ImageOps.expand(image, border=border_size, fill=border_fill)
    img_with_border.save(new_file_name)
    
    return new_file_name, faces


async def generate_blurred(
        image, 
        output_path, 
        extension, 
        id, 
        faces, 
        imgWidth, 
        imgHeight, 
        footer_text
    ) -> str:
        

    # TODO adaptar esta función para que tb salve
    # TODO adaptar esta función para que salve los que recibe como parámetro

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