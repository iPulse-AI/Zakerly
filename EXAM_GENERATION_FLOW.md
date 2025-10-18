# 📚 Exam Generation Flow in chat_service_backup.py

## 🎯 Overview

The exam generation system in `chat_service_backup.py` uses a **sophisticated 3-case routing system** with **multi-method topic extraction** and **agent-based question generation**.

---

## 🔀 Main Entry Point & Routing

### **Entry Point: Lines 2032-2128**

```python
# Receives QuestionGenerationRequest with:
# - scope_type: 'whole_curriculum' | 'whole_book' | 'specific_topics'
# - curriculum_id / book_title / specific_topics
# - count, difficulty, question_types, time_limit

exam_parameters = {
    'count': request.count or 10,
    'difficulty': request.difficulty or ['medium'],
    'question_types': request.question_types or ['multiple_choice_single_answer'],
    'time_limit': request.time_limit or 30,
    'user_message': request.user_message or '',
    'specific_topics': request.specific_topics or ''
}
```

### **3-Case Routing Logic:**

```
┌─────────────────────────────────────────────────────────┐
│              QuestionGenerationRequest                   │
│                                                          │
│  ┌──────────────┬──────────────┬──────────────┐        │
│  │   Case 1     │   Case 2     │   Case 3     │        │
│  │  Curriculum  │     Book     │    Topics    │        │
│  └──────────────┴──────────────┴──────────────┘        │
└─────────────────────────────────────────────────────────┘
         │                │               │
         ▼                ▼               ▼
   CASE 1 AGENT      CASE 2 AGENT    CASE 3 AGENT
```

---

## 🌟 CASE 1: Whole Curriculum Exam

### **Entry Point: `_generate_questions_with_curriculum_agent()` (Lines 2132-2175)**

### **3-Step Sophisticated Flow:**

```
┌─────────────────────────────────────────────────────────────┐
│  STEP 1: Extract Comprehensive Topics from Curriculum       │
│  _extract_curriculum_wide_topics()                          │
│                                                             │
│  Uses 4 METHODS:                                            │
│  ├─ METHOD 1: Extract from all books' TOCs                 │
│  ├─ METHOD 2: Search curriculum overview/syllabus          │
│  ├─ METHOD 3: Content-based keyword analysis               │
│  └─ METHOD 4: Dynamic random chunk analysis                │
│                                                             │
│  Result: List of 10-15 curriculum-wide topics              │
└─────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  STEP 2: Get Content Chunks for Topics                      │
│  _get_chunks_for_curriculum_topics()                        │
│                                                             │
│  For each topic:                                            │
│  ├─ Search curriculum embeddings (k=3-4 chunks/topic)      │
│  ├─ Aggregate chunks from all books                        │
│  └─ Deduplicate and combine content                        │
│                                                             │
│  Result: 15-20 diverse content chunks                      │
└─────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  STEP 3: Generate Comprehensive Questions                   │
│  _generate_comprehensive_curriculum_questions()             │
│                                                             │
│  ├─ Combine chunks into unified content                    │
│  ├─ Build sophisticated prompt with curriculum context     │
│  ├─ Invoke LLM with forbidden phrase rules                 │
│  ├─ Parse JSON response with cleaning                      │
│  └─ Validate and clean questions (_remove_book_references) │
│                                                             │
│  Result: 10+ professional exam questions                   │
└─────────────────────────────────────────────────────────────┘
```

### **Key Methods in CASE 1:**

| Method | Line Range | Purpose |
|--------|------------|---------|
| `_extract_curriculum_wide_topics()` | 2177-2222 | Extract topics using 4 methods |
| `_extract_topics_from_all_books_toc()` | 2224-2270 | METHOD 1: Parse TOCs from all books |
| `_extract_topics_from_curriculum_overview()` | 2272-2320 | METHOD 2: Find overview/syllabus |
| `_extract_topics_from_curriculum_content()` | 2322-2370 | METHOD 3: Content keyword extraction |
| `_extract_keywords_from_random_chunks()` | 2372-2450 | METHOD 4: Random chunk analysis |
| `_get_chunks_for_curriculum_topics()` | 2452-2464 | Search & aggregate chunks |
| `_generate_comprehensive_curriculum_questions()` | 2466-2539 | Final question generation |

---

## 📚 CASE 2: Whole Book Exam

### **Entry Point: `_generate_questions_with_book_agent()` (Lines 2541-2638)**

### **3-Step Sophisticated Flow:**

```
┌─────────────────────────────────────────────────────────────┐
│  STEP 1: Extract Topics from Book TOC                       │
│  _extract_topics_from_book_toc()                            │
│                                                             │
│  Multi-Method TOC Extraction:                               │
│  ├─ METHOD 1: Search for TOC-specific content              │
│  │   (_search_for_toc_content)                             │
│  │   Queries: "table of contents", "chapter", "section"    │
│  │                                                          │
│  ├─ METHOD 2: Get beginning chunks                         │
│  │   (_get_beginning_chunks)                               │
│  │   Get first 8 chunks where TOC typically appears        │
│  │                                                          │
│  └─ PARSE: Use LLM to extract keywords                     │
│     (_parse_toc_topics)                                     │
│     Extracts searchable terms, technical vocabulary        │
│                                                             │
│  Fallback: _extract_topics_from_content_fallback()         │
│                                                             │
│  Result: 8-12 book-specific topics                         │
└─────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  STEP 2: Search Content for Topics                          │
│  _search_book_for_topics()                                  │
│                                                             │
│  For each extracted topic:                                  │
│  ├─ Search book embeddings with enhanced scoring           │
│  ├─ Retry with alternative queries if no results           │
│  ├─ Score and rank results by relevance                    │
│  └─ Select top 12-15 chunks                                │
│                                                             │
│  Advanced Features:                                         │
│  ├─ Multiple search attempts per topic                     │
│  ├─ Query reformulation for better coverage                │
│  └─ Diversity scoring to avoid duplication                 │
│                                                             │
│  Result: 12-15 most relevant content chunks                │
└─────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  STEP 3: Generate Questions from Content                    │
│  _generate_questions_from_content()                         │
│                                                             │
│  ├─ Combine chunks (deduplicated)                          │
│  ├─ Build sophisticated prompt:                            │
│  │   - Forbidden phrases list (15+ patterns)               │
│  │   - Professional question style requirements            │
│  │   - JSON format specification                           │
│  ├─ Invoke LLM (gemini-2.5-flash)                          │
│  ├─ Parse JSON with enhanced error handling                │
│  ├─ Clean each question (_remove_book_references)          │
│  └─ Validate and return exact count                        │
│                                                             │
│  Result: 10+ professional exam questions                   │
└─────────────────────────────────────────────────────────────┘
```

### **Key Methods in CASE 2:**

| Method | Line Range | Purpose |
|--------|------------|---------|
| `_extract_topics_from_book_toc()` | 820-868 | Main TOC extraction entry point |
| `_search_for_toc_content()` | 870-910 | Search for TOC using 7 queries |
| `_get_beginning_chunks()` | 912-965 | Get first chunks of book |
| `_parse_toc_topics()` | 967-1028 | LLM-based keyword extraction |
| `_extract_topics_from_content_fallback()` | 1030-1070 | Fallback if TOC fails |
| `_search_book_for_topics()` | 1072-1114 | Enhanced search with retry |
| `_generate_questions_from_content()` | 2719-2895 | Core question generation |

---

## 🎯 CASE 3: Specific Topics Exam

### **Entry Point: `_generate_questions_with_topic_agent()` (Lines 2640-2717)**

### **3-Step Sophisticated Flow:**

```
┌─────────────────────────────────────────────────────────────┐
│  STEP 1: Analyze & Expand Specific Topics                   │
│  _analyze_and_expand_topics()                               │
│                                                             │
│  ├─ Parse user-provided topic string                       │
│  ├─ Extract keywords using LLM                             │
│  ├─ Generate related search terms                          │
│  └─ Create comprehensive search strategy                   │
│                                                             │
│  Input: "data pipelines and ETL"                           │
│  Output: ["data pipelines", "ETL", "extract transform",    │
│           "data processing", "pipeline architecture"]      │
│                                                             │
│  Result: 5-8 expanded search terms                         │
└─────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  STEP 2: Enhanced Search for Topic Content                  │
│  _search_for_specific_topics_enhanced()                     │
│                                                             │
│  For each search term:                                      │
│  ├─ Primary search in curriculum embeddings                │
│  ├─ Score results by relevance to topic                    │
│  ├─ Retry with alternative formulations if needed          │
│  └─ Aggregate and deduplicate results                      │
│                                                             │
│  Advanced Features:                                         │
│  ├─ Semantic similarity scoring                            │
│  ├─ Topic-specific chunk ranking                           │
│  ├─ Multiple search attempts with reformulation            │
│  └─ Quality filtering (min length, relevance)              │
│                                                             │
│  Result: 8-10 highly relevant chunks                       │
└─────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  STEP 3: Generate Topic-Focused Questions                   │
│  _generate_questions_from_content()                         │
│                                                             │
│  ├─ Combine topic-specific content                         │
│  ├─ Build focused prompt with topic emphasis               │
│  ├─ Apply all quality rules:                               │
│  │   - No meta-references                                  │
│  │   - Professional style                                  │
│  │   - Technical accuracy                                  │
│  ├─ Invoke LLM with topic context                          │
│  ├─ Parse and validate JSON                                │
│  └─ Clean questions (_remove_book_references)              │
│                                                             │
│  Result: 5-10 topic-focused questions                      │
└─────────────────────────────────────────────────────────────┘
```

### **Key Methods in CASE 3:**

| Method | Line Range | Purpose |
|--------|------------|---------|
| `_analyze_and_expand_topics()` | 2640-2682 | Parse and expand topic string |
| `_search_for_specific_topics_enhanced()` | 2684-2717 | Enhanced semantic search |
| `_generate_questions_from_content()` | 2719-2895 | Core question generation (shared) |

---

## ⚙️ Core Shared Methods

### **1. Question Generation (_generate_questions_from_content)**

**Location:** Lines 2719-2895

**Sophisticated Prompt Features:**

```python
STRICTLY FORBIDDEN PHRASES - DO NOT USE:
❌ "According to the content"
❌ "According to the text" 
❌ "As described in Chapter X"
❌ "What does Chapter X cover"
❌ "The book states"
❌ "Based on the provided content"

REQUIRED QUESTION STYLE:
✅ Write direct technical questions
✅ Professional certification exam style
✅ No source material references
✅ Clear, unambiguous wording

JSON FORMAT:
- "difficulty": "easy|medium|hard"
- "type": "multiple_choice_single_answer|true_false|open_ended"
- "question_text": "Direct technical question"
- "options": [4 plausible options]
- "answer": "Correct answer as STRING"
```

**Process Flow:**

1. **Validate Content** - Check length, quality
2. **Build Prompt** - Insert content, parameters, forbidden rules
3. **Invoke LLM** - Google Gemini with temperature 0.7
4. **Clean Response** - Remove markdown, extract JSON array
5. **Parse JSON** - Handle various formats, error recovery
6. **Validate Questions** - Check required fields
7. **Clean Text** - Apply `_remove_book_references()`
8. **Return Results** - Exact count requested

### **2. Book Reference Cleaning (_remove_book_references)**

**Location:** Lines 2897-2956

**15+ Regex Patterns:**

```python
patterns_to_remove = [
    # "According to" patterns
    r'(?:according to|as described in).*?(?:content|text|book|material)[,\s]*',
    r'(?:according to).*?chapter\s+\d+[,\s]*',
    
    # Chapter references
    r'(?:what does|what is)\s+chapter\s+\d+.*?(?:cover|describe)[,\s]*',
    r'chapter\s+\d+\s+(?:of\s+the\s+)?book[,\s]*',
    
    # Content references  
    r'the\s+content\s+(?:describes|mentions|states)[,\s]*',
    r'the\s+text\s+(?:describes|mentions|states)[,\s]*',
    
    # Book/guide references
    r'[A-Z_][A-Z0-9_]*\s+GUIDE?|HANDBOOK|MANUAL|BOOK[,\s]*',
    
    # ... 8+ more patterns
]
```

**Cleaning Steps:**

1. Apply all 15+ regex patterns
2. Clean whitespace (multiple → single)
3. Remove leading/trailing punctuation
4. Fix capitalization (ensure first letter uppercase)
5. Log changes for debugging

### **3. Topic Extraction Methods**

#### **TOC Parsing (Lines 820-1070)**

```
Multi-Method Approach:
├─ Search for TOC-specific content (7 queries)
├─ Get beginning chunks (first 8 chunks)
├─ LLM-based keyword extraction
└─ Fallback to content analysis
```

#### **Keyword Extraction (Lines 2372-2450)**

```
Random Chunk Analysis:
├─ Get 8-12 random chunks from curriculum
├─ Use LLM to extract technical terms
├─ Filter and rank by relevance
└─ Return top 10-12 keywords
```

---

## 📊 Complete Flow Diagram

```
                    ┌──────────────────────────┐
                    │ QuestionGenerationRequest │
                    └────────────┬─────────────┘
                                 │
                    ┌────────────▼─────────────┐
                    │   Route by scope_type    │
                    └────────────┬─────────────┘
                                 │
              ┌──────────────────┼──────────────────┐
              │                  │                  │
              ▼                  ▼                  ▼
      ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
      │   CASE 1     │   │   CASE 2     │   │   CASE 3     │
      │  Curriculum  │   │     Book     │   │    Topics    │
      └──────┬───────┘   └──────┬───────┘   └──────┬───────┘
             │                  │                  │
             ▼                  ▼                  ▼
      ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
      │ STEP 1:      │   │ STEP 1:      │   │ STEP 1:      │
      │ Extract      │   │ Extract      │   │ Analyze &    │
      │ Curriculum   │   │ Book TOC     │   │ Expand       │
      │ Topics       │   │ Topics       │   │ Topics       │
      │ (4 methods)  │   │ (TOC parse)  │   │ (LLM)        │
      └──────┬───────┘   └──────┬───────┘   └──────┬───────┘
             │                  │                  │
             ▼                  ▼                  ▼
      ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
      │ STEP 2:      │   │ STEP 2:      │   │ STEP 2:      │
      │ Get Chunks   │   │ Search Book  │   │ Enhanced     │
      │ for Topics   │   │ for Topics   │   │ Search       │
      │ (aggregate)  │   │ (enhanced)   │   │ (semantic)   │
      └──────┬───────┘   └──────┬───────┘   └──────┬───────┘
             │                  │                  │
             └──────────────────┼──────────────────┘
                                │
                                ▼
                    ┌────────────────────────┐
                    │ STEP 3: Generate       │
                    │ Questions from Content │
                    │                        │
                    │ ├─ Sophisticated Prompt│
                    │ ├─ LLM Invocation      │
                    │ ├─ JSON Parsing        │
                    │ ├─ Validation          │
                    │ └─ Clean References    │
                    └────────────┬───────────┘
                                 │
                                 ▼
                    ┌────────────────────────┐
                    │  Return List[Question] │
                    │  - Professional Style  │
                    │  - No Meta-References  │
                    │  - Exact Count         │
                    └────────────────────────┘
```

---

## 🔑 Key Differentiators

### **Why This System is Sophisticated:**

1. **Multi-Method Topic Extraction**
   - Not just one way to find topics
   - 4 methods for curriculum, TOC parsing for books, LLM expansion for topics
   - Fallback strategies at every level

2. **Enhanced Search with Retry**
   - Multiple search attempts per topic
   - Query reformulation if no results
   - Semantic similarity scoring
   - Diversity filtering

3. **Sophisticated Prompting**
   - Explicit forbidden phrase list (15+)
   - Professional style requirements
   - Technical accuracy emphasis
   - JSON format specification

4. **Comprehensive Cleaning**
   - 15+ regex patterns for reference removal
   - Automatic capitalization fixes
   - Whitespace normalization
   - Logging for debugging

5. **Quality Validation**
   - Field validation at every step
   - Length checks
   - Type validation
   - Exact count enforcement

---

## 📋 Summary Table

| Feature | CASE 1 (Curriculum) | CASE 2 (Book) | CASE 3 (Topics) |
|---------|-------------------|---------------|----------------|
| **Topic Extraction** | 4 methods (TOC all books, overview, content, random) | TOC parsing (search + beginning) + fallback | LLM-based expansion |
| **Search Strategy** | Aggregate across books | Book-specific enhanced search | Semantic topic search |
| **Chunks Retrieved** | 15-20 diverse | 12-15 book-specific | 8-10 highly relevant |
| **Generation Method** | Shared sophisticated prompt | Shared sophisticated prompt | Shared sophisticated prompt |
| **Cleaning** | 15+ regex patterns | 15+ regex patterns | 15+ regex patterns |
| **Primary Use Case** | Full curriculum exams | Single book exams | Focused topic quizzes |

---

## 🎓 Result Quality

**Generated Questions:**
- ✅ Sound like professional certification exams
- ✅ No "According to..." or chapter references
- ✅ Direct technical questions
- ✅ Clear and unambiguous
- ✅ Based on actual content
- ✅ Properly formatted JSON

**Example:**

**Bad (Avoided):** "According to Chapter 2, what is the primary role of data engineers?"

**Good (Generated):** "What is the primary role of data engineers in an organization?"

---

**Status:** Complete flow documentation of sophisticated 3-case exam generation system  
**Source File:** `chat_service_backup.py` (4593 lines)  
**Last Updated:** October 18, 2025
