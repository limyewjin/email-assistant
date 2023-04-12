# GPT-4 Email Assistant
This project provides a GPT-4 email assistant that responds to emails and fulfills various tasks for the user. The assistant has access to numerous commands, resources, and can interact with Google Calendar API. To set up the project, follow the instructions below.

## Requirements
Python 3.8 or higher

## Setup

1. Install the required packages using requirements.txt:

``` bash
pip install -r requirements.txt
```

2. Follow the instructions at Google Calendar Simple API [Getting Started](https://google-calendar-simple-api.readthedocs.io/en/latest/getting_started.html) to set up the Google Calendar API credentials.

## Environment Variables

To set up environment variables for the project, rename the `sample_env` file to `.env` and fill in the necessary information. Here's a description of each variable:

* `OPENAI_API_KEY`: Your OpenAI API key for the GPT-4 model.
* `SERPER_API_KEY`: Your Serpstack API key for search functionality.
* `EMAIL_USER`: The email address of your bot.
* `EMAIL_PASSWORD`: The API key or password for your bot's email account.
* `EXPECTED_SENDERS`: A comma-separated list of email addresses that are allowed to send commands to the bot.

Example:

```plaintext
OPENAI_API_KEY=your_openai_key
SERPER_API_KEY=your_serper_key
EMAIL_USER=your_bot_email@example.com
EMAIL_PASSWORD=your_bot_email_password
EXPECTED_SENDERS=user1@example.com,user2@example.com
```

## Running
Run the email assistant which runs in a loop:

``` bash
python code/main.py
```


