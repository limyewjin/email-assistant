import datetime
import urllib.request
import fitz
import re
import numpy as np
import tensorflow_hub as hub
import os
from sklearn.neighbors import NearestNeighbors

import hashlib

import requests
from bs4 import BeautifulSoup

import api
import constants

import logging

import http.client
import urllib.parse
import urllib.request

import os
from dotenv import load_dotenv
load_dotenv()

def is_valid_url(url):
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except ValueError:
        return False

import magic

def is_pdf(file_path):
    mime_type = magic.from_file(file_path, mime=True)
    return mime_type == 'application/pdf'


def download_pdf(url, output_path):
    urllib.request.urlretrieve(url, output_path)


def download_url(url, output_path):
    if is_pdf:
        download_pdf(url, output_path)
    else:
        text = scrape_text(url)
        with open(output_path, "w") as f:
            f.write(text)


def preprocess(text):
    text = text.replace('\n', ' ')
    text = re.sub('\s+', ' ', text)
    return text


def pdf_to_text(path, start_page=1, end_page=None):
    doc = fitz.open(path)
    total_pages = doc.page_count

    if end_page is None:
        end_page = total_pages

    text_list = []

    for i in range(start_page-1, end_page):
        text = doc.load_page(i).get_text("text")
        text = preprocess(text)
        text_list.append(text)

    doc.close()
    return text_list


def scrapingant_get(url, api_key=os.environ["SCRAPINGANT_API_KEY"]):
    conn = http.client.HTTPSConnection("api.scrapingant.com")

    url_quote = urllib.parse.quote(url, safe='')

    conn.request("GET", f"/v2/general?url={url_quote}&x-api-key={api_key}&proxy_country=US")

    res = conn.getresponse()
    data = res.read()

    return data.decode("utf-8")


def scrape_text(url):
    response = requests.get(url)

    # Check if the response contains an HTTP error
    if response.status_code >= 400:
        if "SCRAPINGANT_API_KEY" in os.environ:
            text = scrapingant_get(url)
        else:
            return "Error: HTTP " + str(response.status_code) + " error"
    else:
        text = response.text

    soup = BeautifulSoup(text, "html.parser")

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


def text_to_chunks(texts, word_length=150, start_page=1):
    text_toks = [t.split(' ') for t in texts]
    chunks = []

    for idx, words in enumerate(text_toks):
        for i in range(0, len(words), word_length):
            chunk = words[i:i+word_length]
            if (i+word_length) > len(words) and (len(chunk) < word_length) and (
                len(text_toks) != (idx+1)):
                text_toks[idx+1] = chunk + text_toks[idx+1]
                continue
            chunk = ' '.join(chunk).strip()
            chunk = f'[{idx+start_page}]' + ' ' + '"' + chunk + '"'
            chunks.append(chunk)
    return chunks


class SemanticSearch:
    
    def __init__(self):
        self.use = hub.load('https://tfhub.dev/google/universal-sentence-encoder/4')
        self.fitted = False
    
    
    def init_fit(self, batch=1000, n_neighbors=5):
        n_neighbors = min(n_neighbors, len(self.embeddings))
        self.nn = NearestNeighbors(n_neighbors=n_neighbors)
        self.nn.fit(self.embeddings)
        self.fitted = True


    def fit(self, data, batch=1000, n_neighbors=5):
        self.data = data
        self.embeddings = self.get_text_embedding(data, batch=batch)
        self.init_fit(batch, n_neighbors)
    
    
    def __call__(self, text, return_data=True):
        inp_emb = self.use([text])
        neighbors = self.nn.kneighbors(inp_emb, return_distance=False)[0]
        
        if return_data:
            return [self.data[i] for i in neighbors]
        else:
            return neighbors
    
    
    def get_text_embedding(self, texts, batch=1000):
        embeddings = []
        for i in range(0, len(texts), batch):
            text_batch = texts[i:(i+batch)]
            emb_batch = self.use(text_batch)
            embeddings.append(emb_batch)
        embeddings = np.vstack(embeddings)
        return embeddings


# The modified function generates embeddings based on PDF file name and page number and checks if the embeddings file exists before loading or generating it.	
recommender = SemanticSearch()

def load_recommender(path, start_page=1, load_embedding=False):
    global recommender
    file = os.path.basename(path)
    embeddings_file = f"{file}_{start_page}.npy"
    
    if load_embedding and os.path.isfile(embeddings_file):
        logging.info(f"Loading Embeddings: {embeddings_file}")

        if is_pdf(path):
            texts = pdf_to_text(path, start_page=start_page)
            chunks = text_to_chunks(texts, start_page=start_page)
        else:
            with open(path, "r") as f:
                texts = f.read()
            chunks = texts.split("\n")

        recommender.data = chunks
        embeddings = np.load(embeddings_file)
        recommender.embeddings = embeddings
        recommender.init_fit()
        return "Embeddings loaded from file"
    
    logging.info(f"Creating Embeddings: {embeddings_file}")

    if is_pdf(path):
        texts = pdf_to_text(path, start_page=start_page)
        chunks = text_to_chunks(texts, start_page=start_page)
    else:
        with open(path, "r") as f:
            texts = f.read()
        chunks = texts.split("\n")

    recommender.fit(chunks)
    np.save(embeddings_file, recommender.embeddings)
    return 'Corpus Loaded.'


def generate_answer(question):
    global recommender
    topn_chunks = recommender(question)
    prompt = ""
    prompt += 'search results:\n\n'
    for c in topn_chunks:
        prompt += c + '\n\n'
        
    prompt += "Instructions: Compose a comprehensive reply to the query using the search results given. "\
              "Cite each reference using [ Page Number] notation (every result has this number at the beginning). "\
              "Citation should be done at the end of each sentence. If the search results mention multiple subjects "\
              "with the same name, create separate answers for each. Only include information found in the results and "\
              "don't add any additional information. Make sure the answer is correct and don't output false content. "\
              "If the text does not relate to the query, simply state 'Text Not Found in PDF'. Ignore outlier "\
              "search results which has nothing to do with the question. Only answer what is asked. The "\
              "answer should be short and concise. Answer step-by-step. \n\nQuery: {question}\nAnswer: "
    
    prompt += f"Query: {question}\nAnswer:"
    return prompt


def hash_url_to_filename(url):
    # Get the current date and hour
    now = datetime.datetime.now()
    date_str = now.strftime('%Y-%m-%d-%H')

    # Encode the URL and date as bytes objects
    url_bytes = url.encode('utf-8')
    date_bytes = date_str.encode('utf-8')

    # Compute the SHA-256 hash of the concatenated bytes
    sha256 = hashlib.sha256()
    sha256.update(url_bytes + date_bytes)
    hash_bytes = sha256.digest()

    # Convert the hash bytes to a hexadecimal string
    hash_string = hash_bytes.hex()

    # Return the first 20 characters of the hash string as the filename
    return hash_string[:20]


def question_answer(url_or_filename, question):
    if is_valid_url(url_or_filename):
        logging.info(f"{url_or_filename} is a valid URL")

        directory_path = constants.FILES_PATH
        if not os.path.exists(directory_path):
            try:
                os.makedirs(directory_path)
                print(f"Successfully created directory '{directory_path}'")
            except OSError as e:
                print(f"Error creating directory '{directory_path}': {e}")

        hash_file = f"{directory_path}/{hash_url_to_filename(url_or_filename)}"
        logging.info(f"Hashing {url_or_filename} to {hash_file}")

        url = url_or_filename
        download_url(url, hash_file)

        load_recommender(hash_file, load_embedding=True)
    else:
        filename = f"{constants.FILES_PATH}/{url_or_filename}"
        load_recommender(filename, load_embedding=False)

    prompt = generate_answer(question)

    return api.generate_response([{"role": "user", "content": prompt}])


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
    chunks = text_to_chunks(text, word_length=4000)

    # Generate a summary for each chunk
    summaries = []
    for i, chunk in enumerate(chunks):
        logging.info(f"Summarizing chunk {i + 1} / {len(chunks)} - length: {len(chunk)}")
        prompt = f"Please summarize the following {'website text and focus on the content and not on the website or publisher itself' if is_website else 'text'}, focusing on extracting concise and specific information{' about {hint}' if (hint is not None and hint.strip() != '') else ''}:\n{chunk}"
        summary = api.generate_response([{"role": "user", "content": prompt}])
        summaries.append(summary)

    if len(summaries) == 1: return summaries[0]

    # Generate a summary for the combined summary chunks
    combined_summary = "\n".join(summaries)
    combined_summary_chunks = text_to_chunks(combined_summary, word_length=4000)
    logging.info(f"Combined summary len: {len(combined_summary)}")
    if len(combined_summary_chunks) > 1:
        logging.info(f"Recursively calling summarization...")
        combined_summary = summarize_text(combined_summary, hint=hint, is_website=is_website)
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
