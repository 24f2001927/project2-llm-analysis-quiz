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
    answer: str | int | float | bool | dict

# --- Core API Endpoint ---

@app.post("/solve-quiz", status_code=status.HTTP_200_OK)
async def solve_quiz_task(task: QuizTask, request: Request):
    """
    Receives a quiz URL and orchestrates the agent to solve and submit the answer.
    """
    start_time = time.time()
    print(f"\n{'='*60}")
    print(f"NEW TASK RECEIVED")
    print(f"URL: {task.url}")
    print(f"Email: {task.email}")
    print(f"{'='*60}\n")
    
    # 1. Verification (HTTP 403 / HTTP 400)
    if task.email != STUDENT_EMAIL or task.secret != STUDENT_SECRET:
        print(f"❌ Authentication failed!")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Invalid email or secret provided."
        )
    
    print("✅ Authentication successful")
    
    current_quiz_url = task.url
    quiz_count = 0
    
    while current_quiz_url:
        quiz_count += 1
        print(f"\n{'─'*60}")
        print(f"🔍 Quiz #{quiz_count}: {current_quiz_url}")
        print(f"{'─'*60}")
        
        # Check remaining time before starting a new cycle
        elapsed_time = time.time() - start_time
        if elapsed_time > (3 * 60 - 30):  # 2:30 buffer
            print("⏰ Time limit approaching (2:30 elapsed). Aborting new quiz cycle.")
            break
        
        print(f"⏱️  Elapsed time: {elapsed_time:.1f}s / 180s")
        
        # --- A. Fetch Quiz Instructions (Headless Browser) ---
        try:
            instructions, submit_url = await get_quiz_details(current_quiz_url)
        except Exception as e:
            print(f"❌ Failed to fetch quiz details: {e}")
            break
        
        if "ERROR" in instructions or not submit_url:
            print(f"❌ Failed to retrieve valid quiz details or submit URL.")
            print(f"Instructions preview: {instructions[:200]}...")
            break

        print(f"✅ Retrieved quiz instructions ({len(instructions)} chars)")
        print(f"📤 Submit URL: {submit_url}\n")

        # --- B. LLM Plan Generation ---
        try:
            plan_data = get_solution_plan(instructions)
            task_type = plan_data.get('task_type', 'ANALYZE')
            steps = plan_data.get('plan', [])
            
            print(f"🎯 Task Type: {task_type}")
            print(f"📋 Plan: {json.dumps(steps, indent=2)}\n")
        except Exception as e:
            print(f"❌ LLM planning failed: {e}")
            break
        
        final_answer = None
        
        # --- C. Execute Plan (Data Sourcing & Analysis) ---
        
        if task_type == 'DOWNLOAD':
            # Look for a download link in the instructions
            download_match = re.search(r"href=['\"]([^'\"]+\.(?:pdf|csv|json|xlsx?))['\"]", instructions, re.IGNORECASE)
            if not download_match:
                download_match = re.search(r"(https?://[^\s\"'<>]+\.(?:pdf|csv|json|xlsx?))", instructions, re.IGNORECASE)
            
            if download_match:
                file_url = download_match.group(1)
                print(f"📥 Downloading file: {file_url}")
                
                # Determine file extension
                file_ext = re.search(r'\.([^.]+)$', file_url)
                file_ext = file_ext.group(1) if file_ext else 'pdf'
                temp_file_path = f"/tmp/quiz_data_{os.getpid()}.{file_ext}"
                
                try:
                    if await download_file(file_url, temp_file_path):
                        print(f"✅ File downloaded to {temp_file_path}")
                        
                        if file_ext.lower() == 'pdf':
                            raw_data = extract_text_from_pdf(temp_file_path)
                            print(f"📄 Extracted {len(raw_data)} characters from PDF")
                        elif file_ext.lower() in ['csv', 'json', 'txt']:
                            with open(temp_file_path, 'r', encoding='utf-8') as f:
                                raw_data = f.read()
                            print(f"📄 Read {len(raw_data)} characters from {file_ext.upper()}")
                        else:
                            raw_data = f"File downloaded but format {file_ext} needs manual parsing."
                            print(f"⚠️  {raw_data}")

                        # Use LLM to perform the calculation based on the raw data
                        print("🤖 Processing data with LLM...")
                        final_answer = process_data_with_llm(raw_data, instructions)
                        print(f"💡 Generated answer: {final_answer}")
                    else:
                        print("❌ File download failed")
                        
                except Exception as e:
                    print(f"❌ Error processing file: {e}")
                finally:
                    # Clean up the file
                    if os.path.exists(temp_file_path):
                        os.remove(temp_file_path)
                        print(f"🗑️  Cleaned up temp file")
            else:
                print("❌ No download URL found in instructions")
        
        elif task_type == 'SCRAPE':
            # For complex scraping tasks, pass the page content to the LLM
            print("🤖 Processing scraped content with LLM...")
            final_answer = process_data_with_llm(instructions, "Extract and calculate the final answer based on these instructions.")

        elif task_type in ['ANALYZE', 'VISUALIZE', 'ERROR']:
            # Use LLM to solve analytical questions directly from instructions
            print("🤖 Analyzing with LLM...")
            final_answer = process_data_with_llm(instructions, "Solve the quiz based on the provided instructions. Output ONLY the final answer value.")
        
        # --- D. Submit Answer ---
        
        if final_answer:
            # Attempt to convert answer to the required type
            original_answer = final_answer
            try:
                # Remove common text artifacts
                final_answer = final_answer.strip().strip('"\'')
                
                # Try to convert to a number if it looks like one
                if re.match(r'^-?\d+$', final_answer):
                    final_answer = int(final_answer)
                elif re.match(r'^-?\d+\.\d+$', final_answer):
                    final_answer = float(final_answer)
                elif final_answer.lower() in ['true', 'false']:
                    final_answer = final_answer.lower() == 'true'
            except Exception as e:
                print(f"⚠️  Could not convert answer type: {e}")
                final_answer = original_answer

            submission_payload = {
                "email": STUDENT_EMAIL,
                "secret": STUDENT_SECRET,
                "url": current_quiz_url,
                "answer": final_answer
            }

            print(f"\n📤 Submitting answer: {final_answer} (type: {type(final_answer).__name__})")
            print(f"📤 To: {submit_url}")
            
            try:
                response = requests.post(
                    submit_url, 
                    json=submission_payload,
                    headers={'Content-Type': 'application/json'},
                    timeout=30
                )
                
                response_data = response.json()
                is_correct = response_data.get('correct', False)
                new_url = response_data.get('url')
                reason = response_data.get('reason')
                
                if is_correct:
                    print(f"✅ CORRECT!")
                else:
                    print(f"❌ INCORRECT")
                    if reason:
                        print(f"   Reason: {reason}")
                
                print(f"📊 Response: {json.dumps(response_data, indent=2)}")

                if is_correct and new_url:
                    current_quiz_url = new_url
                    print(f"➡️  Moving to next quiz: {new_url}")
                elif new_url:
                    # Incorrect but can skip to next
                    current_quiz_url = new_url
                    print(f"⏭️  Skipping to next quiz: {new_url}")
                else:
                    print("🏁 No more quizzes. Stopping.")
                    break

            except requests.exceptions.Timeout:
                print("❌ Submission timed out.")
                break
            except Exception as e:
                print(f"❌ Submission failed: {e}")
                break
        
        else:
            print("❌ Failed to generate a final answer. Stopping.")
            break

    total_time = time.time() - start_time
    print(f"\n{'='*60}")
    print(f"🏁 TASK COMPLETE")
    print(f"⏱️  Total Time: {total_time:.2f} seconds")
    print(f"📊 Quizzes Attempted: {quiz_count}")
    print(f"{'='*60}\n")
    
    return {
        "status": "processing_complete", 
        "total_time": total_time, 
        "quizzes_attempted": quiz_count,
        "final_url_attempted": current_quiz_url
    }

# --- Health Check ---
@app.get("/health")
def health_check():
    return {
        "status": "ok", 
        "email": STUDENT_EMAIL,
        "secret_configured": bool(STUDENT_SECRET),
        "openai_key_configured": bool(os.getenv("OPENAI_API_KEY"))
    }

@app.get("/")
def root():
    return {
        "message": "LLM Quiz Solver API",
        "endpoints": {
            "health": "/health",
            "docs": "/docs",
            "solve": "/solve-quiz (POST)"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)