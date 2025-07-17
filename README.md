# Daily paper feed bot for Slack

## Setup
### Install the dependencies
```bash
pip install -r requirements.txt
```

### Create a Slack app
We use slack-bolt to create a Slack app. Follow the [website](https://tools.slack.dev/bolt-python/getting-started/) and create an app.  
Following settings may need to be done additionally.
1. Add slash command: add `/add_category` command on Slash Commands tab
2. Add scopes: On the `OAuth & Permissions` tab, add `app_mentions:read`, `channels:history`, `channels:read`, `chat:write`, `commands`, `files_write`, `groups:history` to the Bot Token Scopes.
3. Add event subscriptions: On the `Event Subscriptions` tab, add `app_mentions` to the Subscribe to bot events section.

### Setup the environment variables
Following environment variables need to be set.
```bash
SLACK_CHANNEL_ID=""
SLACK_APP_ID=""
SLACK_BOT_USER_ID=""
SLACK_BOT_TOKEN=""
SLACK_APP_TOKEN=""

OPENAI_API_KEY=""

UPSTAGE_API_KEY=""
```

- `SLACK_CHANNEL_ID`: The channel ID to post the daily paper feed. You can find it on the `About` tab of the Slack channel. It is in the format of `CXXXXXXXXXX`.
- `SLACK_APP_ID`: The app ID of the Slack app. You can find it on the `Basic Information` tab of the Slack app.
- `SLACK_BOT_USER_ID`: The bot user ID of the Slack app. You can find it on the Profile of the Slack app. Click the `...` button on the right and select `Copy member ID`.
- `SLACK_BOT_TOKEN`: The bot token of the Slack app. You can find it on the `OAuth & Permissions` tab of the Slack app. It is in the format of `xoxb-...`.
- `SLACK_APP_TOKEN`: The app token of the Slack app. You can find it on the `App-Level Tokens` section in the `Bot Token` tab of the Slack app. It is in the format of `xapp-...`.
- `OPENAI_API_KEY`: The API key of the OpenAI API.
- `UPSTAGE_API_KEY`: The API key of the Upstage API.

### Run the bot
#### Run daily paper feed bot
```bash
python src/feeder.py
```

#### Run chatbot
```bash
python src/chatbot.py
```

### Add bot to Slack channel
Add the bot to the Slack channel you specified. You can use the `Add apps to this channel` shortcut on the Slack channel.

## Usage
### Daily feed
To post the daily feed, run the daily feed bot.  
The bot will post the top 5 papers of 7 days before today to the Slack channel you specified. The papers are collected from [HuggingFace Papers](https://huggingface.co/papers).  
The bot collects the papers' information from the HuggingFace Papers and Arxiv. Additionally, it uses the Upstage Document Parse to extract the text and images from the papers. Then, it posts following information in the thread:
- Title
- Related categories (if any)
- Abstract
- First 3 images, charts or tables

### Chatbot
To use the chatbot, you can simply mention the bot in the Slack channel.

#### Request paper information
You can request the paper information by mentioning the bot with the paper's Arxiv ID (in the format of 0000.00000) or link.  
It'll post the paper's information just like the daily feed in the thread.


#### QA on the paper
Mention the bot in the thread of the daily feed or the paper information request. The bot will answer the question based on the paper's content using the `gpt-4o-mini` model.  
Specifically, the bot will feed the Document Parse result of the paper to the model as context and ask the model to answer the question.

### Additional features
- Add category: You can add a custom category for categorizing the paper. The bot will check whether the given category or any similar category exists and ask you to confirm the addition.
  - `/add_category <category_name>`: Add a custom category.
