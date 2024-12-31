import os
import re
import json
import base64
import requests

from PIL import Image
from io import BytesIO
from dotenv import load_dotenv

load_dotenv()


KEYWORD_REGEX = r"(Figure|Fig\.|Table)\s*\d+[:.]?.*"

def get_dp_result(file_path: str):
    api_key = os.environ.get("UPSTAGE_API_KEY")
    url = "https://api.upstage.ai/v1/document-ai/document-parse"
    headers = {"Authorization": f"Bearer {api_key}"}
    
    files = {"document": open(file_path, "rb")}
    data = {
        "base64_encoding": "['table', 'figure', 'caption', 'paragraph']",
        "output_formats": "['text', 'html']"
    }
    response = requests.post(url, headers=headers, files=files, data=data)
    
    return response.json()


def _merge_images(image_element):
    # Decode base64 images
    image_data = base64.b64decode(image_element["image"])
    if "caption" in image_element and image_element["caption"] is not None:
        caption_data = base64.b64decode(image_element["caption"])
    else:
        caption_data = None

    # Open the image and caption
    image = Image.open(BytesIO(image_data))
    caption = Image.open(BytesIO(caption_data)) if caption_data else None

    # If no caption, return the image as a BytesIO object
    if caption is None:
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        buffer.seek(0)

        return buffer

    # Calculate the size of the canvas
    max_width = max(image.width, caption.width)
    max_height = image.height + caption.height

    # Create a new blank image with the calculated dimensions
    canvas = Image.new("RGB", (max_width, max_height), color=(255, 255, 255))  # White background

    # Calculate offsets to center the image and caption
    image_x_offset = (max_width - image.width) // 2
    caption_x_offset = (max_width - caption.width) // 2

    # Paste the image and caption onto the canvas
    canvas.paste(image, (image_x_offset, 0))
    canvas.paste(caption, (caption_x_offset, image.height))

    # Save the final canvas to a BytesIO object
    buffer = BytesIO()
    canvas.save(buffer, format="PNG")
    buffer.seek(0)

    return buffer


def get_images_from_pdf(dp_path: str, num_images: int = 3):
    with open(dp_path, "r") as f:
        dp_result = json.load(f)

    images = []
    for i, element in enumerate(dp_result["elements"]):
        if element["category"] in ["table", "figure"]:
            image_element = {
                "image": element["base64_encoding"],
            }
            
            # if i > 0:
            #     prev_element = dp_result["elements"][i-1]
            # else:
            #     prev_element = None

            if i < len(dp_result["elements"]) - 1:
                next_element = dp_result["elements"][i+1]
            else:
                next_element = None

            if next_element is not None:
                if next_element["category"] == "caption":
                    image_element["caption"] = next_element["base64_encoding"]
                elif next_element["category"] == "paragraph":
                    if re.match(KEYWORD_REGEX, next_element["content"]["text"]):
                        image_element["caption"] = next_element["base64_encoding"]
            
            images.append(_merge_images(image_element))

        if len(images) >= num_images:
            break

    return images