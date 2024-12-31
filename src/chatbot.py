import os
import re

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from dotenv import load_dotenv

from llm import get_answer

load_dotenv()

app = App(token=os.environ.get("SLACK_BOT_TOKEN"))
client = app.client


def _update_loading_message(client, loading_message_ts, text):
    client.chat_update(
        channel=os.environ.get("SLACK_CHANNEL_ID"),
        ts=loading_message_ts,
        text=text
    )


@app.event("app_mention")
def event_test(body, say):
    event = body["event"]
    if "thread_ts" in event:
        thread_ts = event["thread_ts"]
        text = event["text"]
        question = text.split(">", 1)[1].strip() if ">" in text else ""

        # Post a loading message
        loading_message = client.chat_postMessage(
            channel=event["channel"],
            text=":loading:",
            thread_ts=event["thread_ts"]
        )
        loading_message_ts = loading_message["ts"]
        
        # Get the original message
        response = client.conversations_replies(
            channel=event["channel"],
            ts=thread_ts
        )
        original_message = response["messages"][0]["text"]

        # Extract the arxiv ID from the original message
        pattern = r"<https://arxiv.org/abs/(.*)\|(.*)>"
        search_result = re.search(pattern, original_message)
        if search_result:
            arxiv_id = search_result.group(1)
        else:
            arxiv_id = None

        if arxiv_id is None:
            _update_loading_message(client, loading_message_ts, "Something went wrong. Sorry")
            return

        try:
            answer = get_answer(arxiv_id, question)
            _update_loading_message(client, loading_message_ts, answer)
        except Exception as e:
            _update_loading_message(client, loading_message_ts, "Something went wrong. Sorry")
            print(e)

    else:
        client.chat_postEphemeral(
            channel=event["channel"],
            user=event["user"],
            text="Please call me with a thread~ :sweat_smile:",
        )


if __name__ == "__main__":
    SocketModeHandler(app, os.environ.get("SLACK_APP_TOKEN")).start()
