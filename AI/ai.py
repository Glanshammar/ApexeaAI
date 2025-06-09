import os
import sys
import time
import json

current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
sys.path.insert(0, root_dir)

from openai import OpenAI
import re
from AI.autobrowser import AutoBrowser, BrowserType
import pymupdf
import requests
from typing import List, Dict, Optional

temp_folder = os.path.join(current_dir, 'temp')
os.makedirs(temp_folder, exist_ok=True)


def PromptAI(prompt: str) -> Optional[str]:
    """Send a prompt to the AI and get a response."""
    try:
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=os.getenv("AI_API_KEY")
        )
        response = client.chat.completions.create(
            model="microsoft/mai-ds-r1:free",
            messages=[{"role": "user", "content": prompt}]
        )
        if not response or not response.choices:
            print("Warning: Empty response from AI")
            return None
        return response.choices[0].message.content
    except Exception as e:
        print(f"Error in PromptAI: {str(e)}")
        return None

def GetLinksFromResponse(response_text: str) -> List[str]:
    """Extract URLs from AI response text."""
    if not response_text:
        return []
    pattern = r'https?://[^{}\s)>\]]+'
    urls = re.findall(pattern, response_text)
    return list(set(urls))  # Remove duplicates


def DownloadFile(browser: AutoBrowser, url: str, save_dir: str, filename: str) -> Optional[str]:
    """Download any file from a URL and save it with a user-specified filename."""
    try:
        # Use the provided filename or generate a fallback one
        if not filename:
            # Extract extension from URL if possible, else default to .bin
            ext = os.path.splitext(url.split('/')[-1])[1] or ".bin"
            filename = f"{int(time.time())}{ext}"
        
        filepath = os.path.join(save_dir, filename)
        
        # Configure download settings for Playwright
        browser.page.context.set_default_timeout(10000)  # 10 seconds
        
        # Setup download event handler
        with browser.page.expect_download() as download_info:
            browser.page.goto(url)
        
        download = download_info.value
        # Wait for the download to complete
        download_path = download.path()
        
        # Move the file to the specified directory and filename
        final_path = os.path.join(save_dir, filename)
        os.rename(download_path, final_path)
        
        # Check if file exists
        if os.path.exists(final_path):
            return final_path
        return None
    except Exception as e:
        print(f"Error downloading file: {str(e)}")
        return None

def DocumentInfo(document_path: str, document_type: str, json_structure: str, details: str) -> Dict:
    if not isinstance(document_path, str):
        return CreateErrorResponse(document_path, "invalid_path", "Document path not provided")
    if not os.path.exists(document_path):
        return CreateErrorResponse(document_path, "file_not_found", "Document file not found")
    if not document_type in ('.pdf', '.doc', '.docx', '.txt', '.html', '.xml', '.json'):
        return CreateErrorResponse(document_path, "invalid_file_type", "Document file type not provided")
    if not details:
        return CreateErrorResponse(document_path, "no_details", "No details provided")
    
    try:
        content = ""
        ext = document_type.lower()
        # PDF
        if ext == ".pdf":
            import fitz  # PyMuPDF
            with fitz.open(document_path) as doc:
                content = "".join(page.get_text() for page in doc if page.get_text())
        # DOC/DOCX
        elif ext in (".doc", ".docx"):
            try:
                import docx
                doc = docx.Document(document_path)
                content = "\n".join([para.text for para in doc.paragraphs if para.text.strip()])
            except ImportError:
                import subprocess
                # Use antiword for .doc if python-docx fails or is not installed
                if ext == ".doc":
                    content = subprocess.check_output(['antiword', document_path]).decode('utf-8')
        # TXT
        elif ext == ".txt":
            with open(document_path, encoding="utf-8") as f:
                content = f.read()
        # HTML
        elif ext == ".html":
            from bs4 import BeautifulSoup
            with open(document_path, encoding="utf-8") as f:
                soup = BeautifulSoup(f, "html.parser")
                content = soup.get_text(separator="\n")
        # XML
        elif ext == ".xml":
            import xml.etree.ElementTree as ET
            tree = ET.parse(document_path)
            root = tree.getroot()
            content = ET.tostring(root, encoding="unicode", method="text")
        # JSON
        elif ext == ".json":
            with open(document_path, encoding="utf-8") as f:
                json_obj = json.load(f)
                content = json.dumps(json_obj, indent=2)
        else:
            return CreateErrorResponse(document_path, "unsupported_type", f"Unsupported file type: {ext}")
        
        if not content:
            return CreateErrorResponse(document_path, "no_content", "No content available to analyze")
        
        # Set up prompt based on source type
        prompt = f"""Analyze this {document_type} file and extract the structured information about it.
        I want you to look for specific details in the file:
        {details}

        You should translate the project description to English if it's not already in English and use the English version for the analysis.
        """

        if isinstance(json_structure, dict) and json_structure:
            prompt += f"\nFormat your response exactly like this JSON structure:\n{json.dumps(json_structure)}"
        
        prompt += f"\nContent to analyze:\n{content}"
        
        # Get AI response
        response = PromptAI(prompt)
        if not response:
            return CreateErrorResponse(document_path, "ai_no_response", "Failed to get AI response for tender analysis")
            
        # Validate the response is proper JSON
        try:
            json.loads(response)
            return {"url": document_path, "info": response}
        except json.JSONDecodeError:
            return CreateErrorResponse(document_path, "invalid_json", 
                                    "AI response was not in valid JSON format",
                                    {"raw_response": response[:500]})
    except Exception as e:
        return CreateErrorResponse(document_path, "processing_error", f"Error analyzing tender: {str(e)}")

def CreateErrorResponse(source: str, error_code: str, message: str, extra_data: Dict = None) -> Dict:
    print(f"Warning: {error_code} for source {source} - {message}")
    
    error_response = {
        "error": error_code,
        "message": message
    }
    
    if extra_data:
        error_response.update(extra_data)
        
    return {"url": source, "info": json.dumps(error_response)}
