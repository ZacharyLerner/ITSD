from bs4 import BeautifulSoup
import re
import os
import requests
from requests.auth import HTTPBasicAuth
from login import USERNAME, PASSWORD, INSTANCE
import json
from docx import Document

instance = INSTANCE
username = USERNAME
password = PASSWORD

def extract_html_text(file_path):
    html_text = []

    with open(file_path, 'r', encoding='utf-8') as f:
        html_doc = f.read()

    # Create a BeautifulSoup object
    soup = BeautifulSoup(html_doc, 'html.parser')

    # Find all elements with class="yaqOZd" and extract their text
    text_list = [element.get_text() for element in soup.find_all(class_="yaqOZd")]

    # remove all commas 
    text_list = [re.sub(r',', r'', text) for text in text_list]

    # add spaces between text
    text_list = [re.sub(r'([a-z])([A-Z])', r'\1 \2', text) for text in text_list]

    # add space after punctuation
    text_list = [re.sub(r'(?<=[.,!?])(?=[^\s])', r' ', text) for text in text_list]
    
    # Print the resulting list
    for text in text_list:
        if "L1915 Lippitt Rd" not in text and len(text) > 30:
            html_text.append(text)
    return html_text

# Function to get a list of KB articles for a given subcategory
# (sys_id for kb_category)

def get_kb(subcategory):

    # Construct the URL with sysparm_query and sysparm_limit parameters
    url = (
        f"https://{instance}.service-now.com/api/now/table/kb_knowledge"
        f"?sysparm_query=kb_knowledge_base=dfc19531bf2021003f07e2c1ac0739ab"
        f"^kb_category={subcategory}&sysparm_limit=100"
    )

    # Make the GET request
    response = requests.get(
        url,
        auth=HTTPBasicAuth(username, password),
        headers={"Accept": "application/json"}
    )
    
    # get all kbs
    if response.status_code == 200:
        data = response.json()
        return data.get('result', [])
    
    # if the request fails, return an empty list
    else:
        return []

# Function to gather docs for a list of subcategory ids, using the get_kb function
def gather_docs(subcategory_ids, seen_texts=None):

    # Initialize seen_texts as an empty set if not provided
    if seen_texts is None:
        seen_texts = set()

    # Initialize the gathered list
    gathered = []

    # Loop through each subcategory_id
    for subcategory_id in subcategory_ids:

        # Get the KB articles for the subcategory
        records = get_kb(subcategory_id)

        # Loop through each KB article and extract the short_description, meta_description, and sys_id
        for record in records:
            short_desc = record.get('short_description', '').strip()
            meta_desc = record.get('meta_description', '').strip()
            
            # Create a case-insensitive deduplication key
            text_key = (short_desc.lower(), meta_desc.lower())
            
            # If the text_key is not in seen_texts, add it to seen_texts and append the combined_text to gathered
            if text_key not in seen_texts:
                seen_texts.add(text_key)
                
                sys_id = record.get('sys_id', '')
                link = f"https://uriprod.service-now.com/kb?id=kb_article_view&sys_kb_id={sys_id}"
                combined_text = f"{short_desc} {meta_desc}. LINK: {link}"
                
                # remove all commas 
                combined_text = re.sub(r',', r'', combined_text)

                gathered.append(combined_text)

    # Return the gathered list
    return gathered

def read_docx_numbering(file_path):
    doc = Document(file_path)
    output_lines = []

    all_line = ""

    for para in doc.paragraphs:
        # The raw text in the paragraph:
        level = None
        num_id = None
        paragraph_text = para.text.strip()

        numbering_info = None
        if para._p is not None and para._p.pPr is not None:
            numbering_info = para._p.pPr.numPr  # This is where numbering is stored if it exists

        if numbering_info is not None:
            level = numbering_info.ilvl.val
            num_id = numbering_info.numId.val

            if level == 0:
                output_lines.append(all_line)
                all_line = paragraph_text
            else:
                all_line += " " + paragraph_text
        else:
            all_line += " " + paragraph_text

    # remove all commas
    output_lines = [re.sub(r',', r'', line) for line in output_lines]
    return output_lines

def read_json_file(file_path):
    with open(file_path, 'r') as file:
        data = json.load(file)
    return gather_docs(data)


def create_json_files():
    data_dir = '/Users/zacharylerner/Documents/ITSD/info/data'
    output_dir = '/Users/zacharylerner/Documents/ITSD/info/formattedFiles'
    os.makedirs(output_dir, exist_ok=True)
    
    for folder in os.listdir(data_dir):
        folder_path = os.path.join(data_dir, folder)
        if os.path.isdir(folder_path):
            content = []
            for file in os.listdir(folder_path):
                file_path = os.path.join(folder_path, file)
                if file.endswith('.docx'):
                    print(f"Reading {file}")
                    content.extend(read_docx_numbering(file_path))
                elif file.endswith('.html'):
                    print(f"Reading {file}")
                    content.extend(extract_html_text(file_path))
                elif file.endswith('.json'):
                    print(f"Reading {file}")
                    content.extend(read_json_file(file_path))
            with open(os.path.join(output_dir, f'{folder}.json'), 'w', encoding='utf-8') as its_file:
                json.dump(content, its_file, indent=4, ensure_ascii=False)
                print(f"Finished writing {folder}.json")

create_json_files()
        
