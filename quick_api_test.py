#!/usr/bin/env python3
"""Quick API testing script"""

import requests
import json
import time
from pathlib import Path

BASE_URL = "http://localhost:8000"

def test_health():
    """Test API health"""
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        print(f"Health check: {response.status_code}")
        return response.status_code == 200
    except Exception as e:
        print(f"API not available: {str(e)}")
        return False

def upload_test_resume():
    """Upload test resume"""
    try:
        # Check if test resume exists
        resume_path = Path("test_resume.txt")
        if not resume_path.exists():
            print("test_resume.txt not found!")
            return None
        
        # Upload file
        with open(resume_path, 'r', encoding='utf-8') as f:
            files = {'file': (resume_path.name, f, 'text/plain')}
            data = {
                'applicant_name': 'Иванов Иван Иванович',
                'applicant_email': 'ivan.ivanov@example.com', 
                'applicant_phone': '+7 (999) 123-45-67',
                'vacancy_id': '1'
            }
            
            response = requests.post(
                f"{BASE_URL}/resume/upload",
                files=files,
                data=data,
                timeout=30
            )
        
        print(f"Resume upload: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print(f"Resume ID: {result.get('resume_id')}")
            return result.get('resume_id')
        else:
            print(f"Upload failed: {response.text}")
            return None
            
    except Exception as e:
        print(f"Upload error: {str(e)}")
        return None

def check_resume_processing(resume_id):
    """Check resume processing status"""
    try:
        response = requests.get(f"{BASE_URL}/resume/{resume_id}")
        print(f"Resume status check: {response.status_code}")
        
        if response.status_code == 200:
            resume = response.json()
            print(f"Status: {resume.get('status')}")
            print(f"Has interview plan: {'interview_plan' in resume and resume['interview_plan'] is not None}")
            return resume
        else:
            print(f"Resume check failed: {response.text}")
            return None
            
    except Exception as e:
        print(f"Status check error: {str(e)}")
        return None

def create_interview_session(resume_id):
    """Create interview session"""
    try:
        response = requests.post(f"{BASE_URL}/interview/{resume_id}/token")
        print(f"Interview session creation: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"Room: {result.get('room_name')}")
            print(f"Token length: {len(result.get('token', ''))}")
            return result
        else:
            print(f"Interview creation failed: {response.text}")
            return None
            
    except Exception as e:
        print(f"Interview creation error: {str(e)}")
        return None

def check_admin_processes():
    """Check admin process monitoring"""
    try:
        response = requests.get(f"{BASE_URL}/admin/interview-processes")
        print(f"Admin processes check: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"Active sessions: {result.get('total_active_sessions')}")
            for proc in result.get('processes', []):
                print(f"  Session {proc['session_id']}: PID {proc['pid']}, Running: {proc['is_running']}")
            return result
        else:
            print(f"Admin check failed: {response.text}")
            return None
            
    except Exception as e:
        print(f"Admin check error: {str(e)}")
        return None

def main():
    """Run quick API tests"""
    print("=" * 50)
    print("QUICK API TEST")
    print("=" * 50)
    
    # 1. Check if API is running
    if not test_health():
        print("❌ API not running! Start with: uvicorn app.main:app --reload")
        return
    
    print("✅ API is running")
    
    # 2. Upload test resume
    print("\n--- Testing Resume Upload ---")
    resume_id = upload_test_resume()
    
    if not resume_id:
        print("❌ Resume upload failed!")
        return
    
    print(f"✅ Resume uploaded with ID: {resume_id}")
    
    # 3. Wait for processing and check status
    print("\n--- Checking Resume Processing ---")
    print("Waiting 10 seconds for Celery processing...")
    time.sleep(10)
    
    resume_data = check_resume_processing(resume_id)
    
    if not resume_data:
        print("❌ Could not check resume status!")
        return
    
    if resume_data.get('status') == 'parsed':
        print("✅ Resume processed successfully")
    else:
        print(f"⚠️ Resume status: {resume_data.get('status')}")
    
    # 4. Create interview session
    print("\n--- Testing Interview Session ---") 
    interview_data = create_interview_session(resume_id)
    
    if interview_data:
        print("✅ Interview session created")
    else:
        print("❌ Interview session creation failed")
    
    # 5. Check admin monitoring
    print("\n--- Testing Admin Monitoring ---")
    admin_data = check_admin_processes()
    
    if admin_data:
        print("✅ Admin monitoring works")
    else:
        print("❌ Admin monitoring failed")
    
    print("\n" + "=" * 50)
    print("QUICK TEST COMPLETED")
    print("=" * 50)
    
    print("\nNext steps:")
    print("1. Check Celery worker logs for task processing")
    print("2. Inspect database for interview_plan data")  
    print("3. For voice testing, start LiveKit server")
    print("4. Monitor system with: curl http://localhost:8000/admin/system-stats")

if __name__ == "__main__":
    main()