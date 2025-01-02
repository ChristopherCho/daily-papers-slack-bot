import os

from utils.paper_utils import get_images_from_pdf


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
    message_ts = None
):
    message = f"<{link}|*{title}*>"
    message_ts = post_message(client, channel, message, message_ts)

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
