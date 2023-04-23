import datetime
import dateparser
import http.client
import json
import os

from dotenv import load_dotenv
load_dotenv()

import agent
import api
import code
import commands_text
import memory as mem

from gcsa.google_calendar import GoogleCalendar
from gcsa.event import Event

from dataclasses import dataclass

@dataclass
class State:
    """Class to keep track of command state."""
    task_completed: bool = False
    final_answer: str = None

def get_command(response):
    try:
        response_json = json.loads(response)
        command = response_json["command"]
        command_name = command["name"]
        arguments = command["args"]

        if not arguments:
            arguments = {}

        return command_name, arguments
    except json.decoder.JSONDecodeError:
        return "GetCommandError", "Invalid JSON"
    except Exception as e:
        return "GetCommandError", str(e)


def execute_command(state, command_name, arguments):
    try:
        if command_name == "memory_add":
            return commit_memory(arguments["key"], arguments["string"])
        elif command_name == "memory_del":
            return delete_memory(arguments["key"])
        elif command_name == "memory_ovr":
            return overwrite_memory(arguments["key"], arguments["string"])
        elif command_name == "code_add":
            return add_code(arguments["key"], arguments["description"], arguments["args"], arguments["code"])
        elif command_name == "code_execute":
            return execute_code(arguments["key"], arguments["args"])
        elif command_name == "search":
            return search_serper(arguments["query"])
        elif command_name == "browse_website":
            return browse_website(arguments["url"])
        elif command_name == "call_agent":
            return call_agent(arguments["task"], arguments["agent_type"], arguments)
        elif command_name == "question_answer":
            return question_answer(arguments["url_or_filename"], arguments["question"])
        elif command_name == "get_text_summary":
            return get_text_summary(arguments["text"], arguments["hint"])
        elif command_name == "get_dow":
            return get_dow(arguments["date"])
        elif command_name == "count_words":
            return commands_text.count_words(arguments["text"])
        elif command_name == "count_characters":
            return commands_text.count_characters(arguments["text"])
        elif command_name == "get_datetime":
            return get_datetime()
        elif command_name == "calendar_get_events":
            time_min = datetime.datetime.fromisoformat(arguments["time_min"]) if "time_min" in arguments and arguments["time_min"] != "" else None
            time_max = datetime.datetime.fromisoformat(arguments["time_max"]) if "time_max" in arguments and arguments["time_max"] != "" else None
            return calendar_get_events(time_min, time_max)
        elif command_name == "calendar_get_single_event":
            return calendar_get_single_event(arguments["event_id"])
        elif command_name == "calendar_update_event":
            if "send_notifications" not in arguments: arguments["send_notifications"] = ""
            if "location" not in arguments: arguments["location"] = ""
            if "description" not in arguments: arguments["description"] = ""
            if "start" not in arguments: arguments["start"] = ""
            if "end" not in arguments: arguments["end"] = ""
            return calendar_update_event(arguments["event_id"], arguments["send_notifications"], arguments["start"], arguments["end"], arguments["location"], arguments["description"])
        elif command_name == "calendar_add_event":
            return calendar_add_event(arguments["text"], arguments["send_notifications"])
        elif command_name == "task_complete":
            return task_complete(state, arguments["final_answer"])
        elif command_name == "list_notes":
            return list_notes()
        elif command_name == "write_note":
            return write_note(arguments["filename"], arguments["content"])
        elif command_name == "append_note":
            return append_note(arguments["filename"], arguments["content"])
        elif command_name == "read_note":
            return read_note(arguments["filename"])
        else:
            return f"Unknown command {command_name}"
    # All errors, return "Error: + error message"
    except Exception as e:
        return "Error: " + str(e)


def call_agent(task, agent_type, arguments):
    try:
        return agent.call_agent(task, agent_type, arguments)
    except Exception as e:
        return f"Error calling agent: {e}"


def list_notes():
    try:
        return os.listdir("./data/notes")
    except Exception as e:
        return f"Error listing dir: {e}"

def append_note(key, content):
    try:
        with open(f"./data/notes/{key}", "a+") as f:
            f.write(f"{content}\n")
    except Exception as e:
        return f"Error writing: {e}"

    return "OK wrote to file"


def write_note(key, content):
    try:
        with open(f"./data/notes/{key}", "w+") as f:
            f.write(f"{content}\n")
    except Exception as e:
        return f"Error writing: {e}"

    return "OK wrote to file"

def read_note(key):
    try:
        with open(f"./data/notes/{key}", "r") as f:
            content = f.read().strip()
    except Exception as e:
        return f"Error writing: {e}"

    return f"File content: {content}"


def calendar_update_event(event_id, send_notifications, start, end, location, description):
    try:
        calendar = GoogleCalendar(os.environ["CALENDAR_USER"], token_path=os.environ["CALENDAR_TOKEN_PATH"])
        event = calendar.get_event(event_id)
        send_updates = 'all' if send_notifications.lower() == "true" else 'none'
        if len(start.strip()) != 0:
            event.start = datetime.datetime.fromisoformat(start)
        if len(end.strip()) != 0:
            event.end = datetime.datetime.fromisoformat(end)
        if len(location.strip()) != 0:
            event.location = location.strip()
        if len(description.strip()) != 0:
            event.description= description.strip()

        calendar.update_event(event, send_updates=send_updates)
    except Exception as e:
        return f"Error updating event: {e}"

    return "OK - updated event"


def calendar_get_single_event(event_id):
    try:
        calendar = GoogleCalendar(os.environ["CALENDAR_USER"], token_path=os.environ["CALENDAR_TOKEN_PATH"])
        event = calendar.get_event(event_id)
        event_str = str(event).replace(" - ", " - title: '")
        return f"{event_str}' location: '{event.location}' description: '{event.description}' attendees: '{event.attendees}' recurrence: '{event.recurrence}'"
    except Exception as e:
        return f"Error getting event: {e}"

    return "Unused"


def calendar_add_event(text, send_notifications):
    try:
        send_updates = 'all' if send_notifications.lower() == "true" else 'none'
        calendar = GoogleCalendar(os.environ["CALENDAR_USER"], token_path=os.environ["CALENDAR_TOKEN_PATH"])
        calendar.add_quick_event(text, send_updates=send_updates)
    except Exception as e:
        return f"Error adding: {e}"

    return "OK adding event"


def calendar_get_events(time_min, time_max):
    try:
        calendar = GoogleCalendar(os.environ["CALENDAR_USER"], token_path=os.environ["CALENDAR_TOKEN_PATH"])
        events = calendar.get_events(time_min=time_min, time_max=time_max, single_events=True)
        results = []
        for event in events:
            event_str = str(event).replace(" - ", " - title: '")
            results.append(f"{event_str}' id: '{event.id}'")
        return '\n'.join(results)
    except Exception as e:
        return f"Error getting event: {e}"

    return "Unused"

def calendar_delete_event(event_id):
    try:
        calendar = GoogleCalendar(os.environ["CALENDAR_USER"], token_path=os.environ["CALENDAR_TOKEN_PATH"])
        calendar.delete_event(event_id)
    except Exception as e:
        return f"Error deleting: {e}"

    return "OK deleting event"


def add_code(key, description, args, code_str):
    if not isinstance(args, dict):
        return f"args: {args_str} is not a python dict"

    present = key in mem.code_memory
    mem.code_memory[key] = {
            'description': description,
            'args': args,
            'code': code_str}
    return f"Overwritten code {key}" if present else f'Added code {key}'


def execute_code(key, args):
    if key not in mem.code_memory:
        return f"{key} not found in code memory."

    if not isinstance(args, dict):
        return f"args: {args_str} is not a python dict"

    code_item = mem.code_memory[key]

    vars = args
    vars["args"] = args
    return code.execute_python_code(code_item["code"], vars)


def get_dow(date_string):
    date_object = dateparser.parse(date_string)
    day_of_week = date_object.strftime("%A")
    return day_of_week

def search_serper(query, api_key=os.environ["SERPER_API_KEY"]):
    conn = http.client.HTTPSConnection("google.serper.dev")
    payload = json.dumps({
      "q": query
    })
    headers = {
      'X-API-KEY': api_key,
      'Content-Type': 'application/json'
    }
    conn.request("POST", "/search", payload, headers)
    res = conn.getresponse()
    data = res.read()
    return data.decode("utf-8")


def question_answer(url_or_filename, question):
    return commands_text.question_answer(url_or_filename, question)


def browse_website(url):
    summary = website_summary(url)
    links = get_hyperlinks(url)

    # Limit links to 5
    if len(links) > 5:
        links = links[:5]

    result = f"""Website Content Summary: {summary}\n\nLinks: {links}"""

    return result


def get_hyperlinks(url):
    link_list = commands_text.scrape_links(url)
    return link_list


def website_summary(url):
    text = commands_text.scrape_text(url)
    summary = commands_text.summarize_text(text, "details about the content and not about the site or business")
    return """ "Result" : """ + summary


def get_datetime():
    return "Current date and time: " + \
        datetime.datetime.now().strftime("%Y-%m-%d %A %H:%M:%S")


def get_text_summary(text, hint=None):
    summary = commands_text.summarize_text(text, hint, is_website=False)
    return """ "Result" : """ + summary


def commit_memory(key, string):
    _text = f"""Committing memory with string "{string}" """
    mem.permanent_memory[key] = string
    with open("./data/memory.txt", "w") as f:
        f.write(json.dumps(mem.permanent_memory))
    return _text


def delete_memory(key):
    if key in mem.permanent_memory:
        _text = "Deleting memory with key " + str(key)
        del mem.permanent_memory[key]
        with open("./data/memory.txt", "w") as f:
            f.write(json.dumps(mem.permanent_memory))
        return _text
    else:
        return "Invalid key, cannot delete memory."

def load_memory():
    memory_path = "./data/memory.txt"
    if os.path.isfile(memory_path):
        with open(memory_path, "r") as f:
            data = f.read()
            mem.permanent_memory = json.loads(data)
        return "Loaded memory from file"

    return f"No memory file found. Current memory: {mem.permanent_memory}"

def task_complete(state, answer):
    print(f"FINAL ANSWER: {answer}")
    state.task_completed = True
    state.final_answer = answer
    return "Task Completed!"
