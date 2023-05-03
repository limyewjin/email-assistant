import chat
import commands
import constants
import memory as mem
import prompt_data

from colorama import Fore, Style
import json
import logging
import yaml

agent_types = {}


def init_agents():
    global agent_types

    with open(f"{constants.AGENTS_FILE}", "r") as f:
        agent_types = yaml.safe_load(f)

    for agent_type in agent_types:
        agent = agent_types[agent_type]
        prompt = f"{agent['instructions']}\n\n{agent['prompt']}"
        agent["full_prompt"] = prompt

    # Construct main agent
    instructions = prompt_data.load_instructions()
    prompt = prompt_data.load_prompt()
    agents = "AGENT TYPE:\n\n"
    for i, agent_type in enumerate(agent_types):
        agents += f"{i+1}. {agent_type}: {agent_types[agent_type]['description']}\n"
    full_prompt = f"{instructions}\n\n{agents}\n\n{prompt}"
    agent_types["main"] = { "full_prompt": full_prompt }

    logging.info(f"Loaded agents: {agent_types.keys()}")


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


def call_agent(task, agent_type = "main", arguments = {}):
    """Call an agent to perform a task.

    Args:
        task: Task to perform
        agent_type: Type of agent
        arguments: dict of arguments

    Returns:
        final_answer from agent
    """
    if agent_type not in agent_types:
        return f"agent_type '{agent_type}' not found"

    agent = agent_types[agent_type]

    if agent_type == "main":
        context = chat.Context(
                permanent_memory = mem.permanent_memory,
                code_memory = mem.code_memory)
    else:
        context = chat.Context()

    token_limit = 8000

    task_request = task
    for key in arguments:
        if key in ['task', 'agent_type']: continue
        task_request += f" {key}: {arguments[key]}"
    
    command_state = commands.State()

    num_iterations = 0
    while num_iterations < 50 and command_state.task_completed == False:
        assistant_reply = chat.chat_with_ai(
                agent["full_prompt"],
                task_request if num_iterations == 0 else '',
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

            if (len(context.full_message_history) > 3 and
                context.full_message_history[-1]["role"] == "assistant" and
                context.full_message_history[-3]["role"] == "assistant" and
                context.full_message_history[-1]["content"] == context.full_message_history[-3]["content"]):
                nudge += " You are repeating responses - DO NOT REPEAT YOUR LAST RESPONSE."

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
        command_result = commands.execute_command(command_state, command_name, arguments)
        result = f"Command {command_name} returned: {command_result}"

        if command_name == "code_execute" and command_result == "('', '')":
            nudge = "If you were expecting results from 'code_execute', remember that results need to be printed."
            chat.create_chat_message("user", nudge, context)

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
    if command_state.task_completed and command_state.final_answer is not None:
        result = command_state.final_answer

    return result


