import os
from urllib.parse import urlparse


def create_folder_if_not_exists(folder_path):
    """Create a folder if it doesn't already exist."""
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
        print(f"Folder created: {folder_path}")
    else:
        print(f"Folder already exists: {folder_path}")


def get_file_extension(url):
    """Extract the file extension from a URL."""
    parsed_url = urlparse(url)
    path = parsed_url.path
    extension = path.split(".")[-1] if "." in path else ""
    return extension


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
