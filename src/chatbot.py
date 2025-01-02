import os
import re

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from dotenv import load_dotenv

from utils.llm_utils import get_answer
from utils.paper_utils import download_paper, get_title_from_arxiv, get_abstract_from_arxiv
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
            title = get_title_from_arxiv(arxiv_link)
            abstract = get_abstract_from_arxiv(arxiv_link)
        except Exception as e:
            update_message(client, channel, "Sorry, I couldn't get the title or abstract from the arxiv.", loading_message_ts)
            return

        feed_paper(client, channel, arxiv_id, arxiv_link, title, abstract, dp_path, message_ts)
        delete_message(client, channel, loading_message_ts)


if __name__ == "__main__":
    SocketModeHandler(app, os.environ.get("SLACK_APP_TOKEN")).start()
