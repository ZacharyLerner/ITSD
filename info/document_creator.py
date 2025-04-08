from bs4 import BeautifulSoup
import re
import json
from docx import Document
from .servicenow import gather_docs
import os
from dotenv import load_dotenv

load_dotenv()
data_dir = os.getenv("data_dir")
output_dir = os.getenv("output_dir")


# Goes through Internal Site HTML files and extracts all text within each dropdown menu
# Returns a list of strings, each string representing the text within a dropdown menu
def extract_html_text(file_path):
    html_text = []

    with open(file_path, 'r', encoding='utf-8') as f:
        html_doc = f.read()

    # Create a BeautifulSoup object
    soup = BeautifulSoup(html_doc, 'html.parser')

    # Find all elements with class="yaqOZd" and extract their text
    # This indicates that text is within a dropdown menu
    text_list = [element.get_text() for element in soup.find_all(class_="yaqOZd")]

    # remove all commas 
    text_list = [re.sub(r',', r'', text) for text in text_list]

    # add spaces between text
    text_list = [re.sub(r'([a-z])([A-Z])', r'\1 \2', text) for text in text_list]

    # add space after punctuation, this is to help avoid words being combined
    text_list = [re.sub(r'(?<=[.,!?])(?=[^\s])', r' ', text) for text in text_list]
    
    # remove all text that contains the "address", this is to avoid duplicates that occur at the footer of the page
    for text in text_list:
        if "L1915 Lippitt Rd" not in text and len(text) > 30:
            html_text.append(text)

    # return the list of text
    return html_text

# Goes through a qual docx file and extracts all text within each numbered list
# Returns a list of strings, each string representing the text within a numbered list
def read_docx_numbering(file_path):
    doc = Document(file_path)
    output_lines = []

    # all_line is the string that will be added to the output_lines list
    all_line = ""

    # Loop through each paragraph in the document
    for para in doc.paragraphs:
        # The raw text in the paragraph:
        level = None
        num_id = None
        paragraph_text = para.text.strip()

        numbering_info = None

        # Check if the paragraph has numbering information
        if para._p is not None and para._p.pPr is not None:
            numbering_info = para._p.pPr.numPr 

        # If the paragraph has numbering information, extract the level and num_id
        if numbering_info is not None:
            level = numbering_info.ilvl.val
            num_id = numbering_info.numId.val

            # If the level is 0, add the all_line to the output_lines list and reset all_line
            if level == 0:
                output_lines.append(all_line)
                all_line = paragraph_text
            
            # If the level is not 0, keep adding the paragraph text to all_line
            else:
                all_line += " " + paragraph_text
        
        # If the paragraph does not have numbering information, add the paragraph text to all_line
        else:
            all_line += " " + paragraph_text
    # This will add all lines in the document while maintaining the original structure of the document

    # remove all commas
    output_lines = [re.sub(r',', r'', line) for line in output_lines]
    return output_lines

# Goes through a JSON file and extracts all text within each key
def read_json_file(file_path):
    with open(file_path, 'r') as file:
        data = json.load(file)
    # Uses the gather_docs function from SN_Kb_creator.py to extract the text from the JSON file
    return gather_docs(data)

# Creates JSON files from the data in the data directory
# The JSON files are formatted and stored in the formattedFiles directory
def create_json_files():
    os.makedirs(output_dir, exist_ok=True)
    
    # Loop through each folder in the data directory
    for folder in os.listdir(data_dir):
        folder_path = os.path.join(data_dir, folder)
        if os.path.isdir(folder_path):
            content = []
            # Loop through each file in the folder
            # Depending on the file type, call the appropriate function to extract the text
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
            # Write the extracted text to a JSON file in the formattedFiles directory
            with open(os.path.join(output_dir, f'{folder}.json'), 'w', encoding='utf-8') as its_file:
                json.dump(content, its_file, indent=4, ensure_ascii=False)
                print(f"Finished writing {folder}.json")
        
