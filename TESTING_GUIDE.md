# 🧪 HR-AI Backend Testing Guide

## ✅ System Status

**Core Components:** All PASS ✅
- ✅ Database (PostgreSQL) - Connected, 1 resume found
- ✅ RAG System (OpenAI) - Resume parsing works
- ✅ Redis - Connected for Celery tasks  
- ✅ Interview Service - Token generation works
- ✅ AI Agent - Initialization and plan handling works

## 🚀 Quick Start Testing (Without Voice)

### 1. Start the Services

```bash
# Terminal 1: Start FastAPI server
uvicorn app.main:app --reload --port 8000

# Terminal 2: Start Celery worker  
celery -A celery_worker.celery_app worker --loglevel=info

# Terminal 3: Monitor system
python simple_test.py
```

### 2. Test Resume Upload & Processing

```bash
# Create test resume file
echo "John Doe
Python Developer
Experience: 3 years
Skills: Python, Django, FastAPI, PostgreSQL
Education: Computer Science
Email: john@example.com
Phone: +1234567890" > test_resume.txt

# Upload via API
curl -X POST "http://localhost:8000/resume/upload" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@test_resume.txt" \
  -F "applicant_name=John Doe" \
  -F "applicant_email=john@example.com" \
  -F "applicant_phone=+1234567890" \
  -F "vacancy_id=1"
```

### 3. Check Processing Results

```bash
# Check resume in database
curl http://localhost:8000/resume/1

# Check interview plan generation
# Should see interview_plan field with structured questions
```

### 4. Test Interview Session Creation

```bash
# Create interview session
curl -X POST "http://localhost:8000/interview/1/start" \
  -H "Content-Type: application/json"
```

## 🎤 Full Voice Testing (Requires Additional Setup)

### Prerequisites for Voice Testing

**1. LiveKit Server**
```bash
# Download LiveKit server
docker run --rm -p 7880:7880 -p 7881:7881 \
  livekit/livekit-server --dev
```

**2. Voice API Keys (Optional - has fallbacks)**

Add to your `.env` file:
```bash
# For better STT (Speech-to-Text)
DEEPGRAM_API_KEY=your-deepgram-key

# For better TTS (Text-to-Speech)  
CARTESIA_API_KEY=your-cartesia-key
# OR
ELEVENLABS_API_KEY=your-elevenlabs-key
```

### Voice Interview Testing

**1. Start Complete Stack**
```bash
# All previous services PLUS:
# Terminal 4: LiveKit server (see above)
```

**2. Create Voice Interview Session**
```bash
# This will start AI agent subprocess
curl -X POST "http://localhost:8000/interview/1/token"
```

**3. Monitor AI Processes**
```bash
# Check running AI agents
curl http://localhost:8000/admin/interview-processes

# System stats
curl http://localhost:8000/admin/system-stats
```

## 📊 Monitoring & Debugging

### 1. Check System Health
```bash
python simple_test.py
```

### 2. Monitor Celery Tasks
- Open Celery worker terminal
- Should see task processing logs

### 3. Database Inspection
```sql
-- Check resumes
SELECT id, applicant_name, status, interview_plan IS NOT NULL as has_plan 
FROM resume;

-- Check interview sessions  
SELECT id, room_name, status, ai_agent_pid, ai_agent_status
FROM interview_sessions;
```

### 4. Process Management
```bash
# List active AI processes
curl http://localhost:8000/admin/interview-processes

# Stop specific process
curl -X POST http://localhost:8000/admin/interview-processes/1/stop

# Cleanup dead processes
curl -X POST http://localhost:8000/admin/interview-processes/cleanup
```

## 🔧 Troubleshooting

### Common Issues

**1. "Database connection error"**
- Check PostgreSQL is running
- Verify DATABASE_URL in config
- Run: `alembic upgrade head`

**2. "RAG system error"**  
- Check OPENAI_API_KEY is set
- Verify internet connection

**3. "Redis connection error"**
```bash
docker run -d -p 6379:6379 redis:alpine
```

**4. "Import errors"**
- Make sure you're in project root directory
- Check virtual environment is activated

**5. "Celery tasks not processing"**
- Ensure Redis is running
- Check Celery worker logs
- Restart Celery worker

### Performance Testing

**Test Multiple Concurrent Interviews:**
```bash
# Create 5 interview sessions simultaneously
for i in {1..5}; do
  curl -X POST "http://localhost:8000/interview/$i/token" &
done
wait

# Monitor system resources
curl http://localhost:8000/admin/system-stats
```

## 🧪 Test Scenarios

### Scenario 1: Basic Resume Processing
1. Upload resume → Check parsing
2. Verify interview plan generation
3. Confirm data in database

### Scenario 2: Interview Session Lifecycle
1. Create session → Get token
2. Start AI agent → Monitor process
3. Stop session → Verify cleanup

### Scenario 3: Multi-User Load Test
1. Upload 10 resumes simultaneously  
2. Create 5 interview sessions
3. Monitor system resources
4. Check process management

### Scenario 4: Error Recovery
1. Stop Redis → Resume upload should queue
2. Start Redis → Tasks should process
3. Kill AI process → Should be detected and cleaned

## 📈 Expected Performance

**Single Interview:**
- Memory: ~45MB per AI agent process
- CPU: ~5-15% during active conversation
- Startup: ~3-5 seconds per agent

**System Limits:**
- Recommended max: 50 concurrent interviews
- Theoretical max: ~150 interviews (on 32GB RAM)

## 🎯 Success Criteria

**✅ Basic Functionality:**
- [ ] Resume upload and parsing works
- [ ] Interview plans are generated
- [ ] Database stores all data correctly
- [ ] Celery processes tasks

**✅ Interview System:**
- [ ] Interview sessions can be created
- [ ] AI agent processes start successfully  
- [ ] Tokens are generated correctly
- [ ] Process monitoring works

**✅ Advanced Features:**
- [ ] Multiple concurrent interviews
- [ ] Process cleanup works
- [ ] System monitoring provides accurate data
- [ ] Error recovery works correctly

**✅ Voice Testing (Optional):**
- [ ] LiveKit connection established
- [ ] STT/TTS services work (if configured)
- [ ] Real-time conversation flows
- [ ] Session termination works properly

## 📝 Test Results Log

Keep track of your testing:

```
Date: ___________
System Test: PASS/FAIL
Resume Upload: PASS/FAIL  
Interview Creation: PASS/FAIL
AI Agent Start: PASS/FAIL
Voice Test: PASS/FAIL (if attempted)

Notes:
_________________________________
_________________________________
```

---

## 🎉 Ready to Test!

Start with the **Quick Start Testing** section above. The system is ready for basic testing without voice features. For full voice testing, set up LiveKit server and optionally add voice API keys.

Good luck! 🚀