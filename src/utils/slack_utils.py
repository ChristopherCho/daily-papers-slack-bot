import os
import re

from utils.paper_utils import get_images_from_pdf
from utils.llm_utils import get_related_subcategories


def post_message(client, channel, message, message_ts = None, use_preview = False):
    message_data = client.chat_postMessage(
        channel=channel, 
        text=message,
        unfurl_links=use_preview,
        unfurl_media=use_preview,
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


def check_previous_messages(arxiv_id):
    if not os.path.exists("data/messages.txt"):
        open("data/messages.txt", "w").close()
    
    with open("data/messages.txt", "r") as f:
        for line in f:
            if not line.strip():
                continue

            prev_arxiv_id, message_link = line.strip().split("\t")
            if arxiv_id == prev_arxiv_id:
                return True, message_link

    return False, None


def get_chat_history(client, channel, thread_ts):
    thread_history = client.conversations_replies(
        channel=channel,
        ts=thread_ts
    )
    
    first_user_message_idx = None
    for idx, message in enumerate(thread_history.data["messages"]):
        # First message could be either user or bot. Therefore, skip it.
        if idx == 0:
            continue
        
        if "bot_id" in message:
            continue
        
        first_user_message_idx = idx
        break
    
    if first_user_message_idx is None:
        return []
    
    bot_user_id = os.getenv("SLACK_BOT_USER_ID")
    
    chat_history = []
    for message in thread_history.data["messages"][first_user_message_idx:]:
        if message["user"] == bot_user_id:
            content = message["text"]
            chat_history.append({"role": "assistant", "content": content})
        else:
            content = message["text"]
            if not content.startswith(f"<@{bot_user_id}>"):
                continue
            
            content = content.replace(f"<@{bot_user_id}>", "").strip()
            
            user_id = message["user"]
            content = f"User <@{user_id}>: {content}"
            chat_history.append({"role": "user", "content": content})
    
    return chat_history


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
    
    prev_message_exists, prev_message_link = check_previous_messages(arxiv_id)
    if prev_message_exists:
        existence_message = f"Paper <{prev_message_link}|{arxiv_id}> already posted"
        post_message(client, channel, existence_message, message_ts, use_preview=True)
        return message_ts

    if len(categories) > 0:
        pattern = r"(.*)\s*\((.*)\)"
        
        if not os.path.exists("data/categories"):
            os.makedirs("data/categories", exist_ok=True)

        available_categories = os.listdir("data/categories")
        sub_category_candidates = []

        if os.path.exists("data/categories/custom"):
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

    with open("data/messages.txt", "a") as f:
        message_link = f"https://upstageai.slack.com/archives/{channel}/p{message_ts.replace('.', '')}"
        f.write(f"{arxiv_id}\t{message_link}\n")

    return message_ts
