import os

from apscheduler.schedulers.blocking import BlockingScheduler
from datetime import datetime, timedelta
from slack_bolt import App
from dotenv import load_dotenv

from get_papers import pull_hf_daily
from dp import get_images_from_pdf

load_dotenv()

app = App(token=os.environ.get("SLACK_BOT_TOKEN"))
client = app.client


def post_message(message: str, message_ts: str = None):
    message_data = client.chat_postMessage(
        channel=os.environ.get("SLACK_CHANNEL_ID"), 
        text=message,
        unfurl_links=False,
        unfurl_media=False,
        thread_ts=message_ts
    )

    return message_data.data["ts"]


def daily_feed():
    papers = pull_hf_daily()

    last_week = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    message = f"_*Top 5 papers at {last_week}*_"
    post_message(message)
    
    for paper in papers:
        title = paper["title"]
        arxiv_id = paper["arxiv_id"]
        link = paper["link"]
        dp_path = paper["dp_path"]

        message = f"<{link}|*{title}*>"
        message_ts = post_message(message)
        
        abstract = paper["abstract"]
        if abstract:
            abstract = f"*Abstract*\n{abstract}"
            post_message(abstract, message_ts)

        if dp_path:
            images = get_images_from_pdf(dp_path)
            for i, image in enumerate(images):
                client.files_upload_v2(
                    channels=os.environ.get("SLACK_CHANNEL_ID"),
                    file=image,
                    title=f"{arxiv_id}.{i}",
                    thread_ts=message_ts
                )


if __name__ == "__main__":
    scheduler = BlockingScheduler()
    scheduler.add_job(daily_feed, "cron", hour=9, minute=0)
    scheduler.start()
