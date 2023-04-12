def load_prompt():
    try:
        with open("./data/prompt.txt", "r") as prompt_file:
            prompt = prompt_file.read()
        return prompt

    except FileNotFoundError:
        print("Error: Prompt file not found", flush=True)
        return""
