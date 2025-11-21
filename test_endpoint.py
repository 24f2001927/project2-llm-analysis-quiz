"""
Test script for LLM Quiz Solver
Run this after starting the server to test the endpoint
"""

import requests
import json
import time
import os
from dotenv import load_dotenv

load_dotenv()

# Configuration
BASE_URL = "http://localhost:8000"
STUDENT_EMAIL = os.getenv("STUDENT_EMAIL", "24f2001927@ds.study.iitm.ac.in")
STUDENT_SECRET = os.getenv("STUDENT_SECRET", "tahmeedsecret")

# Colors for terminal output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'

def print_section(title):
    print(f"\n{'='*60}")
    print(f"{Colors.BLUE}{title}{Colors.END}")
    print('='*60)

def print_success(message):
    print(f"{Colors.GREEN}✓ {message}{Colors.END}")

def print_error(message):
    print(f"{Colors.RED}✗ {message}{Colors.END}")

def print_warning(message):
    print(f"{Colors.YELLOW}! {message}{Colors.END}")

def test_health_endpoint():
    """Test the health check endpoint"""
    print_section("Test 1: Health Check")
    
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            print_success(f"Server is running")
            print(f"  Status: {data.get('status')}")
            print(f"  Email: {data.get('email')}")
            print(f"  Secret configured: {data.get('secret_configured')}")
            print(f"  OpenAI key configured: {data.get('openai_key_configured')}")
            return True
        else:
            print_error(f"Health check failed with status {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print_error("Could not connect to server. Is it running?")
        print_warning("Start server with: uvicorn main:app --reload")
        return False
    except Exception as e:
        print_error(f"Error: {e}")
        return False

def test_root_endpoint():
    """Test the root endpoint"""
    print_section("Test 2: Root Endpoint")
    
    try:
        response = requests.get(f"{BASE_URL}/", timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            print_success("Root endpoint working")
            print(f"  Message: {data.get('message')}")
            print(f"  Endpoints: {json.dumps(data.get('endpoints'), indent=4)}")
            return True
        else:
            print_error(f"Root endpoint failed with status {response.status_code}")
            return False
            
    except Exception as e:
        print_error(f"Error: {e}")
        return False

def test_authentication():
    """Test authentication with wrong credentials"""
    print_section("Test 3: Authentication (Wrong Credentials)")
    
    payload = {
        "email": "wrong@email.com",
        "secret": "wrong_secret",
        "url": "https://project2-llm-analysis-quiz-1.onrender.com"
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/solve-quiz",
            json=payload,
            timeout=5
        )
        
        if response.status_code == 403:
            print_success("Authentication validation working (403 returned)")
            return True
        else:
            print_error(f"Expected 403, got {response.status_code}")
            return False
            
    except Exception as e:
        print_error(f"Error: {e}")
        return False

def test_demo_quiz():
    """Test with the demo quiz URL"""
    print_section("Test 4: Demo Quiz (This may take 1-2 minutes)")
    
    payload = {
        "email": STUDENT_EMAIL,
        "secret": STUDENT_SECRET,
        "url": "https://project2-llm-analysis-quiz-1.onrender.com/demo"
    }
    
    print(f"Payload: {json.dumps(payload, indent=2)}")
    print("\nSending request...")
    
    try:
        start_time = time.time()
        response = requests.post(
            f"{BASE_URL}/solve-quiz",
            json=payload,
            timeout=180  # 3 minutes timeout
        )
        elapsed_time = time.time() - start_time
        
        print(f"\nResponse received in {elapsed_time:.2f} seconds")
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print_success("Quiz processing completed")
            print(f"\nResponse Data:")
            print(json.dumps(data, indent=2))
            
            if data.get('status') == 'processing_complete':
                print_success(f"Processed {data.get('quizzes_attempted', 0)} quiz(es)")
                print_success(f"Total time: {data.get('total_time', 0):.2f} seconds")
                return True
            else:
                print_warning("Quiz completed but with unexpected status")
                return False
        else:
            print_error(f"Quiz processing failed with status {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except requests.exceptions.Timeout:
        print_error("Request timed out after 3 minutes")
        return False
    except Exception as e:
        print_error(f"Error: {e}")
        return False

def run_all_tests():
    """Run all tests"""
    print(f"\n{Colors.BLUE}{'='*60}")
    print("LLM Quiz Solver - Test Suite")
    print(f"{'='*60}{Colors.END}\n")
    
    print(f"Testing server at: {BASE_URL}")
    print(f"Using email: {STUDENT_EMAIL}")
    print(f"Using secret: {'*' * len(STUDENT_SECRET)}")
    
    results = []
    
    # Test 1: Health Check
    results.append(("Health Check", test_health_endpoint()))
    
    # Test 2: Root Endpoint
    results.append(("Root Endpoint", test_root_endpoint()))
    
    # Test 3: Authentication
    results.append(("Authentication", test_authentication()))
    
    # Test 4: Demo Quiz
    results.append(("Demo Quiz", test_demo_quiz()))

if __name__ == "__main__":
    try:
        run_all_tests()
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}Tests interrupted by user{Colors.END}")
    except Exception as e:
        print_error(f"Unexpected error: {e}")