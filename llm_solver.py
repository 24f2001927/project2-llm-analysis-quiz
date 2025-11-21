import os
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
CLIENT = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-5-nano")

SYSTEM_PROMPT = """
You are an expert Data Scientist. Your task is to analyze a raw quiz description 
and determine the exact plan to solve it. Respond with ONLY a single JSON object.
The 'plan' should be a concise, sequential list of steps needed.
The 'task_type' must be 'DOWNLOAD', 'SCRAPE', 'ANALYZE', or 'VISUALIZE'.
"""

def get_solution_plan(quiz_text: str) -> dict:
    """Uses GPT-5-nano to create a structured plan from the quiz instructions."""
    print("-> LLM: Generating solution plan...")
    
    # Use a low temperature for deterministic, factual output
    
    try:
        response = CLIENT.chat.completions.create(
            model=LLM_MODEL,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"The quiz instructions are:\n\n---\n{quiz_text}\n---"}
            ],
            temperature=0.1
        )
        
        # The model is instructed to return only a JSON object
        return json.loads(response.choices[0].message.content)

    except Exception as e:
        print(f"LLM Error: {e}")
        # Return a fail-safe structure
        return {"task_type": "ERROR", "plan": [f"LLM failed to generate plan: {e}"]}

def process_data_with_llm(data: str, instruction: str) -> str:
    """Uses GPT-5-nano to perform the analysis (e.g., calculation, summary)."""
    print("-> LLM: Processing data and generating answer...")
    
    # The instruction here comes from the generated plan.
    try:
        response = CLIENT.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": f"You are a calculation and analysis assistant. Solve the user's request based ONLY on the provided data. Output ONLY the final answer as a single value."},
                {"role": "user", "content": f"DATA:\n{data}\n\nINSTRUCTION: {instruction}"}
            ],
            temperature=0.0
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"LLM Processing Error: {e}")
        return f"ERROR: {e}"

if __name__ == '__main__':
    # Example usage for testing
    sample_quiz = "Download the PDF file at https://example.com/data.pdf. What is the sum of the 'price' column in the table on page 3? Post your answer to https://example.com/submit"
    plan = get_solution_plan(sample_quiz)
    print(json.dumps(plan, indent=2))