import os
import json
import re
import requests
import base64

from datetime import datetime, timedelta
from typing import List, Dict
from bs4 import BeautifulSoup
from tqdm import tqdm
from PIL import Image
from io import BytesIO

from dotenv import load_dotenv

load_dotenv()


def _get_title_tag(paper_div):
    title_tag = paper_div.find("a", class_="line-clamp-3")
    if title_tag:
        return title_tag
    else:
        return None
    
def _get_arxiv_id(title_tag):
    link = title_tag["href"]
    arxiv_id_match = re.search(r"/papers/(\d+\.\d+)", link)
    if arxiv_id_match:
        return arxiv_id_match.group(1)
    else:
        return None


def _get_authors(paper_div):
    authors = []
    for li in paper_div.find_all("li"):
        author = li.get("title")
        if author:
            authors.append(author)
    return authors


def _get_upvotes(paper_div):
    upvotes = paper_div.find("div", class_="leading-none")
    try:
        upvotes = int(upvotes.text.strip())
    except:
        upvotes = 0
    return upvotes


def get_arxiv_soup(full_link):
    response = requests.get(full_link)
    soup = BeautifulSoup(response.content, "html.parser")
    return soup


def get_title_from_arxiv(arxiv_soup):
    title = arxiv_soup.find("h1", class_="title")
    if title:
        title = title.text.strip()
    else:
        title = ""
    
    if title.startswith("Title:"):
        title = title[len("Title:"):].strip()

    return title


def get_abstract_from_arxiv(arxiv_soup):
    abstract = arxiv_soup.find("blockquote", class_="abstract")
    
    if abstract:
        abstract = abstract.text.strip()
    else:
        abstract = ""
        
    if abstract.startswith("Abstract:"):
        abstract = abstract[len("Abstract:"):].strip()

    return abstract


def get_categories_from_arxiv(arxiv_soup):
    categories = arxiv_soup.find("td", class_="subjects")
    if categories:
        categories = categories.text.strip()
    else:
        categories = ""
    categories = categories.split(";")

    return categories


def extract_paper_info(paper_div, seen_ids):
    title_tag = _get_title_tag(paper_div)
    if title_tag is None:
        return None
    title = title_tag.text.strip()
    
    arxiv_id = _get_arxiv_id(title_tag)
    if arxiv_id is None or arxiv_id in seen_ids:
        return None
    paper_link = f"https://arxiv.org/abs/{arxiv_id}"
    seen_ids.add(arxiv_id)

    authors = _get_authors(paper_div)
    upvotes = _get_upvotes(paper_div)
    
    arxiv_soup = get_arxiv_soup(paper_link)
    abstract = get_abstract_from_arxiv(arxiv_soup)
    categories = get_categories_from_arxiv(arxiv_soup)
    
    return {
        "title": title,
        "authors": authors,
        "arxiv_id": arxiv_id,
        "link": paper_link,
        "abstract": abstract,
        "upvotes": upvotes,
        "categories": categories,
    }


def _download_pdf(arxiv_id, save_path):
    """
    Downloads the PDF of a paper from arXiv given its ID.

    Args:
        arxiv_id (str): The arXiv ID of the paper.
        save_path (str): The path where the PDF will be saved.

    Returns:
        bool: True if the download was successful, False otherwise.
    """
    url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
    response = requests.get(url)
    assert response.status_code == 200, f"Failed to get response. Error: {response.text}"

    with open(save_path, "wb") as f:
        f.write(response.content)


def _save_dp_result(pdf_path, dp_path):
    api_key = os.environ.get("UPSTAGE_API_KEY")
    url = "https://api.upstage.ai/v1/document-ai/document-parse"
    headers = {"Authorization": f"Bearer {api_key}"}
    
    files = {"document": open(pdf_path, "rb")}
    data = {
        "base64_encoding": "['table', 'figure', 'caption', 'paragraph']",
        "output_formats": "['text', 'html']"
    }
    response = requests.post(url, headers=headers, files=files, data=data)
    assert response.status_code == 200, f"Failed to get response. Error: {response.text}"

    with open(dp_path, "w") as f:
        json.dump(response.json(), f, indent=2)


def download_paper(arxiv_id):
    pdf_dir = "data/pdfs"
    if not os.path.exists(pdf_dir):
        os.makedirs(pdf_dir, exist_ok=True)

    dp_dir = "data/dps"
    if not os.path.exists(dp_dir):
        os.makedirs(dp_dir, exist_ok=True)
    
    pdf_path = os.path.join(pdf_dir, f"{arxiv_id}.pdf")
    if not os.path.exists(pdf_path):
        try:
            _download_pdf(arxiv_id, pdf_path)
        except Exception as e:
            print(f"Failed to download PDF for {arxiv_id}: {e}")
            return None

    dp_path = os.path.join(dp_dir, f"{arxiv_id}.json")
    if not os.path.exists(dp_path):
        try:
            _save_dp_result(pdf_path, dp_path)
        except Exception as e:
            print(f"Failed to extract DP for {arxiv_id}: {e}")
            return None

    return {
        "pdf_path": pdf_path,
        "dp_path": dp_path,
    }


def pull_hf_daily(threshold=0, num_papers=5):
    """
    Pulls the daily papers from Hugging Face's papers page, downloads their PDFs,
    and saves their information in a JSON file.
    """
    HF_URL = "https://huggingface.co/papers"

    today = datetime.now()
    last_week = today - timedelta(days=7)
    last_week_str = last_week.strftime("%Y-%m-%d")
    last_week_params = f"?date={last_week_str}"
    last_week_url = HF_URL + last_week_params

    response = requests.get(last_week_url)
    soup = BeautifulSoup(response.content, "html.parser")

    candidates: List[Dict[str, str]] = []
    seen_ids = set()  # Set to track seen arXiv IDs

    # Locate the relevant div elements
    for paper_div in soup.find_all("div", class_="w-full"):
        paper_info = extract_paper_info(paper_div, seen_ids)
        if paper_info is None:
            continue

        candidates.append(paper_info)
    
    filtered_papers = [paper for paper in candidates if paper["upvotes"] >= threshold]
    sorted_papers = sorted(filtered_papers, key=lambda x: x["upvotes"], reverse=True)

    papers = []
    for paper in tqdm(sorted_papers[:num_papers], desc="Downloading papers and extracting DP"):
        arxiv_id = paper["arxiv_id"]
        download_paths = download_paper(arxiv_id)
        if download_paths is None:
            continue

        papers.append({
            **download_paths,
            **paper
        })

    data_dir = "data/papers"
    if not os.path.exists(data_dir):
        os.makedirs(data_dir, exist_ok=True)

    date = datetime.now().strftime("%Y-%m-%d")
    data_file_path = os.path.join(data_dir, f"{date}_papers.json")

    with open(data_file_path, "w") as f:
        json.dump(papers, f, indent=2)

    return last_week_url, papers


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


def get_images_from_pdf(dp_path, num_images=3):
    KEYWORD_REGEX = r"(figure|fig\.|table|chart)\s*\d+[:.]?.*"

    with open(dp_path, "r") as f:
        dp_result = json.load(f)

    images = []
    for i, element in enumerate(dp_result["elements"]):
        if element["category"] in ["table", "figure", "chart"]:
            image_element = {
                "image": element["base64_encoding"],
            }

            if i < len(dp_result["elements"]) - 1:
                next_element = dp_result["elements"][i+1]
            else:
                next_element = None

            if next_element is not None:
                if next_element["category"] == "caption":
                    image_element["caption"] = next_element["base64_encoding"]
                elif (
                    next_element["category"] == "paragraph" 
                    and re.match(KEYWORD_REGEX, next_element["content"]["text"].lower())
                ):
                    image_element["caption"] = next_element["base64_encoding"]

            images.append(_merge_images(image_element))

        if len(images) >= num_images:
            break

    return images
