import os

from apscheduler.schedulers.blocking import BlockingScheduler
from datetime import datetime, timedelta
from slack_bolt import App
from dotenv import load_dotenv

from utils.paper_utils import pull_hf_daily, get_images_from_pdf
from utils.slack_utils import feed_paper, post_message


load_dotenv()

app = App(token=os.environ.get("SLACK_BOT_TOKEN"))
client = app.client

feed_channel = os.environ.get("SLACK_CHANNEL_ID")


def daily_feed():
    papers = pull_hf_daily()

    last_week = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    message = f"_*Top 5 papers at {last_week}*_"
    post_message(client, feed_channel, message)
    
    for paper in papers:
        title = paper["title"]
        arxiv_id = paper["arxiv_id"]
        link = paper["link"]
        abstract = paper["abstract"] if "abstract" in paper else ""
        dp_path = paper["dp_path"] if "dp_path" in paper else ""

        feed_paper(client, feed_channel, arxiv_id, link, title, abstract, dp_path)


if __name__ == "__main__":
    scheduler = BlockingScheduler()
    scheduler.add_job(daily_feed, "cron", hour=9, minute=0)
    scheduler.start()
