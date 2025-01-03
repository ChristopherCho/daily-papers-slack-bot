import os
import re
import requests

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from dotenv import load_dotenv

from utils.llm_utils import get_answer, get_similar_categories
from utils.paper_utils import (
    download_paper, 
    get_arxiv_soup, 
    get_title_from_arxiv, 
    get_abstract_from_arxiv, 
    get_categories_from_arxiv
)
from utils.slack_utils import post_message, update_message, feed_paper, delete_message


load_dotenv()

app = App(token=os.environ.get("SLACK_BOT_TOKEN"))
client = app.client

app_id = os.environ.get("SLACK_APP_ID")
bot_user_id = os.environ.get("SLACK_BOT_USER_ID")


def _post_loading_message(channel, message_ts):
    return post_message(client, channel, ":loading:", message_ts)


@app.event("app_mention")
def event_test(body, say):
    event = body["event"]
    if "thread_ts" in event:
        thread_ts = event["thread_ts"]
        channel = event["channel"]
        loading_message_ts = _post_loading_message(channel, thread_ts)
        
        text = event["text"]
        question = text.replace(f"<@{bot_user_id}>", "").strip()
        if question == "":
            update_message(client, channel, "Please ask a question.", loading_message_ts)
            return

        # Extract the arxiv ID from the original message
        response = client.conversations_replies(
            channel=event["channel"],
            ts=thread_ts
        )
        first_app_message = next((msg for msg in response["messages"] if "app_id" in msg and msg["app_id"] == app_id), None)
        if first_app_message is None:
            update_message(client, channel, "Sorry, I couldn't find the arxiv ID in the original message.", loading_message_ts)
            return

        title_message = first_app_message["text"]        
        pattern = r"<https://arxiv.org/abs/(.*)\|(.*)>"
        search_result = re.search(pattern, title_message)
        if search_result:
            arxiv_id = search_result.group(1)
        else:
            update_message(client, channel, "Sorry, I couldn't find the arxiv ID in the original message.", loading_message_ts)
            return

        # Get the answer from the LLM
        try:
            answer = get_answer(arxiv_id, question)
            update_message(client, channel, answer, loading_message_ts)
        except Exception as e:
            update_message(client, channel, "Sorry, I couldn't get the response from the LLM.", loading_message_ts)
            return

    else:
        message_ts = event["ts"]
        channel = event["channel"]
        loading_message_ts = _post_loading_message(channel, message_ts)
        
        text = event["text"]
        arxiv_info = text.replace(f"<@{bot_user_id}>", "").strip()
        if arxiv_info == "":
            update_message(client, channel, "Please provide a valid arxiv ID or Link.", loading_message_ts)
            return

        arxiv_pdf_pattern = r"https://arxiv.org/pdf/\d{4}\.\d{4,5}"
        arxiv_link_pattern = r"https://arxiv.org/abs/\d{4}\.\d{4,5}"
        arxiv_id_pattern = r"\d{4}\.\d{4,5}"
        if re.search(arxiv_id_pattern, arxiv_info):
            arxiv_id = re.search(arxiv_id_pattern, arxiv_info).group(0)
        elif re.search(arxiv_pdf_pattern, arxiv_info):
            arxiv_id = re.search(arxiv_pdf_pattern, arxiv_info).group(0).split("/")[-1]
        elif re.search(arxiv_link_pattern, arxiv_info):
            arxiv_id = re.search(arxiv_link_pattern, arxiv_info).group(0).split("/")[-1]
        else:
            update_message(client, channel, "Please provide a valid arxiv ID or Link.", loading_message_ts)
            return
        arxiv_link = f"https://arxiv.org/abs/{arxiv_id}"

        paper_info = download_paper(arxiv_id)
        if paper_info is None:
            update_message(client, channel, "Sorry, I couldn't find the paper. Please check the arxiv ID or Link is valid.", loading_message_ts)
            return
        dp_path = paper_info["dp_path"]

        try:
            arxiv_soup = get_arxiv_soup(arxiv_link)
            title = get_title_from_arxiv(arxiv_soup)
            abstract = get_abstract_from_arxiv(arxiv_soup)
            categories = get_categories_from_arxiv(arxiv_soup)
        except Exception as e:
            update_message(client, channel, "Sorry, I couldn't get the title or abstract from the arxiv.", loading_message_ts)
            return

        feed_paper(client, channel, arxiv_id, arxiv_link, title, abstract, dp_path, categories, message_ts)
        delete_message(client, channel, loading_message_ts)


def _category_check_message_template(category, similar_categories=None):
    blocks = []
    if similar_categories is not None and len(similar_categories) > 0:
        similar_categories_str = "\n".join([f'- {category.strip()}' for category in similar_categories])
        blocks.extend([
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"I found some existing similar categories to *{category}*"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": similar_categories_str
                }
            }, 
        ])
    
    blocks.extend([
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"Do you want to add *{category}* to the list?"
            }
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "emoji": True,
                        "text": "Add"
                    },
                    "style": "primary",
                    "value": category,
                    "action_id": "action_add_category"
                },
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "emoji": True,
                        "text": "Cancel"
                    },
                    "style": "danger",
                    "value": category,
                    "action_id": "action_cancel_add_category"
                }
            ]
        }
    ])

    return {"blocks": blocks}


@app.command("/add_category")
def add_category(ack, body):
    ack()
    
    if body["text"] == "":
        return
    
    category = body["text"]
    already_exists, similar_categories = get_similar_categories(category)
    if already_exists:
        client.chat_postEphemeral(
            channel=body["channel_id"],
            user=body["user_id"],
            text=f"The category *{category}* already exists."
        )
    else:    
        block = _category_check_message_template(category, similar_categories)    
        client.chat_postEphemeral(
            channel=body["channel_id"],
            user=body["user_id"],
            blocks=block["blocks"]
        )


@app.action("action_add_category")
def add_category_action(ack, body):
    ack()
    category = body["actions"][0]["value"]
    
    with open("data/categories/custom", "a") as f:
        f.write(f"{category}\n")
    
    response_url = body["response_url"]
    requests.post(response_url, json={"text": f"The category *{category}* has been added successfully!"})


@app.action("action_cancel_add_category")
def cancel_add_category_action(ack, body):
    ack()
    response_url = body["response_url"]
    requests.post(response_url, json={"text": "Cancelled adding the category."})


if __name__ == "__main__":
    SocketModeHandler(app, os.environ.get("SLACK_APP_TOKEN")).start()
