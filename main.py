import os
import json
import re
import time
import requests
from fastapi import FastAPI, HTTPException, Request, status
from pydantic import BaseModel
from dotenv import load_dotenv

# Import our custom modules
from llm_solver import get_solution_plan, process_data_with_llm
from browser_agent import get_quiz_details, download_file
from data_processor import extract_text_from_pdf

load_dotenv()

# --- Configuration & Setup ---
app = FastAPI(title="LLM Analysis Quiz Solver")
STUDENT_EMAIL = os.getenv("STUDENT_EMAIL")
STUDENT_SECRET = os.getenv("STUDENT_SECRET")

class QuizTask(BaseModel):
    email: str
    secret: str
    url: str
    
class QuizSubmission(BaseModel):
    email: str
    secret: str
    url: str
    answer: str | int | float | bool | dict # Handles varied answer types

# --- Core API Endpoint ---

@app.post("/solve-quiz", status_code=status.HTTP_200_OK)
async def solve_quiz_task(task: QuizTask, request: Request):
    """
    Receives a quiz URL and orchestrates the agent to solve and submit the answer.
    """
    start_time = time.time()
    print(f"\n--- New Task Received for: {task.url} ---")
    
    # 1. Verification (HTTP 403 / HTTP 400)
    if task.email != STUDENT_EMAIL or task.secret != STUDENT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Invalid email or secret provided."
        )
    
    current_quiz_url = task.url
    
    while current_quiz_url:
        print(f"Starting Quiz Solve Cycle for: {current_quiz_url}")
        
        # Check remaining time before starting a new cycle
        if (time.time() - start_time) > (3 * 60 - 30): # 2:30 buffer
            print("Time limit approaching. Aborting new quiz cycle.")
            break
        
        # --- A. Fetch Quiz Instructions (Headless Browser) ---
        instructions, submit_url = get_quiz_details(current_quiz_url)
        
        if "ERROR" in instructions or not submit_url:
            print(f"Failed to retrieve quiz details or submit URL. Aborting.")
            break

        # --- B. LLM Plan Generation (GPT-5-nano) ---
        plan_data = get_solution_plan(instructions)
        task_type = plan_data.get('task_type', 'ANALYZE')
        steps = plan_data.get('plan', [])
        
        final_answer = None
        
        # --- C. Execute Plan (Data Sourcing & Analysis) ---
        
        if task_type == 'DOWNLOAD' and len(steps) > 0:
            # Simple case: look for a download link and process the file
            download_match = re.search(r"https?://[^\s\"]+\.(pdf|csv|json)", instructions, re.IGNORECASE)
            if download_match:
                file_url = download_match.group(0)
                temp_file_path = f"/tmp/quiz_data_{os.getpid()}.pdf" # Secure temp file
                
                if download_file(file_url, temp_file_path):
                    if '.pdf' in file_url.lower():
                        raw_data = extract_text_from_pdf(temp_file_path)
                    else:
                        # For simplicity, we'll assume PDF for this example; 
                        # other formats would require dedicated parsing.
                        raw_data = "File downloaded, but advanced parsing is needed (e.g. CSV/JSON parser)."

                    # Use LLM to perform the calculation based on the raw data
                    final_answer = process_data_with_llm(raw_data, instructions)
                
                # Clean up the file
                if os.path.exists(temp_file_path):
                    os.remove(temp_file_path)
        
        elif task_type == 'SCRAPE':
            # For complex scraping tasks, we would pass the page content to the LLM
            final_answer = process_data_with_llm(instructions, "Extract the final answer based on these instructions and the content you've been given.")

        elif task_type == 'ANALYZE' or task_type == 'VISUALIZE':
            # Use LLM to solve analytical questions directly from instructions
            final_answer = process_data_with_llm(instructions, "Solve the quiz based on the provided instructions. Output ONLY the final numeric or string answer.")
        
        # --- D. Submit Answer ---
        
        if final_answer:
            # Attempt to convert answer to the required type (e.g., int, float)
            try:
                # Try to convert to a number if it looks like one
                if final_answer.isdigit():
                    final_answer = int(final_answer)
                elif re.match(r"^\d+\.\d+$", final_answer):
                    final_answer = float(final_answer)
            except Exception:
                pass # Keep as string if conversion fails

            submission_payload = QuizSubmission(
                email=STUDENT_EMAIL,
                secret=STUDENT_SECRET,
                url=current_quiz_url,
                answer=final_answer
            ).model_dump_json()

            print(f"-> Agent: Submitting answer: {final_answer} to {submit_url}")
            
            try:
                response = requests.post(
                    submit_url, 
                    data=submission_payload,
                    headers={'Content-Type': 'application/json'},
                    timeout=30
                )
                
                response_data = response.json()
                print(f"-> Server Response: Correct: {response_data.get('correct')}, New URL: {response_data.get('url')}")

                if response_data.get('correct') is True:
                    # Move to the next quiz or end the loop
                    current_quiz_url = response_data.get('url')
                else:
                    # If incorrect, check if a new URL is provided (skip option)
                    new_url = response_data.get('url')
                    if new_url:
                        current_quiz_url = new_url
                    else:
                        # If incorrect and no new URL, the script can stop or attempt a retry.
                        # We'll break for simplicity and the time constraint.
                        print("Quiz incorrect and no new URL provided. Stopping.")
                        break

            except requests.exceptions.Timeout:
                print("Submission timed out.")
                break
            except Exception as e:
                print(f"Submission failed: {e}")
                break
        
        else:
            print("Failed to generate a final answer. Stopping.")
            break

    total_time = time.time() - start_time
    print(f"--- Task Complete. Total Time: {total_time:.2f} seconds ---")
    
    return {"status": "processing_complete", "total_time": total_time, "final_url_attempted": current_quiz_url}

# --- Health Check (Optional but Recommended) ---
@app.get("/health")
def health_check():
    return {"status": "ok", "email": STUDENT_EMAIL}