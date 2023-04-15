import os
import time
from dotenv import load_dotenv

import api

import logging
import sys

# Configure the logging module to log to both stdout and stderr
log_format = '%(asctime)s %(levelname)s %(module)s %(funcName)s %(message)s'
logging.basicConfig(level=logging.INFO, format=log_format, stream=sys.stdout)
console = logging.StreamHandler(sys.stderr)
console.setLevel(logging.ERROR)
console.setFormatter(logging.Formatter(log_format))
logging.getLogger('').addHandler(console)

full_message_history = []
working_message_history = []

def reset():
    global full_message_history, working_message_history
    full_message_history = []
    working_message_history = []

def create_chat_message(role, content):
    """
    Create a chat message with the given role and content.
    Args:
    role (str): The role of the message sender, e.g., "system", "user", or "assistant".
    content (str): The content of the message.
    Returns:
    dict: A dictionary containing the role and content of the message.
    """
    global full_message_history, working_message_history

    message = {"role": role, "content": content}
    full_message_history.append(message)
    working_message_history.append(message)


def optimize_messages(messages):
    if len(messages) == 0: return []

    condensed_messages = []

    combined_messages = " ".join([f"{msg['role']}:{msg['content']}" for msg in messages])

    # Summarize user and assistant messages together
    summary = api.generate_response([
        {"role": "system", "content": f"""Your task is to optimize a conversation by summarizing and condensing the messages received so far, while maintaining the context and crucial information. The original system message is passed to you for context, do not repeat it. Based on your understanding of the conversation, provide a concise message for each part of the conversation, excluding the first system prompt, retaining any relevant information needed to answer the user request."""},
        {"role": "user", "content": f"Conversation so far:```\n{combined_messages}\n```\nSummarize the conversation while maintaining its structure and goal for the assistant."}],
        model="gpt-4")

    # Split the summary into separate messages based on their roles
    for message in summary.split("\n"):
        lower_message = message.lower()
        if lower_message.startswith("user:"):
            condensed_messages.append({"role": "user", "content": message[len("user:"):].strip()})
        elif lower_message.startswith("system:"):
            condensed_messages.append({"role": "system", "content": message[len("system:"):].strip()})
        elif lower_message.startswith("assistant:"):
            condensed_messages.append({"role": "assistant", "content": message[len("assistant:"):].strip()})

    if len(condensed_messages) == 0:
        # it's probably a blob representing what the user said.
        condensed_messages.append({"role": "user", "content": summary.strip()})

    return condensed_messages


def chat_with_ai(
        prompt,
        user_input,
        permanent_memory,
        code_memory,
        token_limit,
        debug=False):
    global full_message_history, working_message_history

    code_memory_short = {
            key: {
                'description': code_memory[key]['description'],
                'args': code_memory[key]['args'] 
            }
            for key in code_memory }
    current_context = [
            create_chat_message("system", prompt),
            create_chat_message("system", f"Permanent memory: {permanent_memory}"),
            create_chat_message("system", f"Code memory: {code_memory_short}"),
            ]

    num_current_context_tokens = sum(len(msg["content"].split()) for msg in current_context) + len(prompt.split())
    num_working_message_history_tokens = sum(len(msg["content"].split()) for msg in working_message_history)

    if num_current_context_tokens + num_working_message_history_tokens > token_limit / 2:
        # Optimize the messages using the `optimize_messages` function
        logging.info("Optimizing conversation as it is getting too long")
        condensed_messages = optimize_messages(full_message_history[:-2])
        working_message_history = condensed_messages + full_message_history[-2:]
        logging.info(f"adding this to context: {condensed_messages + full_message_history[-2:]}")
    current_context.extend(working_message_history)

    if len(user_input.strip()) > 0:
        current_context.extend([create_chat_message("user", user_input)])

    # Debug print the current context
    if debug:
        print("------------ CONTEXT SENT TO AI ---------------")
        for message in current_context:
            # Skip printing the prompt
            if message["role"] == "system" and message["content"] == prompt:
                continue
            print(f"{message['role'].capitalize()}: {message['content']}")
        print("----------- END OF CONTEXT ----------------")

    assistant_reply = api.generate_response(current_context, model="gpt-4").strip()

    # Update message history
    if len(user_input.strip()) > 0: create_chat_message("user", user_input)
    create_chat_message("assistant", assistant_reply)
    return assistant_reply
