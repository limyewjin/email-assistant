import re
import logging
import sys
import time

from colorama import Fore, Style
import json
import os

import agent
import api
import chat
import commands
import constants
import memory as mem

import email_helper

import argparse
parser = argparse.ArgumentParser()
parser.add_argument('--testconsole', action='store_true')
args = parser.parse_args()

# Configure the logging module to log to both stdout and stderr
log_format = '%(asctime)s %(levelname)s %(module)s:%(lineno)d %(funcName)s %(message)s'
console = logging.StreamHandler(sys.stderr)
console.setLevel(logging.INFO)
console.setFormatter(logging.Formatter(log_format))

root_logger = logging.getLogger()
# Remove all existing handlers
for handler in root_logger.handlers:
    root_logger.removeHandler(handler)
root_logger.setLevel(logging.INFO)
root_logger.addHandler(console)

# initializations
commands.load_memory()
agent.init_agents()

if not args.testconsole:
    email_helper.check_email_login()
logging.info("Done initializing. Now looping.")

# Loop indefinitely and check for new emails as they arrive, or handle the user-set alarm
while True:
    if args.testconsole:
        user_input = input("User: ").strip()
        final_answer = agent.call_agent(f"Subject: help Body: {user_input}")
        print(final_answer)
        print()
    else:
        msg = email_helper.inner_loop_check()
        if msg is not None:
            email_helper.send_email(f"Re: {msg.subject}", "Received request. I'm working on it", msg.text, msg.from_)
            final_answer = agent.call_agent(f"Subject: {msg.subject} Body: {msg.text.strip()}")
            email_helper.send_email(f"Re: {msg.subject}", final_answer, msg.text, msg.from_)
