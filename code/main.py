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

commands.load_memory()

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
    token_limit = 6000
    result = None

    # Special
    context = chat.Context(
            permanent_memory = mem.permanent_memory,
            code_memory = mem.code_memory)

    commands.task_completed = False
    commands.final_answer = None
    num_iterations = 0
    while num_iterations < 50 and commands.task_completed == False:
        assistant_reply = chat.chat_with_ai(
                prompt,
                request if num_iterations == 0 else '',
                context,
                token_limit, True)
        print_assistant_thoughts(assistant_reply)

        # Get command name and arguments
        command_name = ""
        try:
            command_name, arguments = commands.get_command(assistant_reply)
            command_name = command_name.strip()
        except Exception as e:
            notes = "Error encountered while trying to parse response: {e}."
            chat.create_chat_message("user", notes, context)
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
                            nudge += ' Extranous text found in response that makes response invalid JSON. Remove extra text and just return JSON response.'

                nudge += " Next response should follow RESPONSE FORMAT."

            chat.create_chat_message("user", nudge, context)
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
                chat.create_chat_message("system", nudge, context)
            else:
                chat.create_chat_message("system", result, context)
            if len(result) > 100:
                print_to_console("SYSTEM: ", Fore.YELLOW, result[:100] + "...")
            else:
                print_to_console("SYSTEM: ", Fore.YELLOW, result)
        else:
            chat.create_chat_message("system", "Unable to execute command", context)
            print_to_console("SYSTEM: ", Fore.YELLOW, "Unable to execute command")

        print()
        num_iterations += 1

    result = "No answer found."
    if commands.task_complete and commands.final_answer is not None:
        result = commands.final_answer

    return result

if not args.testconsole:
    email_helper.check_email_login()
logging.info("Done initializing. Now looping.")

# Loop indefinitely and check for new emails as they arrive, or handle the user-set alarm
while True:
    if args.testconsole:
        user_input = input("User: ").strip()
        final_answer = resolve_request(f"Subject: help Body: {user_input}")
        print(final_answer)
        print()
    else:
        msg = email_helper.inner_loop_check()
        if msg is not None:
            email_helper.send_email(f"Re: {msg.subject}", "Received request. I'm working on it", msg.text, msg.from_)
            final_answer = resolve_request(f"Subject: {msg.subject} Body: {msg.text.strip()}")
            email_helper.send_email(f"Re: {msg.subject}", final_answer, msg.text, msg.from_)
