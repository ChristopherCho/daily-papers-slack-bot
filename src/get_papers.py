import os
import json
import re
import requests

from datetime import datetime, timedelta
from typing import List, Dict
from bs4 import BeautifulSoup
from tqdm import tqdm

from dp import get_dp_result


HF_URL = "https://huggingface.co/papers"


def download_pdf(arxiv_id: str, save_path: str) -> bool:
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
    if response.status_code == 200:
        with open(save_path, "wb") as f:
            f.write(response.content)
        return True
    return False


def get_last_week():
    today = datetime.now()
    last_week = today - timedelta(days=7)
    last_week_str = last_week.strftime("%Y-%m-%d")
    
    return f"?date={last_week_str}"


def get_abstract(full_link: str) -> str:
    response = requests.get(full_link)
    soup = BeautifulSoup(response.content, "html.parser")
    abstract = soup.find("blockquote", class_="abstract")
    
    if abstract:
        abstract = abstract.text.strip()
    else:
        abstract = ""
        
    if abstract.startswith("Abstract:"):
        abstract = abstract[len("Abstract:"):].strip()

    return abstract


def pull_hf_daily(threshold: int = 0, num_papers: int = 5) -> None:
    """
    Pulls the daily papers from Hugging Face's papers page, downloads their PDFs,
    and saves their information in a JSON file.
    """
    last_week_url = get_last_week()
    response = requests.get(HF_URL + last_week_url)
    soup = BeautifulSoup(response.content, "html.parser")

    candidates: List[Dict[str, str]] = []
    seen_ids = set()  # Set to track seen arXiv IDs
    pdf_dir = "data/pdfs"
    os.makedirs(
        pdf_dir, exist_ok=True
    )  # Create temp_pdfs directory if it doesn't exist
    dp_dir = "data/dps"
    os.makedirs(dp_dir, exist_ok=True)

    # Locate the relevant div elements
    for paper_div in soup.find_all("div", class_="w-full"):
        # Extract the title
        title_tag = paper_div.find("a", class_="line-clamp-3")
        if title_tag:
            title = title_tag.text.strip()
        else:
            print("Title not found for a paper")
            continue

        # Extract the paper ID from the link
        link = title_tag["href"]
        arxiv_id_match = re.search(r"/papers/(\d+\.\d+)", link)
        if arxiv_id_match:
            arxiv_id = arxiv_id_match.group(1)
        else:
            print(f"Could not extract arXiv ID from link: {link}")
            continue

        # Check for duplicates using arXiv ID
        if arxiv_id in seen_ids:
            print(f"Duplicate paper detected with ID {arxiv_id}, skipping.")
            continue
        seen_ids.add(arxiv_id)  # Add ID to set of seen IDs

        # Extract the authors
        authors = []
        for li in paper_div.find_all("li"):
            author = li.get("title")
            if author:
                authors.append(author)

        # Extract upvote count
        upvotes = paper_div.find("div", class_="leading-none")
        try:
            upvotes = int(upvotes.text.strip())
        except:
            upvotes = 0

        # Create the full link to the paper
        full_link = f"https://arxiv.org/abs/{arxiv_id}"
        abstract = get_abstract(full_link)
        
        candidates.append(
            {
                "title": title,
                "authors": ", ".join(authors),
                "arxiv_id": arxiv_id,
                "link": full_link,
                "abstract": abstract,
                "upvotes": upvotes,
            }
        )
    
    filtered_papers = [paper for paper in candidates if paper["upvotes"] >= threshold]
    sorted_papers = sorted(filtered_papers, key=lambda x: x["upvotes"], reverse=True)
    
    papers = []
    for paper in tqdm(sorted_papers[:num_papers], desc="Downloading papers and extracting DP"):
        arxiv_id = paper["arxiv_id"]

        # Attempt to download the PDF
        try:
            pdf_path = os.path.join(pdf_dir, f"{arxiv_id}.pdf")
            if os.path.exists(pdf_path):
                print(f"PDF already exists for {arxiv_id}")
                pdf_exist = True
            else:
                pdf_exist = download_pdf(arxiv_id, pdf_path)

            if not pdf_exist:
                continue
        except Exception as e:
            print(f"Failed to download PDF for {arxiv_id}: {e}")
            continue

        try:
            dp_path = os.path.join(dp_dir, f"{arxiv_id}.json")
            if os.path.exists(dp_path):
                print(f"DP already exists for {arxiv_id}")
            else:
                dp_result = get_dp_result(pdf_path)
                with open(dp_path, "w") as f:
                    json.dump(dp_result, f, indent=2)

            papers.append({
                "pdf_path": pdf_path,
                "dp_path": dp_path,
                **paper
            })
        except Exception as e:
            print(f"Failed to extract DP for {arxiv_id}: {e}")

    date = datetime.now().strftime("%Y-%m-%d")
    data_dir = "data/papers"
    print(f"Ensuring data directory exists: {data_dir}")
    os.makedirs(data_dir, exist_ok=True)  # Create 'data' directory if it doesn't exist
    data_file_path = os.path.join(data_dir, f"{date}_papers.json")

    print(f"Writing data to {data_file_path}")
    with open(data_file_path, "w") as f:
        json.dump(papers, f, indent=2)
    print(f"Saved {len(papers)} papers' information and PDFs")

    return papers
