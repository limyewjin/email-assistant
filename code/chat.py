import os
import time
from dotenv import load_dotenv

import api

import logging
import sys

from dataclasses import dataclass

@dataclass
class Context:
    """Class to keep track of chat context."""
    full_message_history: list[str] = None
    working_message_history: list[str] = None
    permanent_memory: dict = None
    code_memory: dict = None

    def __post_init__(self):
        self.full_message_history = self.full_message_history or []
        self.working_message_history = self.working_message_history or []
        self.permanent_memory = self.permanent_memory or {}
        self.code_memory = self.code_memory or {}

def create_chat_message(role, content, context, add_to_history=True):
    """
    Create a chat message with the given role and content.
    Args:
    role (str): The role of the message sender, e.g., "system", "user", or "assistant".
    content (str): The content of the message.
    Returns:
    dict: A dictionary containing the role and content of the message.
    """
    message = {"role": role, "content": content}
    if add_to_history:
        context.full_message_history.append(message)
        context.working_message_history.append(message)
    return message


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
        context,
        token_limit,
        debug=False):
    code_memory_short = {
            key: {
                'description': context.code_memory[key]['description'],
                'args': context.code_memory[key]['args'] 
            }
            for key in context.code_memory }
    current_context = [
            create_chat_message("system", prompt, context, False),
            create_chat_message("system", f"Permanent memory: {context.permanent_memory}", context, False),
            create_chat_message("system", f"Code memory: {code_memory_short}", context, False),
            ]

    num_current_context_tokens = sum(len(msg["content"].split()) for msg in current_context) + len(prompt.split())
    num_working_message_history_tokens = sum(len(msg["content"].split()) for msg in context.working_message_history)

    if num_current_context_tokens + num_working_message_history_tokens > token_limit / 2:
        # Optimize the messages using the `optimize_messages` function
        logging.info("Optimizing conversation as it is getting too long")
        condensed_messages = optimize_messages(context.full_message_history[:-2])
        context.working_message_history = condensed_messages + context.full_message_history[-2:]
        logging.info(f"adding this to context: {condensed_messages + context.full_message_history[-2:]}")

    if len(user_input.strip()) > 0:
        create_chat_message("user", user_input, context)

    current_context.extend(context.working_message_history)

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
    create_chat_message("assistant", assistant_reply, context)

    return assistant_reply
