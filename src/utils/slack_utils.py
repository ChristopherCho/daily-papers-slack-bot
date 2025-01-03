import os
import re

from utils.paper_utils import get_images_from_pdf
from utils.llm_utils import get_related_subcategories


def post_message(client, channel, message, message_ts = None):
    message_data = client.chat_postMessage(
        channel=channel, 
        text=message,
        unfurl_links=False,
        unfurl_media=False,
        thread_ts=message_ts
    )

    return message_data.data["ts"]


def update_message(client, channel, text, message_ts):
    return client.chat_update(
        channel=channel,
        ts=message_ts,
        text=text
    )


def delete_message(client, channel, message_ts):
    return client.chat_delete(
        channel=channel,
        ts=message_ts
    )


def feed_paper(
    client, 
    channel, 
    arxiv_id, 
    link, 
    title, 
    abstract, 
    dp_path,
    categories,
    message_ts = None
):
    message = f"<{link}|*{title}*>"
    message_ts = post_message(client, channel, message, message_ts)

    if len(categories) > 0:
        pattern = r"(.*)\s*\((.*)\)"
        
        available_categories = os.listdir("data/categories")
        sub_category_candidates = []
        
        custom_categories = open("data/categories/custom").readlines()
        custom_categories = [category.strip() for category in custom_categories if category.strip() != ""]
        sub_category_candidates.extend(custom_categories)
        
        for category in categories:
            tag_match = re.match(pattern, category.strip())
            if tag_match and tag_match.group(2) in available_categories:
                sub_categories = open(f"data/categories/{tag_match.group(2)}").readlines()
                sub_category_candidates.extend([category.strip() for category in sub_categories])

        if len(sub_category_candidates) > 0:
            try:
                related_subcategories = get_related_subcategories(title, abstract, sub_category_candidates)
                if len(related_subcategories) > 0 and len(related_subcategories) <= 3:
                    category_list = "\n".join([f'- {category}' for category in related_subcategories])
                    category_message = f"*Related categories:*\n{category_list}"
                    post_message(client, channel, category_message, message_ts)
            except Exception:
                pass

    if abstract:
        abstract = f"*Abstract*\n{abstract}"
        post_message(client, channel, abstract, message_ts)

    if dp_path:
        images = get_images_from_pdf(dp_path)
        for i, image in enumerate(images):
            client.files_upload_v2(
                channels=channel,
                file=image,
                title=f"{arxiv_id}.{i}",
                thread_ts=message_ts
            )

    return message_ts
