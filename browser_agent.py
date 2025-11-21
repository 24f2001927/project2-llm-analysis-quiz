import os
import re
from playwright.sync_api import sync_playwright

def get_quiz_details(url: str) -> tuple[str, str]:
    """
    Renders the URL using a headless browser, scrapes the quiz instructions, 
    and finds the submission URL.
    Returns: (quiz_instructions_text, submit_url)
    """
    print(f"-> Browser: Visiting quiz URL: {url}")
    quiz_instructions = "Error: Could not retrieve quiz instructions."
    submit_url = ""
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True) # Use headless=True for production
            page = browser.new_page()
            
            # Set a timeout for loading the page
            page.goto(url, timeout=60000) 
            
            # Wait for the JavaScript to fully render the content (e.g., the div#result)
            page.wait_for_selector('body', state='visible', timeout=30000)
            
            # 1. Scrape the full text of the quiz instructions
            # We assume the quiz instructions are rendered in a human-readable format somewhere on the page
            quiz_instructions = page.main_frame.inner_text("body")
            
            # 2. Extract the submission URL (Look for the common 'Post your answer to...' pattern)
            # This is a robust regex to find the URL within the text
            submit_match = re.search(r"Post your answer to (https?://[^\s\"]+)", quiz_instructions, re.IGNORECASE)
            if submit_match:
                submit_url = submit_match.group(1).strip()
                
            browser.close()

    except Exception as e:
        print(f"Browser Agent Error: {e}")
        quiz_instructions = f"ERROR during browser operation: {e}"
        
    return quiz_instructions, submit_url

def download_file(url: str, save_path: str) -> bool:
    """Downloads a file from a given URL using the browser agent."""
    print(f"-> Browser: Downloading file from: {url}")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            # Start a download listener before navigating
            with page.expect_download() as download_info:
                page.goto(url, timeout=60000)
                
            download = download_info.value
            download.save_as(save_path)
            
            browser.close()
            return True
            
    except Exception as e:
        print(f"Download Error: {e}")
        return False