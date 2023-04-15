def load_file(filename):
    try:
        with open(filename, "r") as prompt_file:
            prompt = prompt_file.read()
        return prompt.strip()

    except FileNotFoundError:
        print(f"Error: Prompt file {filename} not found", flush=True)
        return""


def load_prompt():
    return load_file("./data/prompt.txt")

def load_instructions():
    return load_file("./data/instructions.txt")
