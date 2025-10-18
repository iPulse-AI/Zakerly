# Exam Service Error Fixes

## Issues Identified and Fixed

### 1. **Vector Embedding Error** ❌ → ✅
**Error:**
```
invalid input syntax for type vector: "[t,a,b,l,e, ,o,f, ,c,o,n,t,e,n,t,s]"
```

**Root Cause:**
The exam service was passing raw query strings directly to database methods that expect embedding vectors (`List[float]`). PostgreSQL's pgvector extension was trying to parse the string characters as vector components.

**Fix:**
Updated `_search_curriculum_embeddings()` and `_search_book_embeddings()` to generate embeddings using Ollama before querying:

```python
# Before (WRONG):
async def _search_curriculum_embeddings(self, curriculum_name: str, query: str, k: int = 6):
    return await self.db.search_curriculum_embeddings(curriculum_name, query, k)

# After (CORRECT):
async def _search_curriculum_embeddings(self, curriculum_name: str, query: str, k: int = 6):
    # Generate embedding for the query using Ollama
    query_embedding = await self.embeddings.aembed_query(query)
    
    # Search in curriculum embedding table with proper vector
    results = await self.db.search_curriculum_embeddings(curriculum_name, query_embedding, limit=k)
    return results
```

**Methods Fixed:**
- ✅ `_search_curriculum_embeddings()` (Line ~907)
- ✅ `_search_book_embeddings()` (Line ~640)

---

### 2. **SystemMessage Not Supported** ❌ → ✅
**Error:**
```
SystemMessages are not yet supported!

To automatically convert the leading SystemMessage to a HumanMessage,
set  `convert_system_message_to_human` to True. Example:

llm = ChatGoogleGenerativeAI(model="gemini-pro", convert_system_message_to_human=True)
```

**Root Cause:**
Google Gemini API doesn't support SystemMessage in LangChain. The exam service was using `ChatPromptTemplate.from_messages()` with system messages, which Gemini rejects.

**Fix:**
Added `convert_system_message_to_human=True` parameter to both ChatGoogleGenerativeAI initializations:

```python
# Primary LLM initialization
self.llm = ChatGoogleGenerativeAI(
    model=gemini_model,
    temperature=float(os.getenv("CHAT_MODEL_TEMPERATURE", "0.7")),
    google_api_key=os.getenv("GOOGLE_API_KEY"),
    top_k=40,
    top_p=0.8,
    max_tokens=2048,
    convert_system_message_to_human=True  # ✅ FIX ADDED
)

# Fallback LLM initialization
self.llm = ChatGoogleGenerativeAI(
    model=gemini_model,
    temperature=0.7,
    google_api_key=os.getenv("GOOGLE_API_KEY"),
    convert_system_message_to_human=True  # ✅ FIX ADDED
)
```

**Impact:**
Now all LLM calls using system messages will automatically convert them to human messages, which Gemini accepts.

---

## Testing Checklist

After these fixes, test the following scenarios:

### ✅ Case 2: Book Exam Generation
**Request:**
```json
{
  "curriculum_id": 1,
  "book_title": "HPE_ALLETRA_9000_UPDATING_SOFTWARE",
  "scope_type": "whole_book",
  "count": 10
}
```

**Expected Flow:**
1. ✅ Extract topics from TOC (should work now with fixed LLM)
2. ✅ Search book embeddings (should work now with proper vectors)
3. ✅ Generate questions successfully

### ✅ Case 1: Curriculum Exam Generation
**Request:**
```json
{
  "curriculum_id": 1,
  "scope_type": "whole_curriculum",
  "count": 10
}
```

**Expected Flow:**
1. ✅ 4-method topic extraction (should work with fixed LLM)
2. ✅ Search curriculum embeddings (should work with proper vectors)
3. ✅ Generate comprehensive questions

### ✅ Case 3: Topic-Specific Exam
**Request:**
```json
{
  "curriculum_id": 1,
  "book_title": "HPE_ALLETRA_9000_UPDATING_SOFTWARE",
  "scope_type": "specific_topics",
  "specific_topics": "software update procedures, system maintenance",
  "count": 5
}
```

**Expected Flow:**
1. ✅ Expand topics using LLM (should work with fixed system message)
2. ✅ Enhanced semantic search (should work with proper vectors)
3. ✅ Generate focused questions

---

## Changes Summary

### Files Modified:
- `services/exam/exam_service.py`

### Lines Changed:
1. **Line 42-48**: Added `convert_system_message_to_human=True` to primary LLM
2. **Line 52-56**: Added `convert_system_message_to_human=True` to fallback LLM
3. **Line 640-658**: Fixed `_search_book_embeddings()` to generate embeddings
4. **Line 907-922**: Fixed `_search_curriculum_embeddings()` to generate embeddings

### Total Changes: 4 fixes

---

## Deployment Status

✅ **Service Built Successfully**
✅ **Service Running on Port 8003**
✅ **LLM Initialized: gemini-2.5-flash**
✅ **Database Connected**
✅ **Redis Connected**

```
2025-10-18 18:40:07 - exam-service - exam_service - INFO - ✅ ExamService initialized with gemini-2.5-flash
2025-10-18 18:40:07 - exam-service - main - INFO - Exam Service started successfully
INFO: Uvicorn running on http://0.0.0.0:8003 (Press CTRL+C to quit)
```

---

## Technical Details

### Why These Errors Occurred:

1. **Vector Error**: The database methods in `shared/database.py` expect `List[float]` (embedding vectors), not raw strings. The exam service was calling these methods incorrectly, unlike the chat service which properly generates embeddings first.

2. **SystemMessage Error**: Google Gemini's API has limitations compared to OpenAI. While OpenAI supports separate system messages, Gemini requires them to be converted to human messages. This is a known limitation of the `langchain-google-genai` package.

### How Chat Service Avoided These:

The chat service (`services/chat/chat_service.py`) was already implemented correctly:
- Line 299: `query_embedding = await self.embeddings.aembed_query(query)`
- Line 61: `convert_system_message_to_human=True` in LLM initialization

The exam service was missing both of these fixes, which is why it failed during runtime.

---

## Next Steps

1. **Test All 3 Cases**: Run exam generation for curriculum, book, and topics
2. **Monitor Logs**: Watch for any remaining errors during execution
3. **Validate Output**: Ensure questions are properly formatted and relevant
4. **Performance Check**: Monitor LLM API costs and response times

The service is now ready for production testing! 🚀
