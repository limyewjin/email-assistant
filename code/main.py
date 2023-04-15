from imap_tools import MailBox, A
import datetime
import email
import re
import logging
import sys
import time

from colorama import Fore, Style
import json
import os

import api
import chat
import commands
import memory as mem
import prompt_data

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Configure the logging module to log to both stdout and stderr
log_format = '%(asctime)s %(levelname)s %(module)s %(funcName)s %(message)s'
logging.basicConfig(level=logging.INFO, format=log_format, stream=sys.stdout)
console = logging.StreamHandler(sys.stderr)
console.setLevel(logging.ERROR)
console.setFormatter(logging.Formatter(log_format))
logging.getLogger('').addHandler(console)

from dotenv import load_dotenv
import os
load_dotenv()

# Define the email account details
email_user = os.environ["EMAIL_USER"]
email_password = os.environ["EMAIL_PASSWORD"]
imap_server = 'imap.gmail.com'
imap_port = 993

# Define the expected sender email address
expected_senders = os.environ["EXPECTED_SENDERS"].strip().split(',')

# Timeout to use around connections and requests.
TIMEOUT = 60 * 10

commands.load_memory()


def send_email(subject, body, original_msg, recipient, sender=email_user, password=email_password):
    #msg = MIMEText(body)
    msg = MIMEMultipart()
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = recipient

    # quote the original email
    quoted_body = f"{body}\n\n----- Original Message -----\n"
    for line in original_msg.split('\n'):
        quoted_body += f"> {line}\n"

    # attach the quoted body to the MIME message
    msg.attach(MIMEText(quoted_body, 'plain'))

    smtp_server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
    smtp_server.login(sender, password)
    smtp_server.sendmail(sender, [recipient], msg.as_string())
    smtp_server.quit()


def print_to_console(
        title,
        title_color,
        content):
    print(f"{title_color}{title} {Style.RESET_ALL}{content}")


def print_assistant_thoughts(assistant_reply):
    try:
        # Parse and print Assistant response
        assistant_reply_json = json.loads(assistant_reply)

        assistant_thoughts = assistant_reply_json.get("thoughts")
        if assistant_thoughts:
            assistant_thoughts_text = assistant_thoughts.get("text")
            assistant_thoughts_reasoning = assistant_thoughts.get("reasoning")
            assistant_thoughts_plan = assistant_thoughts.get("plan")
            assistant_thoughts_criticism = assistant_thoughts.get("criticism")
            assistant_thoughts_speak = assistant_thoughts.get("speak")
        else:
            assistant_thoughts_text = None
            assistant_thoughts_reasoning = None
            assistant_thoughts_plan = None
            assistant_thoughts_criticism = None
            assistant_thoughts_speak = None

        print_to_console(
            f"THOUGHTS:",
            Fore.YELLOW,
            assistant_thoughts_text)
        print_to_console(
            "REASONING:",
            Fore.YELLOW,
            assistant_thoughts_reasoning)
        if assistant_thoughts_plan:
            print_to_console("PLAN:", Fore.YELLOW, "")
            # Split the input_string using the newline character and dash
            lines = assistant_thoughts_plan.split('\n')

            # Iterate through the lines and print each one with a bullet
            # point
            for line in lines:
                # Remove any "-" characters from the start of the line
                line = line.lstrip("- ")
                print_to_console("- ", Fore.GREEN, line.strip())
        print_to_console(
            "CRITICISM:",
            Fore.YELLOW,
            assistant_thoughts_criticism)
        print_to_console(
            "SPEAK:",
            Fore.YELLOW,
            assistant_thoughts_speak)
        print()

    except json.decoder.JSONDecodeError:
        print_to_console("Error: Invalid JSON\n", Fore.RED, assistant_reply)
    # All other errors, return "Error: + error message"
    except Exception as e:
        print_to_console("Error: \n", Fore.RED, str(e))


def construct_prompt():
    # Construct full prompt
    instructions = prompt_data.load_instructions()
    prompt = prompt_data.load_prompt()
    full_prompt = f"{instructions}\n\n{prompt}"
    return full_prompt

def resolve_request(request):
    # initialize variables
    prompt = construct_prompt()
    token_limit = 3000
    result = None
    full_message_history = []

    commands.task_completed = False
    commands.final_answer = None
    num_iterations = 0
    while num_iterations < 50 and commands.task_completed == False:
        assistant_reply = chat.chat_with_ai(
                prompt,
                request if num_iterations == 0 else '',
                full_message_history,
                mem.permanent_memory,
                mem.code_memory,
                token_limit, True)
        print_assistant_thoughts(assistant_reply)

        # Get command name and arguments
        command_name = ""
        try:
            command_name, arguments = commands.get_command(assistant_reply)
            command_name = command_name.strip()
        except Exception as e:
            notes = "Error encountered while trying to parse response: {e}."
            full_message_history.append(chat.create_chat_message("user", notes))
            print_to_console("Error: \n", Fore.RED, str(e))

        if len(command_name) == 0 or command_name == "GetCommandError":
            nudge = ""
            if len(command_name) == 0:
                nudge = "Empty command name found. Specify a valid command."

            if command_name == "GetCommandError":
                if arguments == "'command'":
                    nudge = '"command" not found in response. It cannot be empty.'
                elif arguments == "'name'":
                    nudge = '"command" does not contain "name" and it cannot be empty.'
                elif arguments == "'args'":
                    nudge = '"command" does not contain "args".'
                elif arguments == "Invalid JSON":
                    nudge = "Invalid JSON response."
                    if '"command"' not in assistant_reply and '"thoughts"' not in assistant_reply:
                        nudge += ' "command" and "thoughts" not found in response.'
                    elif '"command"' not in assistant_reply:
                        nudge += ' "command" not found in response.'
                    elif '"thoughts"' not in assistant_reply:
                        nudge += ' "thoughts" not found in response.'

                    if '"command"' in assistant_reply and '"thoughts"' in assistant_reply:
                        if assistant_reply.count('"command"') > 1 and assistant_reply.count('"thoughts"') > 1:
                            nudge += ' Multiple "command" and "thoughts" found. Return just one set.'
                        else:
                            nudge += ' Extranous text found in response that makes response invalid JSON.'

                nudge += " Next response should follow RESPONSE FORMAT."

            full_message_history.append(chat.create_chat_message("user", nudge))
            print_to_console("SYSTEM: ", Fore.YELLOW, f"{command_name} {arguments}")
            print()
            num_iterations += 1
            continue

        # Print command
        print_to_console(
            "NEXT ACTION: ",
            Fore.CYAN,
            f"COMMAND = {Fore.CYAN}{command_name}{Style.RESET_ALL}  ARGUMENTS = {Fore.CYAN}{arguments}{Style.RESET_ALL}")

        # Exectute command
        command_result = commands.execute_command(command_name, arguments)
        result = f"Command {command_name} returned: {command_result}"

        # Check if there's a result from the command append it to the message
        # history
        if result is not None:
            if command_result == f"Unknown command {command_name}":
                nudge = f"{result}. Specify only valid commands."
                full_message_history.append(chat.create_chat_message("system", nudge))
            else:
                full_message_history.append(chat.create_chat_message("system", result))
            if len(result) > 100:
                print_to_console("SYSTEM: ", Fore.YELLOW, result[:100] + "...")
            else:
                print_to_console("SYSTEM: ", Fore.YELLOW, result)
        else:
            full_message_history.append(
                chat.create_chat_message("system", "Unable to execute command"))
            print_to_console("SYSTEM: ", Fore.YELLOW, "Unable to execute command")

        print()
        num_iterations += 1

    result = "No answer found."
    if commands.task_complete and commands.final_answer is not None:
        result = commands.final_answer

    return result

with MailBox(imap_server).login(email_user, email_password, 'INBOX') as mailbox:
    logging.info("Login to email confirmed")

logging.info("Done initializing. Now looping.")

# Loop indefinitely and check for new emails as they arrive, or handle the user-set alarm
while True:
    sixty_minutes_ago = datetime.datetime.now() - datetime.timedelta(minutes=60)
    date_gte_criteria = sixty_minutes_ago.date()

    try:
        # waiting for updates TIMEOUT sec, print unseen immediately if any update
        with MailBox(imap_server).login(email_user, email_password, 'INBOX') as mailbox:
            msgs = [msg for msg in mailbox.fetch(A(seen=False, date_gte=date_gte_criteria))]
            if len(msgs) == 0:
                    responses = mailbox.idle.wait(timeout=TIMEOUT)
                    if responses:
                        msgs = [msg for msg in mailbox.fetch(A(seen=False, date_gte=date_gte_criteria))]
            if len(msgs) > 0:
                for msg in msgs:
                    if msg.from_ not in expected_senders: continue

                    # Check the "Received" headers for additional security
                    received_headers = msg.headers.get('received', [])
                    is_valid_email = False
                    for received_header in received_headers:
                        # check if the header contains a trusted domain
                        if 'google.com' in received_header:
                            is_valid_email = True
                            break

                    # Skip if the email is not valid based on the "Received" headers
                    if not is_valid_email:
                        continue

                    send_email(f"Re: {msg.subject}", "Received request. I'm working on it", msg.text, msg.from_)
                    final_answer = resolve_request(f"Subject: {msg.subject} Body: {msg.text.strip()}")
                    send_email(f"Re: {msg.subject}", final_answer, msg.text, msg.from_)
    except Exception as e:
        logging.error(f"Exception {e}")
