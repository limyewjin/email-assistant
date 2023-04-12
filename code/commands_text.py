import requests
from bs4 import BeautifulSoup

import api

def scrape_text(url):
    response = requests.get(url)

    # Check if the response contains an HTTP error
    if response.status_code >= 400:
        return "Error: HTTP " + str(response.status_code) + " error"

    soup = BeautifulSoup(response.text, "html.parser")

    for script in soup(["script", "style"]):
        script.extract()

    text = soup.get_text()
    lines = (line.strip() for line in text.splitlines())
    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
    text = '\n'.join(chunk for chunk in chunks if chunk)

    return text


def extract_hyperlinks(soup):
    hyperlinks = []
    for link in soup.find_all('a', href=True):
        hyperlinks.append((link.text, link['href']))
    return hyperlinks


def format_hyperlinks(hyperlinks):
    formatted_links = []
    for link_text, link_url in hyperlinks:
        formatted_links.append(f"{link_text} ({link_url})")
    return formatted_links


def scrape_links(url):
    response = requests.get(url)

    # Check if the response contains an HTTP error
    if response.status_code >= 400:
        return "error"

    soup = BeautifulSoup(response.text, "html.parser")

    for script in soup(["script", "style"]):
        script.extract()

    hyperlinks = extract_hyperlinks(soup)

    return format_hyperlinks(hyperlinks)


def split_text(text: str, max_length: int = 8192, delimiter: str = "\n") -> list[str]:
    """
    Split a long text string into smaller chunks of specified maximum length.

    Args:
        text (str): The long text string to be split.
        max_length (int, optional): The maximum length of each chunk (default 8192).
        delimiter (str, optional): The delimiter to use for splitting the text string into paragraphs (default "\n").

    Returns:
        A list of strings, each representing a chunk of the original text string.

    Example:
        >>> text = "This is a long text string that needs to be split into smaller chunks."
        >>> chunks = split_text(text, max_length=20)
        >>> for chunk in chunks:
        >>>     print(chunk)
        This is a long text
         string that needs
         to be split into
         smaller chunks.

    """
    # Use a generator expression to split the text string into chunks of specified maximum length
    chunks = (paragraph + delimiter for paragraph in text.split(delimiter))
    chunk = next(chunks, "")

    # Yield each chunk that does not exceed the maximum length
    for paragraph in chunks:
        if len(chunk) + len(paragraph) <= max_length:
            chunk += paragraph
        else:
            yield chunk
            chunk = paragraph
    yield chunk


def summarize_text(text, hint=None, is_website=True):
    """
    Summarize a long text string by extracting concise and specific information from it.

    Args:
        text (str): The long text string to be summarized.
        is_website (bool, optional): Whether the text is a website page (default True).

    Returns:
        str: The summarized text.

    Raises:
        ValueError: If the input text is empty.

    Example:
        >>> text = "This is a long text string that needs to be summarized."
        >>> summary = summarize_text(text, is_website=False)
        >>> print(summary)
        This is a summary of the long text string.
    """
    # Check if the text is empty
    if not text:
        raise ValueError("No text to summarize.")

    # Split the text into chunks
    chunks = list(split_text(text))

    # Generate a summary for each chunk
    summaries = []
    for i, chunk in enumerate(chunks):
        print(f"Summarizing chunk {i + 1} / {len(chunks)}")
        prompt = f"Please summarize the following {'website text and focus on the content and not on the website or publisher itself' if is_website else 'text'}, focusing on extracting concise and specific information{' about {hint}' if (hint is not None and hint.strip() != '') else ''}:\n{chunk}"
        summary = api.generate_response([{"role": "user", "content": prompt}])
        summaries.append(summary)

    if len(summaries) == 1: return summaries[0]

    # Generate a summary for the combined summary chunks
    combined_summary = "\n".join(summaries)
    prompt = f"Please summarize the following {'website text and focus on the content and not on the website or publisher itself' if is_website else 'text'}, focusing on extracting concise and specific information{' about {hint}' if (hint is not None and hint.strip() != '') else ''}:\n{combined_summary}"
    final_summary = api.generate_response([{"role": "user", "content": prompt}])

    return final_summary


def tokenize(text):
    prompt = f"Tokenize and break the following text into individual words (no punctuation) and return as a list of words as strings in python: '{text}'"
    try:
        response = api.generate_response([{"role": "user", "content": prompt}])
        words = eval(response)
        if isinstance(words, list): return words
    except Exception as e:
        print(f"Unable to tokenize {text}: {e}")
        return []
    return []

def count_words(text):
    words = tokenize(text)
    print(f"Tokenize '{text}' into '{words}': {len(words)}")
    return len(words)

def count_characters(text):
    return len(text)
