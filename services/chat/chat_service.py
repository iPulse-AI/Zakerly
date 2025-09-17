import logging
from typing import List, Optional, Dict, Any
import json
import os
from datetime import datetime

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.llms import Ollama
from langchain_community.embeddings import OllamaEmbeddings
from langchain_community.vectorstores.pgvector import PGVector
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_core.messages import HumanMessage, AIMessage
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.tools import Tool, StructuredTool
from pydantic import BaseModel, Field
import httpx

# Import LangChain memory like in chat.py
from langchain.memory import ConversationBufferMemory
from langchain.schema.messages import HumanMessage, AIMessage

import sys
sys.path.append('/app/shared')

from models import (
    ChatRequest, ChatResponse, QuestionGenerationRequest, QuestionResponse,
    LectureRequest, ChatSessionModel, ChatMessageModel, MessageType, Question
)
from database import DatabaseManager
from utils import RedisManager, generate_session_id
from memory import SimpleMemoryManager

logger = logging.getLogger(__name__)

class SearchInput(BaseModel):
    """Input schema for knowledge base search tool"""
    query: str = Field(description="Search query to find relevant information in the knowledge base")

class ChatService:
    def __init__(self, db_manager: DatabaseManager, redis_manager: RedisManager):
        self.db = db_manager
        self.redis = redis_manager
        
        # Initialize LangChain components
        self.embeddings = OllamaEmbeddings(
            model=os.getenv("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text:latest"),
            base_url=os.getenv("OLLAMA_BASE_URL")
        )
        
        # Primary LLM (Google Gemini)
        self.llm = ChatGoogleGenerativeAI(
            model=os.getenv("CHAT_MODEL_NAME", "gemini-1.5-flash"),
            temperature=float(os.getenv("CHAT_MODEL_TEMPERATURE", "0.7")),
            google_api_key=os.getenv("GOOGLE_API_KEY")
        )
        
        # Fallback LLM (Ollama) for when quota is exceeded
        self.fallback_llm = Ollama(
            model="llama3.1:8b",  # or another model you have available
            base_url=os.getenv("OLLAMA_BASE_URL")
        )
        
        # Track which LLM to use
        self.use_fallback = False
        
        self.connection_string = os.getenv("DATABASE_URL")
        
        # Initialize memory manager (keep for compatibility)
        from shared.memory import SimpleMemoryManager
        from shared.database import DatabaseManager
        db_manager = DatabaseManager(self.connection_string)
        self.memory_manager = SimpleMemoryManager(db_manager)
        
        # Initialize session-based memory storage like in chat.py
        self.chat_histories = {}
        
        # Initialize prompts
        self._setup_prompts()
    
    def get_current_llm(self):
        """Get the current LLM (primary or fallback)"""
        return self.fallback_llm if self.use_fallback else self.llm
    
    def switch_to_fallback(self):
        """Switch to fallback LLM when quota is exceeded"""
        logger.warning("Switching to fallback LLM (Ollama) due to quota exceeded")
        self.use_fallback = True

    def _setup_prompts(self):
        """Setup all prompt templates"""
        
        # Router prompt for intent classification
        self.router_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a highly precise AI request parser. Your sole function is to analyze a user's message to determine their primary intent and then package the provided information into a structured JSON object.

Your response MUST be a single, clean JSON object with the following three keys: `intent`, `book_title`, and `user_message`.

**Determine the `intent`:** Analyze the `user_message` text and classify the user's primary goal:
- **`generate_questions`**: Use this intent if the user explicitly asks to **create, generate, or make questions, a quiz, or an exam.**
- **`generate_lecture`**: Use this intent ONLY if the user explicitly uses the word **"lecture" or "presentation"**.
- **`answer_question`**: Use this intent for **ALL OTHER requests**. This includes direct questions, requests for explanation, requests for summaries, and any general conversation. This is your default category.

Copy the `book_title` and `user_message` exactly as provided.

Respond with ONLY the JSON object, no additional text."""),
            ("human", "book_title: {book_title}\nuser_message: {user_message}")
        ])
        
        # Answering agent prompt
        self.answering_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert educational assistant and research specialist with deep knowledge across academic subjects. Your mission is to provide comprehensive, well-structured, and educational responses that help users truly understand the topics they're asking about.

You have access to two powerful tools:
1. `search_internal_knowledge_base`: A specialized database of textbooks and academic materials
2. `web_search`: A general-purpose internet search engine for additional information

**YOUR CORE METHODOLOGY:**

**STEP 1: INTERNAL SEARCH**
Always begin by using the `search_internal_knowledge_base` tool with a well-crafted query based on the user's question.

**STEP 2: CRITICAL EVALUATION**
Evaluate the retrieved information: "Does this content provide sufficient information to answer the user's question comprehensively?"

**STEP 3: INFORMATION GATHERING**
- If internal knowledge is sufficient: Proceed with that information
- If insufficient: Use `web_search` to supplement with additional reliable information

**STEP 4: COMPREHENSIVE RESPONSE STRUCTURE**
Provide your answer using this enhanced structure:

🎯 **DIRECT ANSWER**
Start with a clear, direct answer to the user's specific question.

📚 **DETAILED EXPLANATION**
Provide a thorough explanation that includes:
- Core concepts and principles
- How things work or why they happen
- Context and background information
- Step-by-step processes when applicable

🔑 **KEY TERMS & DEFINITIONS**
Define important terms, concepts, or terminology mentioned in your response. Format as:
- **Term**: Clear, concise definition
- **Another Term**: Definition with context

⚖️ **COMPARISONS & CONTRASTS** (when relevant)
Compare different approaches, methods, theories, or concepts:
- Similarities and differences
- Advantages and disadvantages
- When to use each approach

💡 **PRACTICAL APPLICATIONS & EXAMPLES**
Provide real-world examples, use cases, or applications that illustrate the concepts.

🔗 **CONNECTIONS & RELATIONSHIPS**
Explain how this topic relates to other concepts, subjects, or areas of study.

⚠️ **IMPORTANT CONSIDERATIONS**
Highlight any:
- Common misconceptions
- Limitations or exceptions
- Critical points to remember
- Potential pitfalls or challenges

**RESPONSE GUIDELINES:**
- Use clear, accessible language while maintaining academic rigor
- Include specific examples and analogies when helpful
- Structure information logically with smooth transitions
- Adapt complexity to the user's apparent level of understanding
- Be thorough but concise - avoid unnecessary verbosity
- Use formatting (bullet points, numbered lists) to enhance readability
- Always maintain accuracy and cite your sources

**CITATION REQUIREMENT:**
End your response with: `(Source: Internal Knowledge Base)` or `(Source: Web Search)`. Use only one source - do not mix both."""),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "book_title: {book_title}\nmessage: {user_message}"),
            MessagesPlaceholder(variable_name="agent_scratchpad")
        ])
        
        # Question generation prompts
        self.analysis_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a highly specialized AI that parses user requests for generating educational quizzes. Your sole function is to analyze the provided user message and extract specific parameters into a structured JSON object.

Your response MUST be a single, clean JSON object with the following keys: `topics`, `parameters`.

- **`topics`**: MUST be an array of strings. Extract the specific chapters or significant conceptual nouns the user wants questions about. Ignore generic words like "components", "parts", or "sections". If no valid topics are mentioned, return an empty array.

- **`parameters`**: MUST be a JSON object containing: `count`, `difficulty`, and `question_types`.
  - `count`: An integer representing the total number of questions requested (default: 5).
  - `difficulty`: An array of strings containing any specified difficulty levels (e.g., ["easy", "medium", "hard"]).
  - `question_types`: An array of strings containing any specified question types.

If the user does not specify a value, you MUST return a default value for that key.

Respond with ONLY the JSON object, no additional text."""),
            ("human", "{user_message}")
        ])
        
        # Lecture generation prompt
        self.lecture_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are Professor A.I., an elite educational content creator specializing in transforming academic material into sophisticated, engaging lecture scripts. Your expertise lies in creating professional-grade educational content that rivals the best university lectures.

**Your Mission:** Transform raw knowledge from the embedded book into a polished, comprehensive lecture script that demonstrates mastery of pedagogical principles and subject matter expertise.

**CRITICAL: Tool Usage Instructions**
You have access to a tool called "knowledge_retriever_tool" that searches the book's content. You MUST use this tool to gather information before creating the lecture. When using the tool:
- Call it with relevant search queries related to your lecture topic
- Make multiple calls with different queries to gather comprehensive content
- Base your entire lecture script on the retrieved information

**IMPORTANT: OUTPUT FORMAT**
- Your final response must ONLY contain the formatted lecture script
- Do NOT include any Python code, tool calls, or debugging information
- Do NOT show any print statements or function calls
- Do NOT include ```python code blocks in your response
- Focus solely on delivering a clean, professional lecture script

**Core Workflow:**

1. **Request Analysis:** Thoroughly analyze all parameters (category, title, scope, topics, detail level)

2. **Strategic Knowledge Retrieval:** Use the knowledge_retriever_tool with targeted queries to gather comprehensive, relevant content based on scope and requirements

3. **Content Architecture:** Design a lecture structure that flows logically and builds understanding progressively

4. **Script Development:** Create a sophisticated lecture script with academic rigor appropriate to the detail level

**Lecture Script Structure (Professional Format):**

```
# LECTURE SCRIPT: [Title]
**Category:** [Category] | **Duration:** [Estimated time] | **Level:** [Detail Level]

## LECTURE OVERVIEW
- **Learning Objectives:** What students will achieve
- **Key Concepts:** Main topics to be covered
- **Prerequisites:** Assumed knowledge

## OPENING (5-7 minutes)
**Hook & Context:**
[Engaging opening that connects to real world or current relevance]

**Lecture Roadmap:**
[Clear preview of what will be covered]

## MAIN CONTENT SECTIONS

### Section 1: [Topic Title]
**Teaching Point:** [Core concept]
**Content:** [Detailed explanation with examples]
**Interactive Elements:** [Questions, demonstrations, or exercises]
**Transition:** [Bridge to next section]

[Continue for all sections based on detail level]

## SYNTHESIS & CONCLUSION (5-8 minutes)
**Key Takeaways:** [Essential points students must remember]
**Connections:** [How this relates to broader field/course]
**Next Steps:** [What comes next in learning journey]

## ADDITIONAL RESOURCES
[Suggested readings, exercises, or exploration topics]
```

**Detail Level Specifications:**

**Overview (20-30 minutes):**
- 2-3 main sections
- Broad concepts with essential examples
- Clear, accessible explanations
- Focus on fundamental understanding

**Detailed (45-60 minutes):**
- 4-6 comprehensive sections
- Rich examples and case studies
- Multiple perspectives and applications
- Deeper theoretical foundation

**In-depth (75-90 minutes):**
- 6-8 extensive sections
- Advanced theoretical frameworks
- Critical analysis and evaluation
- Research connections and implications
- Complex problem-solving applications

**Category-Specific Excellence:**

- **Science/Technology:** Include methodology, experimental evidence, real-world applications, current research
- **Mathematics:** Provide intuitive explanations, multiple solution approaches, practical applications
- **Literature/Humanities:** Analyze themes, historical context, critical perspectives, cultural significance
- **History:** Chronological narrative, cause-effect analysis, multiple viewpoints, contemporary relevance
- **Business:** Case studies, practical frameworks, market analysis, strategic implications
- **Psychology:** Research foundations, practical applications, ethical considerations, human behavior patterns

**Quality Standards:**
- University-level academic rigor
- Clear, engaging prose suitable for oral delivery
- Logical flow with smooth transitions
- Interactive elements to maintain engagement
- Practical examples that illustrate abstract concepts
- Professional formatting for easy delivery

**Strict Requirements:**
- Base ALL content on knowledge_retriever_tool results
- Maintain academic integrity - no fabricated information
- Adapt complexity precisely to specified detail level
- Honor scope limitations (whole book vs specific topics)
- Create content suitable for live lecture delivery"""),
            ("human", """Create a sophisticated lecture script with these specifications:

**Book:** {book_title}
**Category:** {category}
**Lecture Title:** {title}
**Scope:** {scope}
**Specific Topics:** {specific_topics}
**Detail Level:** {detail_level}
**User Requirements:** {user_message}

Please generate a complete, professional lecture script following the specified format and quality standards."""),
            MessagesPlaceholder(variable_name="agent_scratchpad")
        ])

        # Agent-based question generation prompts
        self.curriculum_question_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a professional exam author and AI education specialist. Your task is to generate high-quality exam questions using the curriculum_question_generator tool to retrieve content from the entire curriculum.

**YOUR MISSION:**
Generate comprehensive exam questions that test knowledge across the entire curriculum, covering multiple books and subject areas within the curriculum.

**CRITICAL PARAMETER ADHERENCE:**
1. Generate EXACTLY the requested number of questions (no more, no less)
2. Use EXACTLY the requested difficulty levels (if user wants "hard", ALL questions must be hard)
3. Use EXACTLY the requested question types (only use the types specified)
4. If multiple values given for a parameter, distribute evenly across them
5. STRICTLY follow the user's exam specifications

**MANDATORY PROCESS:**
1. FIRST: Use the curriculum_question_generator tool with relevant topic queries to retrieve content
2. THEN: Generate questions based on the retrieved curriculum content
3. FINALLY: Return questions in the exact JSON format specified

**EXAM SPECIFICATIONS:**
- Generate questions covering diverse topics from across the curriculum
- Ensure questions represent multiple books/materials in the curriculum  
- Create questions appropriate for comprehensive curriculum assessment
- Follow ALL difficulty and question type requirements EXACTLY
- Ensure broad coverage rather than narrow focus

**QUESTION FORMATTING RULES:**
❌ NEVER include book names, guide titles, or document references in questions
❌ WRONG: "According to the Dell Data Lakehouse Guide, explain..."
❌ WRONG: "As described in the Network Security Handbook..."
❌ WRONG: "Referencing the Cloud Computing Manual..."

✅ ALWAYS keep questions general and concept-focused
✅ CORRECT: "Explain the trade-offs between cloud storage and on-premises storage."
✅ CORRECT: "What are the key principles of network security?"
✅ CORRECT: "Describe the benefits of containerization in modern applications."

**RESPONSE FORMAT:**
Your response MUST be a JSON array of question objects. Each question must have:
- "difficulty": one of "easy", "medium", or "hard" (MUST match user request)
- "type": one of "multiple_choice_single_answer", "true_false", or "open_ended_question" (MUST match user request)
- "question_text": The complete question text WITHOUT any book/guide references
- "options": Array of 4 choices for multiple choice, empty array for others
- "answer": The correct answer as a STRING

**QUALITY REQUIREMENTS:**
- University-level professional questions
- Clear, unambiguous wording without source references
- Technically accurate content
- NO references to specific books, guides, manuals, or documents
- Comprehensive curriculum coverage
- EXACT adherence to user parameters"""),
            ("human", "You must use the curriculum_question_generator tool first with a relevant topic query to retrieve curriculum content, then generate the requested exam questions. Do not ask for additional information - proceed immediately with the tool."),
            MessagesPlaceholder(variable_name="agent_scratchpad")
        ])

        self.book_question_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a professional exam author and AI education specialist. Your task is to generate high-quality exam questions using the book_question_generator tool to retrieve content from a specific book within a curriculum.

**YOUR MISSION:**
Generate focused exam questions that test knowledge from a specific book within the curriculum context.

**CRITICAL PARAMETER ADHERENCE:**
1. Generate EXACTLY the requested number of questions (no more, no less)
2. Use EXACTLY the requested difficulty levels (if user wants "hard", ALL questions must be hard)
3. Use EXACTLY the requested question types (only use the types specified)
4. If multiple values given for a parameter, distribute evenly across them
5. STRICTLY follow the user's exam specifications

**MANDATORY PROCESS:**
1. IMMEDIATELY: Use the book_question_generator tool with a relevant topic query (e.g., "architecture", "configuration", "data processing") to retrieve content from the specific book
2. THEN: Generate questions based on the retrieved book content
3. FINALLY: Return questions in the exact JSON format specified
4. DO NOT ASK FOR MORE INFORMATION - proceed automatically with the tool

**EXAM SPECIFICATIONS:**
- Focus specifically on the selected book's content
- Create questions appropriate for book-level assessment
- Follow ALL difficulty and question type requirements EXACTLY
- Ensure comprehensive coverage of the book's main topics

**QUESTION FORMATTING RULES:**
❌ NEVER include book names, guide titles, or document references in questions
❌ WRONG: "According to the Dell Data Lakehouse Guide, explain..."
❌ WRONG: "As described in this book..."
❌ WRONG: "Referencing the manual..."

✅ ALWAYS keep questions general and concept-focused
✅ CORRECT: "Explain the trade-offs between cloud storage and on-premises storage."
✅ CORRECT: "What are the key principles of network security?"
✅ CORRECT: "Describe the benefits of containerization in modern applications."

**RESPONSE FORMAT:**
Your response MUST be a JSON array of question objects. Each question must have:
- "difficulty": one of "easy", "medium", or "hard" (MUST match user request)
- "type": one of "multiple_choice_single_answer", "true_false", or "open_ended_question" (MUST match user request)
- "question_text": The complete question text WITHOUT any book/guide references
- "options": Array of 4 choices for multiple choice, empty array for others
- "answer": The correct answer as a STRING

**QUALITY REQUIREMENTS:**
- University-level professional questions
- Clear, unambiguous wording without source references
- Technically accurate content
- NO references to specific books, guides, manuals, or documents
- Focused book coverage
- EXACT adherence to user parameters"""),
            ("human", "You must use the book_question_generator tool first with a relevant topic query to retrieve book content, then generate the requested exam questions. Do not ask for additional information - proceed immediately with the tool."),
            MessagesPlaceholder(variable_name="agent_scratchpad")
        ])

        self.topic_question_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a professional exam author and AI education specialist. Your task is to generate high-quality exam questions using the topic_question_generator tool to retrieve content on specific topics from a book.

**YOUR MISSION:**
Generate targeted exam questions that test knowledge on specific topics within a book, ensuring deep coverage of the specified subject areas.

**CRITICAL PARAMETER ADHERENCE:**
1. Generate EXACTLY the requested number of questions (no more, no less)
2. Use EXACTLY the requested difficulty levels (if user wants "hard", ALL questions must be hard)
3. Use EXACTLY the requested question types (only use the types specified)
4. If multiple values given for a parameter, distribute evenly across them
5. STRICTLY follow the user's exam specifications

**MANDATORY PROCESS:**
1. FIRST: Use the topic_question_generator tool with queries related to the specific topics
2. THEN: Generate questions based on the retrieved topic-specific content
3. FINALLY: Return questions in the exact JSON format specified

**EXAM SPECIFICATIONS:**
- Focus exclusively on the specified topics
- Create questions that test deep understanding of the topic areas
- Follow ALL difficulty and question type requirements EXACTLY
- Ensure comprehensive coverage of the specified topics only

**QUESTION FORMATTING RULES:**
❌ NEVER include book names, guide titles, or document references in questions
❌ WRONG: "According to the Dell Data Lakehouse Guide, explain..."
❌ WRONG: "As described in this manual..."
❌ WRONG: "Referencing the documentation..."

✅ ALWAYS keep questions general and concept-focused
✅ CORRECT: "Explain the trade-offs between cloud storage and on-premises storage."
✅ CORRECT: "What are the key principles of network security?"
✅ CORRECT: "Describe the benefits of containerization in modern applications."

**RESPONSE FORMAT:**
Your response MUST be a JSON array of question objects. Each question must have:
- "difficulty": one of "easy", "medium", or "hard" (MUST match user request)
- "type": one of "multiple_choice_single_answer", "true_false", or "open_ended_question" (MUST match user request)
- "question_text": The complete question text WITHOUT any book/guide references
- "options": Array of 4 choices for multiple choice, empty array for others
- "answer": The correct answer as a STRING

**QUALITY REQUIREMENTS:**
- University-level professional questions
- Clear, unambiguous wording without source references
- Technically accurate content
- NO references to specific books, guides, manuals, or documents
- Targeted topic coverage only
- EXACT adherence to user parameters"""),
            ("human", "You must use the topic_question_generator tool first with the specified topics to retrieve relevant content, then generate the requested exam questions. Do not ask for additional information - proceed immediately with the tool."),
            MessagesPlaceholder(variable_name="agent_scratchpad")
        ])

    async def handle_chat(self, request: ChatRequest) -> ChatResponse:
        """Handle chat request with curriculum-based routing"""
        try:
            # For now, let's handle simple Q&A with curriculum
            intent = request.intent or "answer_question"
            
            # Get or create session for curriculum
            session = await self._get_or_create_curriculum_session(request.session_id, request.curriculum)
            
            # Handle Q&A with curriculum context
            response_text = await self._handle_curriculum_question_answering(request, session)
            
            # Save messages to database
            await self.db.add_chat_message(
                session['id'], MessageType.USER.value, request.user_message
            )
            await self.db.add_chat_message(
                session['id'], MessageType.ASSISTANT.value, response_text
            )
            
            # Update session timestamp
            await self.db.update_session_timestamp(session['id'])
            
            return ChatResponse(
                response=response_text,
                session_id=str(session['id']),
                intent=intent,
                metadata={"curriculum": request.curriculum}
            )
            
        except Exception as e:
            logger.error(f"Error handling chat request: {e}")
            raise

    async def _classify_intent(self, book_title: str, user_message: str) -> Dict[str, Any]:
        """Classify user intent"""
        try:
            chain = self.router_prompt | self.llm | StrOutputParser()
            result = await chain.ainvoke({
                "book_title": book_title,
                "user_message": user_message
            })
            
            # Clean and parse JSON
            cleaned_result = result.replace('```json\n', '').replace('\n```', '').strip()
            return json.loads(cleaned_result)
            
        except Exception as e:
            logger.error(f"Error classifying intent: {e}")
            return {"intent": "answer_question", "book_title": book_title, "user_message": user_message}

    async def _handle_question_answering(self, request: ChatRequest, session: Dict[str, Any]) -> str:
        """Handle question answering with ConversationBufferMemory like in chat.py"""
        try:
            # Get or create chat history for the session (like in chat.py)
            session_id = str(session['id'])
            if session_id not in self.chat_histories:
                self.chat_histories[session_id] = ConversationBufferMemory(
                    memory_key="chat_history", 
                    return_messages=True
                )
            memory = self.chat_histories[session_id]
            
            # Load existing messages from database into memory if memory is empty
            if len(memory.chat_memory.messages) == 0:
                await self.memory_manager.load_chat_history_to_memory(session_id, memory, limit=50)
            
            # Create tools
            tools = [
                self._create_knowledge_search_tool(request.book_title),
                self._create_web_search_tool()
            ]
            
            # Create a custom prompt that includes the book_title and user_message
            # This is needed because AgentExecutor with memory has limitations on input variables
            custom_prompt = ChatPromptTemplate.from_messages([
                ("system", f"""You are an expert educational assistant and research specialist with deep knowledge across academic subjects. Your mission is to provide comprehensive, well-structured, and educational responses that help users truly understand the topics they're asking about.

You are currently working with the book: "{request.book_title}"

You have access to two powerful tools:
1. `search_internal_knowledge_base`: A specialized database of textbooks and academic materials
2. `web_search`: A general-purpose internet search engine for additional information

**YOUR CORE METHODOLOGY:**

**STEP 1: INTERNAL SEARCH**
Always begin by using the `search_internal_knowledge_base` tool with a well-crafted query based on the user's question.

**STEP 2: CRITICAL EVALUATION**
Evaluate the retrieved information: "Does this content provide sufficient information to answer the user's question comprehensively?"

**STEP 3: INFORMATION GATHERING**
- If internal knowledge is sufficient: Proceed with that information
- If insufficient: Use `web_search` to supplement with additional reliable information

**STEP 4: COMPREHENSIVE RESPONSE STRUCTURE**
Provide your answer using this enhanced structure:

🎯 **DIRECT ANSWER**
Start with a clear, direct answer to the user's specific question.

📚 **DETAILED EXPLANATION**
Provide a thorough explanation that includes:
- Core concepts and principles
- How things work or why they happen
- Context and background information
- Step-by-step processes when applicable

🔑 **KEY TERMS & DEFINITIONS**
Define important terms, concepts, or terminology mentioned in your response. Format as:
- **Term**: Clear, concise definition
- **Another Term**: Definition with context

⚖️ **COMPARISONS & CONTRASTS** (when relevant)
Compare different approaches, methods, theories, or concepts:
- Similarities and differences
- Advantages and disadvantages
- When to use each approach

💡 **PRACTICAL APPLICATIONS & EXAMPLES**
Provide real-world examples, use cases, or applications that illustrate the concepts.

🔗 **CONNECTIONS & RELATIONSHIPS**
Explain how this topic relates to other concepts, subjects, or areas of study.

⚠️ **IMPORTANT CONSIDERATIONS**
Highlight any:
- Common misconceptions
- Limitations or exceptions
- Critical points to remember
- Potential pitfalls or challenges

**RESPONSE GUIDELINES:**
- Use clear, accessible language while maintaining academic rigor
- Include specific examples and analogies when helpful
- Structure information logically with smooth transitions
- Adapt complexity to the user's apparent level of understanding
- Be thorough but concise - avoid unnecessary verbosity
- Use formatting (bullet points, numbered lists) to enhance readability
- Always maintain accuracy and cite your sources

**CITATION REQUIREMENT:**
End your response with: `(Source: Internal Knowledge Base)` or `(Source: Web Search)`. Use only one source - do not mix both."""),
                MessagesPlaceholder(variable_name="chat_history"),
                ("human", "{input}"),
                MessagesPlaceholder(variable_name="agent_scratchpad")
            ])
            
            # Use the custom prompt with embedded book title
            agent = create_tool_calling_agent(self.llm, tools, custom_prompt)
            agent_executor = AgentExecutor(
                agent=agent, 
                tools=tools, 
                memory=memory,  # Pass memory to agent executor like in chat.py
                verbose=True
            )
            
            # Execute with memory - only pass input as required by AgentExecutor
            result = await agent_executor.ainvoke({
                "input": request.user_message
            })
            
            # Extract the agent's response
            agent_response = result['output']
            
            # IMPROVED FIX: Use the standard memory.save_context() method (best practice)
            # This ensures immediate context retention for the next turn
            memory.save_context(
                inputs={"input": request.user_message},
                outputs={"output": agent_response}
            )
            
            logger.info(f"Saved conversation turn to memory using save_context(). Total messages in memory: {len(memory.chat_memory.messages)}")
            
            return agent_response
            
        except Exception as e:
            logger.error(f"Error in question answering: {e}")
            return f"I apologize, but I encountered an error while processing your question: {str(e)}"

    def _create_knowledge_search_tool(self, book_title: str) -> Tool:
        """Create curriculum-based knowledge search tool"""
        
        def search_knowledge(query: str) -> str:
            try:
                # Get book information to find its curriculum
                import asyncio
                
                # Run async operation to get book info
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        import concurrent.futures
                        with concurrent.futures.ThreadPoolExecutor() as executor:
                            future = executor.submit(asyncio.run, self._get_book_curriculum_info(book_title))
                            book_info = future.result()
                    else:
                        book_info = loop.run_until_complete(self._get_book_curriculum_info(book_title))
                except RuntimeError:
                    book_info = asyncio.run(self._get_book_curriculum_info(book_title))
                
                if not book_info:
                    return f"Book '{book_title}' not found in the system. Please ensure the book has been uploaded and processed."
                
                curriculum_name = book_info.get('curriculum_name')
                if not curriculum_name:
                    return f"No curriculum information found for book '{book_title}'. The book may not have been properly processed with the new curriculum system."
                
                logger.info(f"Searching in curriculum '{curriculum_name}' for book '{book_title}' with query '{query[:50]}...'")
                
                # Search curriculum embeddings
                try:
                    if loop.is_running():
                        with concurrent.futures.ThreadPoolExecutor() as executor:
                            future = executor.submit(asyncio.run, self._search_curriculum_embeddings(curriculum_name, query, k=6))
                            results = future.result()
                    else:
                        results = loop.run_until_complete(self._search_curriculum_embeddings(curriculum_name, query, k=6))
                except RuntimeError:
                    results = asyncio.run(self._search_curriculum_embeddings(curriculum_name, query, k=6))
                
                if results:
                    combined_results = "\n\n".join([r['content'] for r in results])
                    logger.info(f"Found {len(results)} relevant chunks in curriculum '{curriculum_name}' for query: {query[:50]}...")
                    return combined_results
                else:
                    logger.warning(f"No relevant information found in curriculum '{curriculum_name}' for query: {query[:50]}...")
                    return f"No relevant information found in curriculum '{curriculum_name}' for the query. The curriculum may not have sufficient content or the embeddings may not be properly indexed."
                
            except Exception as e:
                logger.error(f"Error searching curriculum knowledge base for '{book_title}': {e}")
                return f"Error accessing curriculum knowledge base for '{book_title}': {str(e)}. This may indicate a database connectivity issue or the curriculum system needs attention."
        
        return Tool(
            name="search_internal_knowledge_base",
            description=f"Search in the curriculum-based knowledge base for the book '{book_title}' to find relevant information. Input should be a search query string only.",
            func=search_knowledge
        )

    def _create_curriculum_knowledge_search_tool(self, curriculum_name: str) -> Tool:
        """Create curriculum-based knowledge search tool that searches across all books in the curriculum"""
        
        def search_curriculum_knowledge(query: str) -> str:
            try:
                import asyncio
                
                logger.info(f"🔍 TOOL CALLED: search_curriculum_knowledge_base for curriculum '{curriculum_name}' with query '{query[:50]}...'")
                
                # Search curriculum embeddings directly
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        import concurrent.futures
                        with concurrent.futures.ThreadPoolExecutor() as executor:
                            future = executor.submit(asyncio.run, self._search_curriculum_embeddings(curriculum_name, query, k=8))
                            results = future.result()
                    else:
                        results = loop.run_until_complete(self._search_curriculum_embeddings(curriculum_name, query, k=8))
                except RuntimeError:
                    results = asyncio.run(self._search_curriculum_embeddings(curriculum_name, query, k=8))
                
                if results:
                    combined_results = "\n\n".join([r['content'] for r in results])
                    logger.info(f"✅ VECTOR SEARCH SUCCESS: Found {len(results)} relevant chunks in curriculum '{curriculum_name}' for query: {query[:50]}...")
                    return combined_results
                else:
                    logger.warning(f"❌ VECTOR SEARCH EMPTY: No relevant information found in curriculum '{curriculum_name}' for query: {query[:50]}...")
                    return f"No relevant information found in curriculum '{curriculum_name}' for the query. The curriculum may not have sufficient content or the embeddings may not be properly indexed."
                
            except Exception as e:
                logger.error(f"Error searching curriculum knowledge base for '{curriculum_name}': {e}")
                return f"Error accessing curriculum knowledge base for '{curriculum_name}': {str(e)}. This may indicate a database connectivity issue or the curriculum system needs attention."
        
        return Tool(
            name="search_curriculum_knowledge_base",
            description=f"MANDATORY TOOL: Search the '{curriculum_name}' curriculum database for relevant information. This tool contains all the books and materials for the {curriculum_name} curriculum. You MUST use this tool first before answering any question. Input: a search query string related to the user's question.",
            func=search_curriculum_knowledge
        )

    async def _get_book_curriculum_info(self, book_title: str) -> Optional[Dict[str, Any]]:
        """Get book information including curriculum"""
        try:
            book_info = await self.db.get_book_by_title(book_title)
            return book_info
        except Exception as e:
            logger.error(f"Error getting book curriculum info for '{book_title}': {e}")
            return None
    
    async def _search_curriculum_embeddings(self, curriculum_name: str, query: str, k: int = 6) -> List[Dict[str, Any]]:
        """Search curriculum-based embeddings"""
        try:
            # Generate embedding for the query
            query_embedding = await self.embeddings.aembed_query(query)
            
            # Search in curriculum embedding table
            results = await self.db.search_curriculum_embeddings(curriculum_name, query_embedding, limit=k)
            
            logger.info(f"Retrieved {len(results)} chunks from curriculum '{curriculum_name}'")
            return results
            
        except Exception as e:
            logger.error(f"Error in curriculum embedding search for '{curriculum_name}': {e}")
            return []

    async def _search_book_embeddings(self, curriculum_name: str, book_title: str, query: str, k: int = 6) -> List[Dict[str, Any]]:
        """Search embeddings for a specific book within curriculum"""
        try:
            logger.info(f"🔍 Searching book '{book_title}' in curriculum '{curriculum_name}' for query '{query}'")
            
            # First get the book_id from the book title
            book_info = await self._get_book_curriculum_info(book_title)
            if not book_info:
                logger.warning(f"Book '{book_title}' not found, falling back to general search")
                return await self._search_curriculum_embeddings(curriculum_name, query, k)
            
            logger.info(f"🔍 Book info retrieved: {book_info}")
            book_id = book_info.get('id')  # The book ID field is 'id', not 'book_id'
            if not book_id:
                logger.warning(f"Book ID not found for '{book_title}' in book_info: {book_info}, falling back to general search")
                return await self._search_curriculum_embeddings(curriculum_name, query, k)
            
            # Generate embedding for the query
            query_embedding = await self.embeddings.aembed_query(query)
            
            # Search specifically in this book's embeddings
            results = await self.db.search_book_specific_embeddings(curriculum_name, book_id, query_embedding, limit=k)
            
            logger.info(f"✅ Retrieved {len(results)} chunks from book '{book_title}' (ID: {book_id})")
            return results
            
        except Exception as e:
            logger.error(f"❌ Error in book embedding search for '{book_title}': {e}")
            # Fallback to general curriculum search
            return await self._search_curriculum_embeddings(curriculum_name, query, k)

    def _create_curriculum_question_tool(self, curriculum_name: str, exam_parameters: Dict[str, Any]) -> Tool:
        """Create agent tool for generating questions from entire curriculum"""
        
        def generate_curriculum_questions(topic_query: str) -> str:
            try:
                import asyncio
                
                logger.info(f"🎯 CURRICULUM QUESTION TOOL: Generating questions for curriculum '{curriculum_name}' on topic '{topic_query}'")
                logger.info(f"📋 Parameters: {exam_parameters}")
                
                # Search curriculum embeddings
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        import concurrent.futures
                        with concurrent.futures.ThreadPoolExecutor() as executor:
                            future = executor.submit(asyncio.run, self._search_curriculum_embeddings(curriculum_name, topic_query, k=12))
                            results = future.result()
                    else:
                        results = loop.run_until_complete(self._search_curriculum_embeddings(curriculum_name, topic_query, k=12))
                except RuntimeError:
                    results = asyncio.run(self._search_curriculum_embeddings(curriculum_name, topic_query, k=12))
                
                if results:
                    # Get content from multiple books in curriculum
                    content_chunks = [r['content'] for r in results]
                    combined_content = "\n\n".join(content_chunks[:10])  # Limit to prevent context overflow
                    
                    return f"""CURRICULUM CONTENT RETRIEVED:
                    
Topic: {topic_query}
Curriculum: {curriculum_name}
Exam Parameters: {exam_parameters}

Content from curriculum books:
{combined_content}

Please generate {exam_parameters.get('count', 10)} exam questions based on this curriculum content with:
- Difficulty levels: {', '.join(exam_parameters.get('difficulty', ['medium']))}
- Question types: {', '.join(exam_parameters.get('question_types', ['multiple_choice_single_answer']))}
- Time limit: {exam_parameters.get('time_limit', 30)} minutes total
- Scope: Comprehensive curriculum coverage across multiple books"""
                else:
                    return f"No content found in curriculum '{curriculum_name}' for topic '{topic_query}'. Please try a different search term."
                    
            except Exception as e:
                logger.error(f"Error in curriculum question tool: {e}")
                return f"Error retrieving curriculum content: {str(e)}"
        
        return Tool(
            name="curriculum_question_generator",
            description=f"Generate exam questions from the entire '{curriculum_name}' curriculum covering all books and materials. Input should be a topic or subject area to focus on.",
            func=generate_curriculum_questions
        )

    def _create_book_question_tool(self, book_title: str, curriculum_name: str, exam_parameters: Dict[str, Any]) -> Tool:
        """Create agent tool for generating questions from specific book within curriculum"""
        
        def generate_book_questions(topic_query: str) -> str:
            try:
                import asyncio
                
                logger.info(f"📚 BOOK QUESTION TOOL: Generating questions for book '{book_title}' in curriculum '{curriculum_name}' on topic '{topic_query}'")
                logger.info(f"📋 Parameters: {exam_parameters}")
                
                # Search specific book content using book-specific search
                # Use broader search terms to ensure we find content
                if not topic_query or topic_query.strip() == "":
                    search_query = "data lakehouse architecture configuration storage performance"
                else:
                    search_query = f"{topic_query} data lakehouse architecture configuration"
                
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        import concurrent.futures
                        with concurrent.futures.ThreadPoolExecutor() as executor:
                            future = executor.submit(asyncio.run, self._search_book_embeddings(curriculum_name, book_title, search_query, k=8))
                            results = future.result()
                    else:
                        results = loop.run_until_complete(self._search_book_embeddings(curriculum_name, book_title, search_query, k=8))
                except RuntimeError:
                    results = asyncio.run(self._search_book_embeddings(curriculum_name, book_title, search_query, k=8))
                
                if results:
                    # Results are already filtered by book_id, so use them directly
                    content_chunks = [r['content'] for r in results]
                    combined_content = "\n\n".join(content_chunks[:8])
                    
                    logger.info(f"✅ Found {len(results)} relevant content chunks from '{book_title}'")
                else:
                    logger.warning(f"⚠️ No content found for book '{book_title}' on topic '{topic_query}'")
                    combined_content = f"No specific content found for topic '{topic_query}' in book '{book_title}'. Please generate general questions about the topic."
                    
                return f"""BOOK CONTENT RETRIEVED:
                    
Book: {book_title}
Curriculum: {curriculum_name}
Topic: {topic_query}
Exam Parameters: {exam_parameters}

Content from "{book_title}":
{combined_content}

Please generate {exam_parameters.get('count', 10)} exam questions based specifically on this book content with:
- Difficulty levels: {', '.join(exam_parameters.get('difficulty', ['medium']))}
- Question types: {', '.join(exam_parameters.get('question_types', ['multiple_choice_single_answer']))}
- Time limit: {exam_parameters.get('time_limit', 30)} minutes total
- Scope: Focus specifically on "{book_title}" content"""
                    
            except Exception as e:
                logger.error(f"Error in book question tool: {e}")
                return f"Error retrieving book content: {str(e)}"
        
        return Tool(
            name="book_question_generator",
            description=f"Generate exam questions specifically from the book '{book_title}' within the '{curriculum_name}' curriculum. Input should be a topic or concept to focus on within this book.",
            func=generate_book_questions
        )

    def _create_topic_question_tool(self, book_title: str, curriculum_name: str, specific_topics: str, exam_parameters: Dict[str, Any]) -> Tool:
        """Create agent tool for generating questions on specific topics from a book"""
        
        def generate_topic_questions(search_query: str) -> str:
            try:
                import asyncio
                
                logger.info(f"🎯 TOPIC QUESTION TOOL: Generating questions for specific topics '{specific_topics}' in book '{book_title}'")
                logger.info(f"📋 Parameters: {exam_parameters}")
                
                # Use book-specific search with topic keywords
                search_query_enhanced = f"{specific_topics} {search_query}"
                
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        import concurrent.futures
                        with concurrent.futures.ThreadPoolExecutor() as executor:
                            future = executor.submit(asyncio.run, self._search_book_embeddings(curriculum_name, book_title, search_query_enhanced, k=8))
                            results = future.result()
                    else:
                        results = loop.run_until_complete(self._search_book_embeddings(curriculum_name, book_title, search_query_enhanced, k=8))
                except RuntimeError:
                    results = asyncio.run(self._search_book_embeddings(curriculum_name, book_title, search_query_enhanced, k=8))
                
                if results:
                    # Filter and prioritize results that match the specific topics
                    topic_keywords = [t.strip().lower() for t in specific_topics.split(',')]
                    scored_results = []
                    
                    for r in results:
                        content_lower = r.get('content', '').lower()
                        score = sum(1 for keyword in topic_keywords if keyword in content_lower)
                        scored_results.append((score, r))
                    
                    # Sort by relevance to topics
                    scored_results.sort(key=lambda x: x[0], reverse=True)
                    relevant_results = [r[1] for r in scored_results[:6]]
                    
                    content_chunks = [r['content'] for r in relevant_results]
                    combined_content = "\n\n".join(content_chunks)
                    
                    return f"""TOPIC-SPECIFIC CONTENT RETRIEVED:
                    
Book: {book_title}
Curriculum: {curriculum_name}
Specific Topics: {specific_topics}
Search Query: {search_query}
Exam Parameters: {exam_parameters}

Content related to specified topics:
{combined_content}

Please generate {exam_parameters.get('count', 10)} exam questions focused SPECIFICALLY on these topics: {specific_topics}
Requirements:
- Difficulty levels: {', '.join(exam_parameters.get('difficulty', ['medium']))}
- Question types: {', '.join(exam_parameters.get('question_types', ['multiple_choice_single_answer']))}
- Time limit: {exam_parameters.get('time_limit', 30)} minutes total
- Scope: Targeted assessment of the specified topics only"""
                else:
                    return f"No content found for topics '{specific_topics}' in book '{book_title}'. Please try broader search terms."
                    
            except Exception as e:
                logger.error(f"Error in topic question tool: {e}")
                return f"Error retrieving topic-specific content: {str(e)}"
        
        return Tool(
            name="topic_question_generator",
            description=f"Generate exam questions on specific topics '{specific_topics}' from the book '{book_title}'. Input should be related concepts or keywords to enhance topic coverage.",
            func=generate_topic_questions
        )

    async def _search_vector_table(self, table_name: str, query: str, k: int = 6) -> List[str]:
        """Search vector table directly using embeddings"""
        try:
            # Generate embedding for the query
            query_embedding = await self.embeddings.aembed_query(query)
            
            # Convert to PostgreSQL vector format
            embedding_str = '[' + ','.join(map(str, query_embedding)) + ']'
            
            # Connect to database and search
            import asyncpg
            conn = await asyncpg.connect(self.connection_string)
            
            try:
                # Check if table exists (case-insensitive)
                table_exists = await conn.fetchval("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE LOWER(table_name) = LOWER($1)
                    )
                """, table_name.lower())
                
                if not table_exists:
                    logger.error(f"Vector table '{table_name}' does not exist")
                    # Try to find the actual table name by looking for tables with embedding column
                    vector_tables = await conn.fetch("""
                        SELECT DISTINCT t.table_name
                        FROM information_schema.tables t
                        JOIN information_schema.columns c ON t.table_name = c.table_name
                        WHERE t.table_schema = 'public' 
                        AND c.column_name = 'embedding'
                        ORDER BY t.table_name
                    """)
                    
                    if vector_tables:
                        logger.info(f"Available vector tables: {[t['table_name'] for t in vector_tables]}")
                        
                        # Try to find a table that matches the book title pattern
                        # Look for tables that contain key words from the original book title
                        book_title = getattr(self, '_current_book_title', '')
                        if book_title:
                            # Try exact match with full title first
                            for table in vector_tables:
                                if table['table_name'].upper() == book_title.upper():
                                    logger.info(f"Found exact match: {table['table_name']}")
                                    table_name = table['table_name']
                                    break
                            else:
                                # Try partial matches
                                book_words = set(book_title.upper().split('_'))
                                best_match = None
                                best_score = 0
                                
                                for table in vector_tables:
                                    table_words = set(table['table_name'].upper().split('_'))
                                    common_words = book_words.intersection(table_words)
                                    score = len(common_words)
                                    
                                    if score > best_score:
                                        best_score = score
                                        best_match = table['table_name']
                                
                                if best_match and best_score > 0:
                                    logger.info(f"Using best match table: {best_match} (score: {best_score})")
                                    table_name = best_match
                                else:
                                    logger.error(f"No suitable vector table found for book: {book_title}")
                                    return []
                        else:
                            # If no book title context, use the first available vector table
                            table_name = vector_tables[0]['table_name']
                            logger.info(f"Using first available vector table: {table_name}")
                    else:
                        logger.error("No vector tables found in database")
                        return []
                
                # Perform vector similarity search with proper table name quoting
                rows = await conn.fetch(f"""
                    SELECT content, embedding <-> $1::vector as distance
                    FROM "{table_name.lower()}"
                    ORDER BY embedding <-> $1::vector
                    LIMIT $2
                """, embedding_str, k)
                
                # Extract content from results
                results = [row['content'] for row in rows if row['content']]
                logger.info(f"Retrieved {len(results)} chunks from table '{table_name}'")
                
                return results
                
            finally:
                await conn.close()
                
        except Exception as e:
            logger.error(f"Error in vector search for table '{table_name}': {e}")
            return []

    def _create_web_search_tool(self) -> Tool:
        """Create web search tool using Tavily"""
        def web_search(query: str) -> str:
            try:
                tavily_api_key = os.getenv("TAVILY_API_KEY")
                if not tavily_api_key:
                    return "Web search is not available - API key not configured."
                
                # Use synchronous httpx client
                import httpx
                with httpx.Client() as client:
                    response = client.post(
                        "https://api.tavily.com/search",
                        headers={
                            "Authorization": f"Bearer {tavily_api_key}",
                            "Content-Type": "application/json"
                        },
                        json={"query": query}
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        results = data.get('results', [])
                        
                        # Format results
                        formatted_results = []
                        for result in results[:3]:  # Top 3 results
                            formatted_results.append(f"Title: {result.get('title', 'N/A')}\nContent: {result.get('content', 'N/A')}")
                        
                        return "\n\n".join(formatted_results) if formatted_results else "No web search results found."
                    else:
                        return "Web search failed - API error."
                        
            except Exception as e:
                logger.error(f"Error in web search: {e}")
                return "Web search encountered an error."
        
        return Tool(
            name="web_search",
            description="Search the web for information when the internal knowledge base doesn't have the answer.",
            func=web_search
        )

    async def generate_questions(self, request: QuestionGenerationRequest) -> QuestionResponse:
        """Generate questions using AI agents for curriculum, book, or topic-specific exams"""
        try:
            logger.info(f"🎯 AGENT-BASED QUESTION GENERATION STARTED")
            logger.info(f"Request: curriculum_id={request.curriculum_id}, book={request.book_title}, scope={request.scope_type}")
            logger.info(f"Parameters: count={request.count}, difficulty={request.difficulty}, types={request.question_types}")
            logger.info(f"Topics: {request.specific_topics}, Time: {request.time_limit}min")
            
            # Prepare exam parameters
            exam_parameters = {
                'count': request.count or 10,
                'difficulty': request.difficulty or ['medium'],
                'question_types': request.question_types or ['multiple_choice_single_answer'],
                'time_limit': request.time_limit or 30,
                'user_message': request.user_message or '',
                'specific_topics': request.specific_topics or ''
            }
            
            # Case 1: Whole Curriculum Exam
            if request.scope_type == 'whole_curriculum' and request.curriculum_id:
                logger.info("🌟 CASE 1: Generating questions for WHOLE CURRICULUM")
                
                # Get curriculum information
                curriculum_info = await self.db.get_curriculum_by_id(int(request.curriculum_id))
                if not curriculum_info:
                    raise ValueError(f"Curriculum with ID {request.curriculum_id} not found")
                
                curriculum_name = curriculum_info['name']
                
                # Call agent-based curriculum question generation
                all_questions = await self._generate_questions_with_curriculum_agent(
                    curriculum_name, exam_parameters
                )
                
                logger.info(f"✅ Generated {len(all_questions)} questions for curriculum {curriculum_name}")
                
                return QuestionResponse(
                    chapter=f"{curriculum_name} Curriculum - Comprehensive Exam",
                    questions_generated=all_questions
                )
            
            # Case 2: Single Book Exam
            elif request.scope_type == 'whole_book' and request.book_title:
                logger.info("📚 CASE 2: Generating questions for SINGLE BOOK")
                
                # Get curriculum context for the book
                book_info = await self._get_book_curriculum_info(request.book_title)
                curriculum_name = book_info.get('curriculum_name') if book_info else 'IT Curriculum'
                
                # Call agent-based book question generation
                all_questions = await self._generate_questions_with_book_agent(
                    request.book_title, curriculum_name, exam_parameters
                )
                
                logger.info(f"✅ Generated {len(all_questions)} questions for book {request.book_title}")
                
                return QuestionResponse(
                    chapter=f"{request.book_title} - Comprehensive Book Exam",
                    questions_generated=all_questions
                )
            
            # Case 3: Specific Topics Exam
            elif request.scope_type == 'specific_topics' and request.specific_topics:
                logger.info("🎯 CASE 3: Generating questions for SPECIFIC TOPICS")
                
                # Get curriculum context for the book
                book_title = request.book_title or 'General Book'
                book_info = await self._get_book_curriculum_info(book_title)
                curriculum_name = book_info.get('curriculum_name') if book_info else 'IT Curriculum'
                
                # Call agent-based topic question generation
                all_questions = await self._generate_questions_with_topic_agent(
                    book_title, curriculum_name, request.specific_topics, exam_parameters
                )
                
                logger.info(f"✅ Generated {len(all_questions)} questions for topics: {request.specific_topics}")
                
                return QuestionResponse(
                    chapter=f"{book_title} - {request.specific_topics}",
                    questions_generated=all_questions
                )
            
            else:
                # Fallback: Default to book-based generation
                logger.info("🔄 FALLBACK: Using book-based generation")
                book_title = request.book_title or 'General Content'
                book_info = await self._get_book_curriculum_info(book_title)
                curriculum_name = book_info.get('curriculum_name') if book_info else 'IT Curriculum'
                
                all_questions = await self._generate_questions_with_book_agent(
                    book_title, curriculum_name, exam_parameters
                )
                
                return QuestionResponse(
                    chapter=f"{book_title} - General Exam",
                    questions_generated=all_questions
                )
            
        except Exception as e:
            logger.error(f"❌ Error in agent-based question generation: {e}")
            raise

    async def _extract_topics_from_book(self, book_title: str) -> List[str]:
        """Extract topics from book using vector search"""
        try:
            # Set the current book title for context in search
            self._current_book_title = book_title
            
            # Use the full book title as table name (no sanitization)
            table_name = book_title
            
            # Search for table of contents or main topics
            results = await self._search_vector_table(table_name, "table of contents main topics chapters", k=5)
            
            # Extract potential topics (this is a simplified approach)
            topics = ["Introduction", "Main Concepts", "Advanced Topics"]
            return topics
            
        except Exception as e:
            logger.error(f"Error extracting topics: {e}")
            return ["General Topics"]

    async def _generate_questions_with_curriculum_agent(self, curriculum_name: str, exam_parameters: Dict[str, Any]) -> List[Question]:
        """Generate questions using agent that searches entire curriculum"""
        try:
            logger.info(f"🌟 Creating curriculum agent for '{curriculum_name}'")
            
            # Create curriculum question generation tool
            curriculum_tool = self._create_curriculum_question_tool(curriculum_name, exam_parameters)
            tools = [curriculum_tool]
            
            # Create agent with curriculum-specific prompt
            current_llm = self.get_current_llm()
            agent = create_tool_calling_agent(current_llm, tools, self.curriculum_question_prompt)
            agent_executor = AgentExecutor(
                agent=agent,
                tools=tools,
                verbose=True,
                handle_parsing_errors=True,
                max_iterations=3,
                return_intermediate_steps=False
            )
            
            # Execute agent to generate questions
            logger.info("🚀 Executing curriculum question generation agent")
            
            # Create detailed instruction with all parameters
            difficulty_str = ", ".join(exam_parameters['difficulty']) if isinstance(exam_parameters['difficulty'], list) else exam_parameters['difficulty']
            types_str = ", ".join(exam_parameters['question_types']) if isinstance(exam_parameters['question_types'], list) else exam_parameters['question_types']
            
            detailed_instruction = f"""You must generate EXACTLY {exam_parameters['count']} exam questions for the {curriculum_name} curriculum.

MANDATORY REQUIREMENTS:
- Number of questions: EXACTLY {exam_parameters['count']} (no more, no less)
- Difficulty level(s): {difficulty_str} (use ONLY these difficulty levels)
- Question type(s): {types_str} (use ONLY these question types)
- Time limit: {exam_parameters['time_limit']} minutes total
- DO NOT mention any book names, guide titles, or document references in questions
- Keep all questions general and concept-focused

STEP 1: Call the curriculum_question_generator tool with topic "IT concepts programming databases networks" to retrieve curriculum content.
STEP 2: Generate the required questions based on the retrieved content.
STEP 3: Return the questions in the exact JSON format.

Start by calling the curriculum_question_generator tool now."""

            result = await agent_executor.ainvoke({
                "input": detailed_instruction
            })
            
            # Parse the result
            return await self._parse_agent_questions_result(result['output'], exam_parameters)
            
        except Exception as e:
            logger.error(f"❌ Error in curriculum agent: {e}")
            # Fallback to direct generation
            return await self._generate_questions_for_curriculum(curriculum_name, "comprehensive curriculum", exam_parameters)

    async def _generate_questions_with_book_agent(self, book_title: str, curriculum_name: str, exam_parameters: Dict[str, Any]) -> List[Question]:
        """Generate questions using agent that searches specific book in curriculum"""
        try:
            logger.info(f"📚 Creating book agent for '{book_title}' in curriculum '{curriculum_name}'")
            
            # Create book question generation tool
            book_tool = self._create_book_question_tool(book_title, curriculum_name, exam_parameters)
            tools = [book_tool]
            
            # Create agent with book-specific prompt
            current_llm = self.get_current_llm()
            agent = create_tool_calling_agent(current_llm, tools, self.book_question_prompt)
            agent_executor = AgentExecutor(
                agent=agent,
                tools=tools,
                verbose=True,
                handle_parsing_errors=True,
                max_iterations=3,
                return_intermediate_steps=False
            )
            
            # Execute agent to generate questions
            logger.info("🚀 Executing book question generation agent")
            logger.info(f"📋 Agent will use book_question_generator tool to search for content from '{book_title}'")
            
            # Create detailed instruction with all parameters
            difficulty_str = ", ".join(exam_parameters['difficulty']) if isinstance(exam_parameters['difficulty'], list) else exam_parameters['difficulty']
            types_str = ", ".join(exam_parameters['question_types']) if isinstance(exam_parameters['question_types'], list) else exam_parameters['question_types']
            
            detailed_instruction = f"""You must generate EXACTLY {exam_parameters['count']} exam questions from the book content.

MANDATORY REQUIREMENTS:
- Number of questions: EXACTLY {exam_parameters['count']} (no more, no less)
- Difficulty level(s): {difficulty_str} (use ONLY these difficulty levels)
- Question type(s): {types_str} (use ONLY these question types)
- Time limit: {exam_parameters['time_limit']} minutes total
- Focus on: {book_title} content within {curriculum_name} curriculum
- DO NOT mention the book name '{book_title}' or any guide titles in questions
- Keep all questions general and concept-focused

STEP 1: Call the book_question_generator tool with topic "data lakehouse architecture configuration storage" to retrieve book content.
STEP 2: Generate the required questions based on the retrieved content.
STEP 3: Return the questions in the exact JSON format.

Start by calling the book_question_generator tool now."""

            result = await agent_executor.ainvoke({
                "input": detailed_instruction
            })
            
            # Parse the result
            return await self._parse_agent_questions_result(result['output'], exam_parameters)
            
        except Exception as e:
            logger.error(f"❌ Error in book agent: {e}")
            # Fallback to direct generation
            return await self._generate_questions_for_topic(book_title, "comprehensive book content", exam_parameters)

    async def _generate_questions_with_topic_agent(self, book_title: str, curriculum_name: str, specific_topics: str, exam_parameters: Dict[str, Any]) -> List[Question]:
        """Generate questions using agent that searches specific topics in book"""
        try:
            logger.info(f"🎯 Creating topic agent for topics '{specific_topics}' in book '{book_title}'")
            
            # Create topic question generation tool
            topic_tool = self._create_topic_question_tool(book_title, curriculum_name, specific_topics, exam_parameters)
            tools = [topic_tool]
            
            # Create agent with topic-specific prompt
            current_llm = self.get_current_llm()
            try:
                agent = create_tool_calling_agent(current_llm, tools, self.topic_question_prompt)
                agent_executor = AgentExecutor(
                    agent=agent,
                    tools=tools,
                    verbose=True,
                    handle_parsing_errors=True,
                    max_iterations=3,
                    return_intermediate_steps=False
                )
            except Exception as e:
                logger.error(f"❌ Error creating topic agent: {e}")
                raise
            
            # Execute agent to generate questions
            logger.info("🚀 Executing topic question generation agent")
            
            # Create detailed instruction with all parameters
            difficulty_str = ", ".join(exam_parameters['difficulty']) if isinstance(exam_parameters['difficulty'], list) else exam_parameters['difficulty']
            types_str = ", ".join(exam_parameters['question_types']) if isinstance(exam_parameters['question_types'], list) else exam_parameters['question_types']
            
            detailed_instruction = f"""You must generate EXACTLY {exam_parameters['count']} exam questions on the specific topics.

MANDATORY REQUIREMENTS:
- Number of questions: EXACTLY {exam_parameters['count']} (no more, no less)  
- Difficulty level(s): {difficulty_str} (use ONLY these difficulty levels)
- Question type(s): {types_str} (use ONLY these question types)
- Time limit: {exam_parameters['time_limit']} minutes total
- Focus on topics: {specific_topics}
- Context: From book '{book_title}' in {curriculum_name} curriculum
- DO NOT mention the book name '{book_title}' or any guide titles in questions
- Keep all questions general and concept-focused

STEP 1: Call the topic_question_generator tool with topic "{specific_topics}" to retrieve relevant content.
STEP 2: Generate the required questions based on the retrieved content.
STEP 3: Return the questions in the exact JSON format.

Start by calling the topic_question_generator tool now."""

            result = await agent_executor.ainvoke({
                "input": detailed_instruction
            })
            
            # Parse the result
            return await self._parse_agent_questions_result(result['output'], exam_parameters)
            
        except Exception as e:
            logger.error(f"❌ Error in topic agent: {e}")
            # Fallback to direct generation
            exam_parameters['specific_topics'] = specific_topics
            return await self._generate_questions_for_topic(book_title, specific_topics, exam_parameters)

    async def _parse_agent_questions_result(self, agent_output: str, exam_parameters: Dict[str, Any]) -> List[Question]:
        """Parse agent output and convert to Question objects"""
        try:
            logger.info(f"🔍 Parsing agent output: {agent_output[:500]}...")
            logger.info(f"🔍 Full agent output length: {len(agent_output)} characters")
            
            # Log the complete output if it's short (likely empty or error)
            if len(agent_output) < 100:
                logger.warning(f"⚠️ Agent output is very short: '{agent_output}'")
            
            # Clean the output to extract JSON
            cleaned_output = agent_output.strip()
            if '```json' in cleaned_output:
                start = cleaned_output.find('```json') + 7
                end = cleaned_output.find('```', start)
                if end != -1:
                    cleaned_output = cleaned_output[start:end].strip()
            elif '[' in cleaned_output and ']' in cleaned_output:
                start = cleaned_output.find('[')
                end = cleaned_output.rfind(']') + 1
                cleaned_output = cleaned_output[start:end]
            
            # Parse JSON
            questions_data = json.loads(cleaned_output)
            if not isinstance(questions_data, list):
                raise ValueError("Agent output is not a list of questions")
            
            # Convert to Question objects
            questions = []
            for q_data in questions_data:
                # Ensure answer is string
                answer_value = q_data.get('answer', '')
                if isinstance(answer_value, bool):
                    answer_str = str(answer_value)
                else:
                    answer_str = str(answer_value) if answer_value is not None else ''
                
                question = Question(
                    difficulty=q_data.get('difficulty', 'medium'),
                    type=q_data.get('type', 'multiple_choice_single_answer'),
                    question_text=q_data.get('question_text', ''),
                    options=q_data.get('options', []),
                    answer=answer_str
                )
                questions.append(question)
            
            # Apply professional exam enhancements
            enhanced_questions = await self._enhance_questions_professionally(questions, exam_parameters)
            
            logger.info(f"✅ Successfully parsed and enhanced {len(enhanced_questions)} questions from agent output")
            return enhanced_questions
            
        except Exception as e:
            logger.error(f"❌ Error parsing agent output: {e}")
            logger.error(f"Raw output: {agent_output}")
            return []

    async def _enhance_questions_professionally(self, questions: List[Question], exam_parameters: Dict[str, Any]) -> List[Question]:
        """Apply professional exam enhancements and quality assurance"""
        try:
            logger.info(f"🎓 Applying professional exam enhancements to {len(questions)} questions")
            
            enhanced_questions = []
            
            # Quality metrics
            difficulty_distribution = {}
            question_type_distribution = {}
            time_per_question = exam_parameters.get('time_limit', 30) / len(questions) if questions else 0
            
            for i, question in enumerate(questions):
                # Validate and enhance each question
                enhanced_question = await self._validate_and_enhance_question(question, i + 1, time_per_question)
                
                if enhanced_question:
                    enhanced_questions.append(enhanced_question)
                    
                    # Track distributions for quality analysis
                    difficulty = enhanced_question.difficulty
                    question_type = enhanced_question.type
                    
                    difficulty_distribution[difficulty] = difficulty_distribution.get(difficulty, 0) + 1
                    question_type_distribution[question_type] = question_type_distribution.get(question_type, 0) + 1
            
            # Log quality metrics
            logger.info(f"📊 EXAM QUALITY METRICS:")
            logger.info(f"   Questions Generated: {len(enhanced_questions)}")
            logger.info(f"   Time per Question: {time_per_question:.1f} minutes")
            logger.info(f"   Difficulty Distribution: {difficulty_distribution}")
            logger.info(f"   Question Type Distribution: {question_type_distribution}")
            
            # Apply professional quality checks
            enhanced_questions = await self._apply_quality_checks(enhanced_questions, exam_parameters)
            
            return enhanced_questions
            
        except Exception as e:
            logger.error(f"❌ Error in professional enhancement: {e}")
            return questions  # Return original questions if enhancement fails

    async def _validate_and_enhance_question(self, question: Question, question_number: int, time_per_question: float) -> Optional[Question]:
        """Validate and enhance individual question quality"""
        try:
            # Basic validation
            if not question.question_text or not question.question_text.strip():
                logger.warning(f"⚠️ Question {question_number}: Empty question text")
                return None
            
            # Enhance question text clarity and remove book references
            enhanced_text = question.question_text.strip()
            
            # Remove book name references and guide titles
            enhanced_text = self._remove_book_references(enhanced_text)
            
            if not enhanced_text.endswith('?') and question.type != 'true_false':
                if question.type == 'multiple_choice_single_answer':
                    enhanced_text += "?"
                elif question.type == 'open_ended_question':
                    enhanced_text += "?"
            
            # Validate multiple choice options
            if question.type == 'multiple_choice_single_answer':
                if not question.options or len(question.options) < 4:
                    logger.warning(f"⚠️ Question {question_number}: Insufficient options for multiple choice")
                    return None
                
                # Ensure answer matches one of the options
                if question.answer not in question.options:
                    logger.warning(f"⚠️ Question {question_number}: Answer not found in options")
                    return None
            
            # Validate true/false questions
            if question.type == 'true_false':
                if question.answer.lower() not in ['true', 'false']:
                    logger.warning(f"⚠️ Question {question_number}: Invalid true/false answer")
                    return None
                
                # Ensure proper true/false formatting
                question.answer = question.answer.capitalize()
                question.options = []  # True/false should have no options
            
            # Optimize for time constraints
            if time_per_question < 1:  # Very fast exam
                if question.type == 'open_ended_question':
                    # Convert to multiple choice for speed
                    logger.info(f"🚀 Converting open-ended question {question_number} to multiple choice for time optimization")
                    question.type = 'multiple_choice_single_answer'
                    if not question.options:
                        question.options = [question.answer, "Alternative A", "Alternative B", "Alternative C"]
            
            # Create enhanced question
            enhanced_question = Question(
                difficulty=question.difficulty,
                type=question.type,
                question_text=enhanced_text,
                options=question.options,
                answer=question.answer
            )
            
            return enhanced_question
            
        except Exception as e:
            logger.error(f"❌ Error validating question {question_number}: {e}")
            return question

    async def _apply_quality_checks(self, questions: List[Question], exam_parameters: Dict[str, Any]) -> List[Question]:
        """Apply final quality checks and optimizations"""
        try:
            logger.info("🔍 Applying final quality checks")
            
            # Check difficulty distribution
            requested_difficulties = exam_parameters.get('difficulty', ['medium'])
            difficulty_counts = {}
            
            for question in questions:
                difficulty_counts[question.difficulty] = difficulty_counts.get(question.difficulty, 0) + 1
            
            # Ensure we have questions of requested difficulties
            missing_difficulties = [d for d in requested_difficulties if difficulty_counts.get(d, 0) == 0]
            if missing_difficulties:
                logger.warning(f"⚠️ Missing requested difficulties: {missing_difficulties}")
            
            # Check question type distribution
            requested_types = exam_parameters.get('question_types', ['multiple_choice_single_answer'])
            type_counts = {}
            
            for question in questions:
                type_counts[question.type] = type_counts.get(question.type, 0) + 1
            
            # Ensure we have questions of requested types
            missing_types = [t for t in requested_types if type_counts.get(t, 0) == 0]
            if missing_types:
                logger.warning(f"⚠️ Missing requested question types: {missing_types}")
            
            # Professional exam scoring
            total_time = exam_parameters.get('time_limit', 30)
            total_questions = len(questions)
            
            logger.info(f"✅ PROFESSIONAL EXAM ANALYSIS:")
            logger.info(f"   📝 Total Questions: {total_questions}")
            logger.info(f"   ⏱️ Total Time: {total_time} minutes")
            logger.info(f"   🎯 Average Time per Question: {total_time/total_questions:.1f} minutes")
            logger.info(f"   📊 Difficulty Spread: {difficulty_counts}")
            logger.info(f"   🔧 Question Types: {type_counts}")
            
            # Professional recommendations
            if total_time / total_questions < 0.5:
                logger.info("💡 RECOMMENDATION: Very fast-paced exam - consider reducing complexity")
            elif total_time / total_questions > 5:
                logger.info("💡 RECOMMENDATION: Generous time allocation - suitable for in-depth analysis")
            
            return questions
            
        except Exception as e:
            logger.error(f"❌ Error in quality checks: {e}")
            return questions

    async def _generate_exam_analytics(self, questions: List[Question], exam_parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Generate comprehensive exam analytics for professional reporting"""
        try:
            logger.info("📊 Generating comprehensive exam analytics")
            
            # Basic metrics
            total_questions = len(questions)
            total_time = exam_parameters.get('time_limit', 30)
            
            # Difficulty analysis
            difficulty_breakdown = {}
            for question in questions:
                difficulty_breakdown[question.difficulty] = difficulty_breakdown.get(question.difficulty, 0) + 1
            
            # Question type analysis
            type_breakdown = {}
            for question in questions:
                type_breakdown[question.type] = type_breakdown.get(question.type, 0) + 1
            
            # Time optimization analysis
            avg_time_per_question = total_time / total_questions if total_questions > 0 else 0
            
            # Professional scoring metrics
            complexity_score = self._calculate_complexity_score(questions)
            balance_score = self._calculate_balance_score(difficulty_breakdown, type_breakdown)
            
            # Create comprehensive analytics
            analytics = {
                "exam_overview": {
                    "total_questions": total_questions,
                    "total_time_minutes": total_time,
                    "average_time_per_question": round(avg_time_per_question, 2),
                    "complexity_score": complexity_score,
                    "balance_score": balance_score
                },
                "difficulty_analysis": {
                    "breakdown": difficulty_breakdown,
                    "percentages": {
                        level: round((count / total_questions) * 100, 1) 
                        for level, count in difficulty_breakdown.items()
                    } if total_questions > 0 else {}
                },
                "question_type_analysis": {
                    "breakdown": type_breakdown,
                    "percentages": {
                        q_type: round((count / total_questions) * 100, 1) 
                        for q_type, count in type_breakdown.items()
                    } if total_questions > 0 else {}
                },
                "professional_recommendations": self._generate_professional_recommendations(
                    questions, exam_parameters, complexity_score, balance_score
                ),
                "quality_indicators": {
                    "has_varied_difficulty": len(difficulty_breakdown) > 1,
                    "has_varied_types": len(type_breakdown) > 1,
                    "appropriate_time_allocation": 0.5 <= avg_time_per_question <= 5,
                    "sufficient_questions": total_questions >= 5,
                    "professional_standard": complexity_score >= 7 and balance_score >= 8
                }
            }
            
            logger.info(f"✅ Generated comprehensive analytics with {len(analytics)} key metrics")
            return analytics
            
        except Exception as e:
            logger.error(f"❌ Error generating exam analytics: {e}")
            return {"error": str(e)}

    def _calculate_complexity_score(self, questions: List[Question]) -> float:
        """Calculate exam complexity score (1-10 scale)"""
        try:
            if not questions:
                return 0.0
            
            # Base score
            score = 5.0
            
            # Difficulty distribution bonus
            difficulty_counts = {}
            for question in questions:
                difficulty_counts[question.difficulty] = difficulty_counts.get(question.difficulty, 0) + 1
            
            # Bonus for varied difficulty
            if len(difficulty_counts) > 1:
                score += 1.0
            
            # Bonus for hard questions
            hard_percentage = difficulty_counts.get('hard', 0) / len(questions)
            score += hard_percentage * 2
            
            # Question type complexity bonus
            type_counts = {}
            for question in questions:
                type_counts[question.type] = type_counts.get(question.type, 0) + 1
            
            # Open-ended questions increase complexity
            open_ended_percentage = type_counts.get('open_ended_question', 0) / len(questions)
            score += open_ended_percentage * 1.5
            
            # Variety bonus
            if len(type_counts) > 2:
                score += 0.5
            
            return min(10.0, max(1.0, round(score, 1)))
            
        except Exception as e:
            logger.error(f"❌ Error calculating complexity score: {e}")
            return 5.0

    def _calculate_balance_score(self, difficulty_breakdown: Dict[str, int], type_breakdown: Dict[str, int]) -> float:
        """Calculate exam balance score (1-10 scale)"""
        try:
            score = 5.0
            total_questions = sum(difficulty_breakdown.values())
            
            if total_questions == 0:
                return 0.0
            
            # Difficulty balance analysis
            diff_percentages = {level: count/total_questions for level, count in difficulty_breakdown.items()}
            
            # Ideal distribution: some easy (20-40%), medium (40-60%), hard (10-30%)
            ideal_ranges = {
                'easy': (0.2, 0.4),
                'medium': (0.4, 0.6),
                'hard': (0.1, 0.3)
            }
            
            # Check balance
            balance_points = 0
            for level, (min_pct, max_pct) in ideal_ranges.items():
                actual_pct = diff_percentages.get(level, 0)
                if min_pct <= actual_pct <= max_pct:
                    balance_points += 2
                elif actual_pct > 0:  # Has some questions of this type
                    balance_points += 1
            
            score += balance_points
            
            # Type variety bonus
            if len(type_breakdown) >= 2:
                score += 1
            if len(type_breakdown) >= 3:
                score += 0.5
            
            return min(10.0, max(1.0, round(score, 1)))
            
        except Exception as e:
            logger.error(f"❌ Error calculating balance score: {e}")
            return 5.0

    def _generate_professional_recommendations(self, questions: List[Question], exam_parameters: Dict[str, Any], 
                                             complexity_score: float, balance_score: float) -> List[str]:
        """Generate professional recommendations for exam improvement"""
        recommendations = []
        
        try:
            total_time = exam_parameters.get('time_limit', 30)
            avg_time = total_time / len(questions) if questions else 0
            
            # Time recommendations
            if avg_time < 0.5:
                recommendations.append("⚡ Consider increasing time limit - questions may feel rushed")
            elif avg_time > 5:
                recommendations.append("🕐 Time allocation is generous - suitable for complex analysis")
            
            # Complexity recommendations
            if complexity_score < 5:
                recommendations.append("📈 Consider adding more challenging questions to increase engagement")
            elif complexity_score > 8:
                recommendations.append("⚖️ High complexity exam - ensure students are well-prepared")
            
            # Balance recommendations
            if balance_score < 6:
                recommendations.append("🎯 Improve question balance - vary difficulty levels and types")
            elif balance_score > 8:
                recommendations.append("✨ Excellent question balance across difficulties and types")
            
            # Difficulty distribution analysis
            difficulty_counts = {}
            for question in questions:
                difficulty_counts[question.difficulty] = difficulty_counts.get(question.difficulty, 0) + 1
            
            total = len(questions)
            easy_pct = (difficulty_counts.get('easy', 0) / total) * 100
            hard_pct = (difficulty_counts.get('hard', 0) / total) * 100
            
            if easy_pct > 60:
                recommendations.append("🎓 Many easy questions - suitable for introductory assessment")
            if hard_pct > 40:
                recommendations.append("🔥 High proportion of difficult questions - advanced level exam")
            
            # Question type recommendations
            type_counts = {}
            for question in questions:
                type_counts[question.type] = type_counts.get(question.type, 0) + 1
            
            if len(type_counts) == 1:
                recommendations.append("🔄 Consider adding variety with different question types")
            
            # Professional quality indicators
            if complexity_score >= 7 and balance_score >= 8:
                recommendations.append("🏆 Professional-grade exam meeting educational standards")
            
            return recommendations
            
        except Exception as e:
            logger.error(f"❌ Error generating recommendations: {e}")
            return ["Error generating recommendations"]

    def _create_professional_summary(self, questions: List[Question], exam_parameters: Dict[str, Any], 
                                   analytics: Dict[str, Any]) -> Dict[str, Any]:
        """Create professional exam summary for educators"""
        try:
            return {
                "executive_summary": {
                    "exam_title": f"Professional {exam_parameters.get('scope_type', 'Curriculum')} Assessment",
                    "total_questions": len(questions),
                    "estimated_duration": f"{exam_parameters.get('time_limit', 30)} minutes",
                    "target_audience": "Students and professionals",
                    "assessment_level": self._determine_assessment_level(analytics.get('exam_overview', {}).get('complexity_score', 5))
                },
                "quality_metrics": {
                    "complexity_rating": analytics.get('exam_overview', {}).get('complexity_score', 5),
                    "balance_rating": analytics.get('exam_overview', {}).get('balance_score', 5),
                    "professional_standard_met": analytics.get('quality_indicators', {}).get('professional_standard', False)
                },
                "instructor_notes": {
                    "preparation_time": "Review curriculum materials thoroughly",
                    "recommended_resources": "Access to course materials and references",
                    "grading_guidelines": "Consider partial credit for complex questions",
                    "accommodation_suggestions": "Additional time for accessibility needs"
                },
                "performance_expectations": {
                    "passing_threshold": "70% for basic competency",
                    "excellence_threshold": "85% for advanced proficiency",
                    "time_management": f"Average {analytics.get('exam_overview', {}).get('average_time_per_question', 0):.1f} minutes per question"
                }
            }
            
        except Exception as e:
            logger.error(f"❌ Error creating professional summary: {e}")
            return {"error": "Could not generate professional summary"}

    def _determine_assessment_level(self, complexity_score: float) -> str:
        """Determine assessment level based on complexity"""
        if complexity_score >= 8:
            return "Advanced/Professional"
        elif complexity_score >= 6:
            return "Intermediate"
        elif complexity_score >= 4:
            return "Basic/Introductory"
        else:
            return "Foundational"

    def _remove_book_references(self, question_text: str) -> str:
        """Remove book name references and guide titles from question text"""
        try:
            import re
            
            # Common patterns to remove
            patterns_to_remove = [
                # Book/guide references
                r'(?:according to|as described in|referencing|detailed in|from|in)\s+(?:the\s+)?[A-Z_][A-Z0-9_]*(?:\s+[A-Z_][A-Z0-9_]*)*(?:\s+GUIDE?|HANDBOOK|MANUAL|BOOK)?[,\s]*',
                r'(?:according to|as described in|referencing|detailed in|from|in)\s+(?:the\s+)?\"[^\"]+\"[,\s]*',
                r'(?:according to|as described in|referencing|detailed in|from|in)\s+(?:the\s+)?\'[^\']+\'[,\s]*',
                
                # Specific guide patterns
                r'[,\s]*referencing considerations detailed in[^,.?]*[,\s]*',
                r'[,\s]*as outlined in[^,.?]*[,\s]*',
                r'[,\s]*mentioned in[^,.?]*[,\s]*',
                r'[,\s]*described in[^,.?]*[,\s]*',
                
                # Clean up extra spaces and punctuation
                r'\s+', # Multiple spaces
                r'^[,\s]+|[,\s]+$', # Leading/trailing commas and spaces
                r'[,\s]*\?+$', # Multiple question marks
            ]
            
            cleaned_text = question_text
            
            # Apply all patterns
            for pattern in patterns_to_remove[:-3]:  # Don't apply cleanup patterns yet
                cleaned_text = re.sub(pattern, '', cleaned_text, flags=re.IGNORECASE)
            
            # Apply cleanup patterns
            cleaned_text = re.sub(r'\s+', ' ', cleaned_text)  # Multiple spaces to single
            cleaned_text = re.sub(r'^[,\s]+|[,\s]+$', '', cleaned_text)  # Leading/trailing
            cleaned_text = re.sub(r'\?+$', '?', cleaned_text)  # Multiple question marks
            
            # Ensure proper capitalization
            if cleaned_text and not cleaned_text[0].isupper():
                cleaned_text = cleaned_text[0].upper() + cleaned_text[1:]
            
            # Log if changes were made
            if cleaned_text != question_text:
                logger.info(f"📝 Cleaned question text: '{question_text[:50]}...' → '{cleaned_text[:50]}...'")
            
            return cleaned_text.strip()
            
        except Exception as e:
            logger.error(f"❌ Error cleaning question text: {e}")
            return question_text

    async def _generate_questions_for_curriculum(self, curriculum_name: str, topic: str, parameters: Dict[str, Any]) -> List[Question]:
        """Generate questions for an entire curriculum"""
        try:
            # Search for content across the entire curriculum
            logger.info(f"Searching curriculum '{curriculum_name}' for question generation with topic: {topic}")
            
            # Use broader search queries to get diverse content from curriculum
            search_queries = [
                "introduction overview concepts",
                "advanced topics techniques methods",
                "practical applications examples",
                "key principles fundamentals",
                topic  # Include the specific topic as well
            ]
            
            all_content = []
            for query in search_queries:
                results = await self._search_curriculum_embeddings(curriculum_name, query, k=4)
                if results:
                    all_content.extend([r['content'] for r in results])
            
            # Remove duplicates and combine content
            unique_content = list(set(all_content))
            content = "\n\n".join(unique_content[:15])  # Limit to prevent context overflow
            
            if not content:
                logger.warning(f"No content found for curriculum '{curriculum_name}'")
                return []
            
            # Extract parameters for comprehensive exam generation
            count = parameters.get('count', 2)
            difficulty_levels = parameters.get('difficulty', ['medium'])
            question_types = parameters.get('question_types', ['multiple_choice_single_answer'])
            user_message = parameters.get('user_message', '')
            
            # Create dynamic difficulty and type constraints
            difficulty_constraint = f"Focus on {', '.join(difficulty_levels)} difficulty levels"
            type_constraint = f"Generate only these question types: {', '.join(question_types)}"
            
            # Enhanced question generation prompt for curriculum-wide exams
            question_prompt = ChatPromptTemplate.from_messages([
                ("system", f"""You are a professional exam author and educational assessment specialist. Generate high-quality technical exam questions based STRICTLY on the provided content from the {curriculum_name} curriculum.

CURRICULUM EXAM SPECIFICATIONS:
- {difficulty_constraint}
- {type_constraint}
- Generate exactly {count} questions
- Cover diverse topics from across the curriculum
- User Request: "{user_message}"

DISTRIBUTION GUIDELINES:
- Distribute questions evenly across different subject areas in the curriculum
- Ensure questions cover various books/materials in the curriculum
- If multiple question types specified, vary the types throughout
- Make questions comprehensive and representative of the entire curriculum

CRITICAL CONTENT FOCUS REQUIREMENTS:
- ONLY create questions about TECHNICAL CONTENT, concepts, theories, procedures, and subject matter
- Write questions as if they are from a professional certification exam covering the entire curriculum
- Questions must be direct, clear, and professional without any meta-references

STRICTLY FORBIDDEN QUESTION ELEMENTS:
- DO NOT mention chapters, sections, or book structure ("Chapter 2", "Section 1.3", etc.)
- DO NOT use phrases like "According to the text", "Based on the provided text", "The book states", "As described in the book"
- DO NOT ask about book organization, preface, introduction, or meta-information
- DO NOT ask "What does the book teach" or "What does the book aim to"
- DO NOT reference the source material in questions

REQUIRED QUESTION STYLE:
- Write questions in direct, technical language
- Ask about concepts, processes, tools, and techniques directly
- Use professional terminology appropriate for the field
- Questions should sound like they come from industry certification exams covering multiple subject areas

Your response MUST be a JSON array of question objects. Each question object must have:
- "difficulty": one of "easy", "medium", or "hard" (matching the specified levels)
- "type": one of "multiple_choice_single_answer", "true_false", or "open_ended_question" (matching specified types)
- "question_text": The full text of the question (clear, specific, and exam-appropriate)
- "options": Array of 4 choices for multiple choice, empty array for others
- "answer": The correct answer as a STRING (for true/false use "True" or "False", for multiple choice use the exact option text)

CURRICULUM EXAM QUALITY STANDARDS:
- Easy questions: Test basic recall of technical definitions and concepts from across the curriculum
- Medium questions: Test application of concepts and analysis of scenarios from multiple subject areas
- Hard questions: Test evaluation, synthesis, and critical thinking across curriculum domains
- Multiple choice: Provide 4 plausible technical options with clear distinctions, only one correct answer
- True/False: Create statements about technical facts that are unambiguously true or false
- Open-ended: Ask for explanations that demonstrate understanding across curriculum topics

CRITICAL REQUIREMENTS:
- The "answer" field must ALWAYS be a string
- Base questions on technical concepts from the curriculum content
- Make questions appropriate for comprehensive curriculum assessment
- Ensure clear, unambiguous wording
- Questions must test actual technical understanding across multiple subject areas
- NO meta-references to source material whatsoever"""),
                ("human", "Curriculum Content: {content}\nTopic: {topic}\nGenerate {count} professional technical exam questions covering the breadth of the curriculum. Write each question as if it appears on a comprehensive certification exam covering multiple subject areas.")
            ])
            
            chain = question_prompt | self.get_current_llm() | StrOutputParser()
            
            logger.info(f"Invoking AI chain for curriculum: {curriculum_name} using {'Ollama' if self.use_fallback else 'Google Gemini'}")
            
            try:
                result = await chain.ainvoke({
                    "content": content,
                    "topic": topic,
                    "count": count,
                    "difficulty_constraint": difficulty_constraint,
                    "type_constraint": type_constraint
                })
            except Exception as e:
                error_str = str(e).lower()
                # Check if this is a quota exceeded error
                if "quota" in error_str or "429" in error_str or "rate limit" in error_str:
                    logger.warning(f"Google Gemini quota exceeded: {e}")
                    if not self.use_fallback:
                        self.switch_to_fallback()
                        # Retry with fallback LLM
                        chain = question_prompt | self.get_current_llm() | StrOutputParser()
                        logger.info(f"Retrying with Ollama fallback for curriculum: {curriculum_name}")
                        result = await chain.ainvoke({
                            "content": content,
                            "topic": topic,
                            "count": count,
                            "difficulty_constraint": difficulty_constraint,
                            "type_constraint": type_constraint
                        })
                    else:
                        raise e
                else:
                    raise e
            
            logger.info(f"Raw AI response for curriculum {curriculum_name}: {result[:500]}...")
            
            # Parse questions
            try:
                # Clean the response
                cleaned_result = result.strip()
                if cleaned_result.startswith('```json'):
                    cleaned_result = cleaned_result.replace('```json\n', '').replace('\n```', '')
                elif cleaned_result.startswith('```'):
                    cleaned_result = cleaned_result.replace('```\n', '').replace('\n```', '')
                
                logger.info(f"Cleaned response for parsing: {cleaned_result[:300]}...")
                questions_data = json.loads(cleaned_result)
                logger.info(f"Successfully parsed {len(questions_data)} questions for curriculum: {curriculum_name}")
            except json.JSONDecodeError as e:
                logger.error(f"JSON parsing error for curriculum {curriculum_name}: {e}")
                logger.error(f"Raw response: {result}")
                return []
            except Exception as e:
                logger.error(f"Unexpected error parsing response for curriculum {curriculum_name}: {e}")
                return []
            
            questions = []
            for q_data in questions_data:
                # Convert answer to string to handle boolean values from LLM
                answer_value = q_data.get('answer', '')
                if isinstance(answer_value, bool):
                    answer_str = str(answer_value)
                else:
                    answer_str = str(answer_value) if answer_value is not None else ''
                
                question = Question(
                    difficulty=q_data.get('difficulty', 'medium'),
                    type=q_data.get('type', 'multiple_choice_single_answer'),
                    question_text=q_data.get('question_text', ''),
                    options=q_data.get('options', []),
                    answer=answer_str
                )
                questions.append(question)
            
            return questions
            
        except Exception as e:
            logger.error(f"Error generating questions for curriculum {curriculum_name}: {e}")
            return []

    async def _generate_questions_for_topic(self, book_title: str, topic: str, parameters: Dict[str, Any]) -> List[Question]:
        """Generate questions for a specific topic"""
        try:
            logger.info(f"🔄 Using fallback method for book '{book_title}' topic '{topic}'")
            
            # Use curriculum embedding search instead of individual book tables
            try:
                # Use IT curriculum as default since most content is in IT curriculum
                curriculum_name = "IT"
                
                if book_title and book_title != "General Content":
                    # Use book-specific search
                    search_results = await self._search_book_embeddings(curriculum_name, book_title, topic, k=8)
                    content_chunks = [r['content'] for r in search_results] if search_results else []
                else:
                    # Use general curriculum search
                    search_results = await self._search_curriculum_embeddings(curriculum_name, topic, k=8)
                    content_chunks = [r['content'] for r in search_results] if search_results else []
                    
                content = "\n\n".join(content_chunks) if content_chunks else f"General content about {topic}"
                logger.info(f"✅ Fallback method retrieved {len(content_chunks)} content chunks")
            except Exception as e:
                logger.error(f"❌ Error in fallback search: {e}")
                content = f"General content about {topic}"
            
            # Extract parameters for comprehensive exam generation
            count = parameters.get('count', 2)
            difficulty_levels = parameters.get('difficulty', ['medium'])
            question_types = parameters.get('question_types', ['multiple_choice_single_answer'])
            scope_type = parameters.get('scope_type', 'whole_book')
            specific_topics = parameters.get('specific_topics', '')
            time_limit = parameters.get('time_limit', 30)
            user_message = parameters.get('user_message', '')
            
            # Create dynamic difficulty and type constraints
            difficulty_constraint = f"Focus on {', '.join(difficulty_levels)} difficulty levels"
            type_constraint = f"Generate only these question types: {', '.join(question_types)}"
            
            # Create scope-specific instruction
            scope_instruction = ""
            if scope_type == 'specific_topics' and specific_topics:
                scope_instruction = f"Focus SPECIFICALLY on these topics: {specific_topics}. "
            else:
                scope_instruction = "Cover comprehensive content from the book. "
            
            # Create time-based instruction
            time_instruction = ""
            if time_limit:
                time_per_question = time_limit / count if count > 0 else 2
                if time_per_question < 1:
                    time_instruction = "Create quick, focused questions suitable for rapid assessment. "
                elif time_per_question > 5:
                    time_instruction = "Create in-depth questions that require thorough analysis. "
                else:
                    time_instruction = f"Create questions appropriate for {time_per_question:.1f} minutes per question. "
            
            # Enhanced question generation prompt for comprehensive exams
            question_prompt = ChatPromptTemplate.from_messages([
                ("system", f"""You are a professional exam author and educational assessment specialist. Generate high-quality technical exam questions based STRICTLY on the provided content.

COMPREHENSIVE EXAM SPECIFICATIONS:
- {difficulty_constraint}
- {type_constraint}
- Generate exactly {count} questions
- {scope_instruction}
- {time_instruction}
- User Request: "{user_message}"

DISTRIBUTION GUIDELINES:
- Distribute questions evenly across specified difficulty levels
- If multiple question types specified, vary the types throughout
- Ensure each question tests different aspects of the content

CRITICAL CONTENT FOCUS REQUIREMENTS:
- ONLY create questions about TECHNICAL CONTENT, concepts, theories, procedures, and subject matter
- Write questions as if they are from a professional certification exam or university exam
- Questions must be direct, clear, and professional without any meta-references

STRICTLY FORBIDDEN QUESTION ELEMENTS:
- DO NOT mention chapters, sections, or book structure ("Chapter 2", "Section 1.3", etc.)
- DO NOT use phrases like "According to the text", "Based on the provided text", "The book states", "As described in the book"
- DO NOT ask about book organization, preface, introduction, or meta-information
- DO NOT ask "What does the book teach" or "What does the book aim to"
- DO NOT reference the source material in questions

REQUIRED QUESTION STYLE:
- Write questions in direct, technical language
- Ask about concepts, processes, tools, and techniques directly
- Use professional terminology appropriate for the field
- Questions should sound like they come from industry certification exams

Your response MUST be a JSON array of question objects. Each question object must have:
- "difficulty": one of "easy", "medium", or "hard" (matching the specified levels)
- "type": one of "multiple_choice_single_answer", "true_false", or "open_ended_question" (matching specified types)
- "question_text": The full text of the question (clear, specific, and exam-appropriate)
- "options": Array of 4 choices for multiple choice, empty array for others
- "answer": The correct answer as a STRING (for true/false use "True" or "False", for multiple choice use the exact option text)

EXAM QUESTION QUALITY STANDARDS:
- Easy questions: Test basic recall of technical definitions, concepts, and simple comprehension
- Medium questions: Test application of concepts, analysis of technical scenarios, and connections between ideas
- Hard questions: Test evaluation of solutions, synthesis of complex concepts, and critical thinking about technical problems
- Multiple choice: Provide 4 plausible technical options with clear distinctions, only one correct answer
- True/False: Create statements about technical facts that are unambiguously true or false
- Open-ended: Ask for explanations of technical concepts, comparisons of methods, applications of principles

PROFESSIONAL QUESTION EXAMPLES (GOOD):
- "What is the primary function of Apache Kafka in data streaming?"
- "Which algorithm is most efficient for sorting large datasets?"
- "What are the key advantages of using Docker containers?"
- "How does load balancing improve system performance?"
- "What happens when a database transaction fails?"
- "Which data structure provides O(1) lookup time?"

AVOID THESE PHRASES AND PATTERNS (BAD):
- "According to the text/book/chapter..."
- "Based on the provided information..."
- "What tools are mentioned in Chapter X?"
- "What does the book teach about..."
- "As described in the book..."
- "Considering the provided text..."
- "The book aims to..."
- "What is discussed in Section X?"

WRITE QUESTIONS LIKE A PROFESSIONAL EXAM:
- Direct technical questions about concepts and tools
- No reference to source material or book structure
- Professional, industry-standard language
- Focus on practical knowledge and understanding

CRITICAL REQUIREMENTS:
- The "answer" field must ALWAYS be a string
- Base questions on technical concepts from the content
- Make questions appropriate for professional certification or academic exams
- Ensure clear, unambiguous wording
- Questions must test actual technical understanding
- NO meta-references to source material whatsoever"""),
                ("human", "Content: {content}\nTopic: {topic}\nGenerate {count} professional technical exam questions. Write each question as if it appears on a certification exam or university test. Focus ONLY on technical concepts and avoid any reference to source material.")
            ])
            
            chain = question_prompt | self.get_current_llm() | StrOutputParser()
            
            logger.info(f"Invoking AI chain for topic: {topic} using {'Ollama' if self.use_fallback else 'Google Gemini'}")
            
            try:
                result = await chain.ainvoke({
                    "content": content,
                    "topic": topic,
                    "count": count,
                    "difficulty_constraint": difficulty_constraint,
                    "type_constraint": type_constraint
                })
            except Exception as e:
                error_str = str(e).lower()
                # Check if this is a quota exceeded error
                if "quota" in error_str or "429" in error_str or "rate limit" in error_str:
                    logger.warning(f"Google Gemini quota exceeded: {e}")
                    if not self.use_fallback:
                        self.switch_to_fallback()
                        # Retry with fallback LLM
                        chain = question_prompt | self.get_current_llm() | StrOutputParser()
                        logger.info(f"Retrying with Ollama fallback for topic: {topic}")
                        result = await chain.ainvoke({
                            "content": content,
                            "topic": topic,
                            "count": count,
                            "difficulty_constraint": difficulty_constraint,
                            "type_constraint": type_constraint
                        })
                    else:
                        raise e
                else:
                    raise e
            
            logger.info(f"Raw AI response for topic {topic}: {result[:500]}...")
            
            # Parse questions
            try:
                # Clean the response
                cleaned_result = result.strip()
                if cleaned_result.startswith('```json'):
                    cleaned_result = cleaned_result.replace('```json\n', '').replace('\n```', '')
                elif cleaned_result.startswith('```'):
                    cleaned_result = cleaned_result.replace('```\n', '').replace('\n```', '')
                
                logger.info(f"Cleaned response for parsing: {cleaned_result[:300]}...")
                questions_data = json.loads(cleaned_result)
                logger.info(f"Successfully parsed {len(questions_data)} questions for topic: {topic}")
            except json.JSONDecodeError as e:
                logger.error(f"JSON parsing error for topic {topic}: {e}")
                logger.error(f"Raw response: {result}")
                return []
            except Exception as e:
                logger.error(f"Unexpected error parsing response for topic {topic}: {e}")
                return []
            
            questions = []
            for q_data in questions_data:
                # Convert answer to string to handle boolean values from LLM
                answer_value = q_data.get('answer', '')
                if isinstance(answer_value, bool):
                    answer_str = str(answer_value)
                else:
                    answer_str = str(answer_value) if answer_value is not None else ''
                
                question = Question(
                    difficulty=q_data.get('difficulty', 'medium'),
                    type=q_data.get('type', 'multiple_choice_single_answer'),
                    question_text=q_data.get('question_text', ''),
                    options=q_data.get('options', []),
                    answer=answer_str
                )
                questions.append(question)
            
            return questions
            
        except Exception as e:
            logger.error(f"Error generating questions for topic {topic}: {e}")
            return []

    async def generate_lecture(self, request: LectureRequest) -> str:
        """Generate lecture for a book with comprehensive parameters"""
        try:
            # Create knowledge retriever tool
            knowledge_tool = self._create_knowledge_search_tool(request.book_title)
            knowledge_tool.name = "knowledge_retriever_tool" # Ensure the name matches the prompt

            # Create agent for lecture generation
            tools = [knowledge_tool]
            current_llm = self.get_current_llm()
            
            # Try to create the agent with better error handling
            try:
                agent = create_tool_calling_agent(current_llm, tools, self.lecture_prompt)
                agent_executor = AgentExecutor(
                    agent=agent, 
                    tools=tools, 
                    verbose=False,  # Disable verbose to reduce output clutter
                    handle_parsing_errors=True,  # This helps with tool calling issues
                    max_iterations=5,  # Limit iterations to prevent infinite loops
                    return_intermediate_steps=False  # Don't return intermediate steps
                )
            except Exception as agent_error:
                logger.error(f"Error creating agent: {agent_error}")
                # Fallback: try with fallback LLM
                if not self.use_fallback:
                    self.switch_to_fallback()
                    current_llm = self.get_current_llm()
                    agent = create_tool_calling_agent(current_llm, tools, self.lecture_prompt)
                    agent_executor = AgentExecutor(
                        agent=agent, 
                        tools=tools, 
                        verbose=False,
                        handle_parsing_errors=True,
                        max_iterations=5,
                        return_intermediate_steps=False
                    )
                else:
                    raise agent_error
            
            # Prepare parameters with fallbacks
            category = request.category or "General"
            title = request.title or f"Lecture on {request.book_title}"
            scope = request.scope or "whole_book"
            specific_topics = request.specific_topics if scope == "specific_topics" else ""
            detail_level = request.detail_level or "overview"
            
            logger.info(f"Generating lecture with parameters: category={category}, title={title}, scope={scope}, detail_level={detail_level}")
            
            # Create a more focused input that encourages proper tool usage
            input_text = f"""Please create a comprehensive {detail_level} lecture titled "{title}" about {request.book_title} in the {category} category.

Requirements:
- Use the knowledge_retriever_tool to search for relevant content from the book
- Create a well-structured lecture script following the format specified
- Scope: {scope}
{f"- Focus specifically on: {specific_topics}" if specific_topics else ""}

Begin by searching for relevant content using the knowledge retrieval tool."""
            
            try:
                result = await agent_executor.ainvoke({
                    "book_title": request.book_title,
                    "category": category,
                    "title": title,
                    "scope": scope,
                    "specific_topics": specific_topics,
                    "detail_level": detail_level,
                    "user_message": request.user_message,
                    "input": input_text,
                })
                
                # Clean the output to remove any debugging code or unwanted content
                cleaned_output = self._clean_lecture_output(result['output'])
                return cleaned_output
                
            except Exception as execution_error:
                logger.error(f"Error during agent execution: {execution_error}")
                
                # Check if it's a parsing error and try to extract useful content
                error_str = str(execution_error).lower()
                if "parsing" in error_str or "tool" in error_str:
                    # Try a simpler approach - direct content retrieval and simple generation
                    logger.info("Falling back to direct content retrieval approach")
                    return await self._generate_lecture_fallback(request)
                else:
                    raise execution_error
            
        except Exception as e:
            logger.error(f"Error generating lecture: {e}")
            # Check if this is a quota exceeded error and switch to fallback
            error_str = str(e).lower()
            if "quota" in error_str or "429" in error_str or "rate limit" in error_str:
                logger.warning(f"Google Gemini quota exceeded during lecture generation: {e}")
                if not self.use_fallback:
                    self.switch_to_fallback()
                    # Retry with fallback LLM
                    return await self.generate_lecture(request)
                else:
                    raise e
            else:
                raise

    async def _generate_lecture_fallback(self, request: LectureRequest) -> str:
        """Fallback method for lecture generation when agent fails"""
        try:
            logger.info("Using fallback lecture generation method")
            
            # Directly search for content
            table_name = request.book_title
            
            # Search queries based on scope
            if request.scope == "specific_topics" and request.specific_topics:
                search_query = request.specific_topics
            else:
                search_query = f"overview introduction main concepts {request.book_title}"
            
            # Get content directly
            content_results = await self._search_vector_table(table_name, search_query, k=8)
            content = "\n\n".join(content_results) if content_results else "No content found"
            
            # Generate lecture using simple LLM chain
            fallback_prompt = ChatPromptTemplate.from_messages([
                ("system", """You are a professional lecture creator. Create a comprehensive lecture script based on the provided content.

Follow this structure:
# LECTURE SCRIPT: {title}
**Category:** {category} | **Duration:** Estimated time | **Level:** {detail_level}

## LECTURE OVERVIEW
- **Learning Objectives:** What students will achieve
- **Key Concepts:** Main topics covered

## MAIN CONTENT
[Create detailed sections based on the content provided]

## CONCLUSION
- **Key Takeaways:** Essential points
- **Next Steps:** Future learning

Base your lecture entirely on the provided content. Make it engaging and educational."""),
                ("human", """Content: {content}

Create a {detail_level} lecture titled "{title}" for category "{category}".
Book: {book_title}
Scope: {scope}
{specific_topics_instruction}""")
            ])
            
            # Prepare variables
            category = request.category or "General"
            title = request.title or f"Lecture on {request.book_title}"
            detail_level = request.detail_level or "overview"
            scope = request.scope or "whole_book"
            specific_topics_instruction = f"Focus on: {request.specific_topics}" if request.specific_topics else ""
            
            chain = fallback_prompt | self.get_current_llm() | StrOutputParser()
            
            result = await chain.ainvoke({
                "content": content,
                "title": title,
                "category": category,
                "detail_level": detail_level,
                "book_title": request.book_title,
                "scope": scope,
                "specific_topics_instruction": specific_topics_instruction
            })
            
            # Clean the output for the fallback method too
            return self._clean_lecture_output(result)
            
        except Exception as e:
            logger.error(f"Error in fallback lecture generation: {e}")
            return f"I apologize, but I encountered an error generating the lecture: {str(e)}"

    def _clean_lecture_output(self, output: str) -> str:
        """Clean the lecture output to remove unwanted debugging code and tool calls"""
        try:
            import re
            
            # Remove Python code blocks that contain tool calls
            # Pattern to match ```python ... ``` blocks
            python_code_pattern = r'```python\s*\n.*?```'
            cleaned_output = re.sub(python_code_pattern, '', output, flags=re.DOTALL)
            
            # Remove any remaining tool call references
            tool_call_patterns = [
                r'print\(default_api\.knowledge_retriever_tool\([^)]+\)\)',
                r'default_api\.knowledge_retriever_tool\([^)]+\)',
                r'knowledge_retriever_tool\([^)]+\)',
                r'> Entering new AgentExecutor chain\.\.\.',
                r'> Finished chain\.',
                r'```\s*\n*```'  # Empty code blocks
            ]
            
            for pattern in tool_call_patterns:
                cleaned_output = re.sub(pattern, '', cleaned_output, flags=re.MULTILINE)
            
            # Remove multiple consecutive newlines
            cleaned_output = re.sub(r'\n{3,}', '\n\n', cleaned_output)
            
            # Remove leading/trailing whitespace
            cleaned_output = cleaned_output.strip()
            
            # If the output is too short after cleaning, it might have been mostly debugging
            if len(cleaned_output) < 100:
                logger.warning("Output was mostly debugging code, using fallback generation")
                return "The lecture content was not generated properly. Please try again."
            
            return cleaned_output
            
        except Exception as e:
            logger.error(f"Error cleaning lecture output: {e}")
            # Return original output if cleaning fails
            return output

    def _format_questions_response(self, question_response: QuestionResponse) -> str:
        """Format questions response for chat"""
        formatted = f"# Questions for: {question_response.chapter}\n\n"
        
        for i, question in enumerate(question_response.questions_generated, 1):
            formatted += f"**Question {i}: ({question.difficulty}, {question.type})**\n"
            formatted += f"{question.question_text}\n"
            
            if question.options:
                for option in question.options:
                    formatted += f"- {option}\n"
            
            formatted += f"**Answer:** {question.answer}\n\n---\n\n"
        
        return formatted

    async def _get_or_create_session(self, session_id: str, book_title: str) -> Dict[str, Any]:
        """Get existing session or create new one"""
        try:
            # CRITICAL FIX: Only try to get existing session if session_id is provided and not empty
            session = None
            if session_id and session_id.strip() and session_id != "null":
                logger.info(f"Attempting to find existing session: {session_id}")
                session = await self.db.get_chat_session(session_id)
                
                if session:
                    logger.info(f"Found existing session: {session['id']} for book: {session.get('book_title', 'Unknown')}")
                    return session
                else:
                    logger.warning(f"Session {session_id} not found in database, will create new session")
            else:
                logger.info(f"No valid session_id provided (got: '{session_id}'), creating new session")
            
            # Create new session only if existing session not found or session_id is invalid
            logger.info(f"Creating new session for book: {book_title}")
            
            # Get book info
            book = await self.db.get_book_by_title(book_title)
            if not book:
                raise ValueError(f"Book '{book_title}' not found")
            
            # Create new session
            new_session_id = await self.db.create_chat_session(
                user_id="default_user",  # In production, get from auth
                book_id=book['id'],
                session_name=f"Chat about {book_title}"
            )
            
            # Get the newly created session
            session = await self.db.get_chat_session(new_session_id)
            if not session:
                raise RuntimeError(f"Failed to retrieve newly created session {new_session_id}")
                
            logger.info(f"Created new session: {session['id']} for book: {book_title}")
            return session
            
        except Exception as e:
            logger.error(f"Error getting/creating session: {e}")
            raise

    async def _get_or_create_curriculum_session(self, session_id: str, curriculum: str) -> Dict[str, Any]:
        """Get existing session or create new one for curriculum"""
        try:
            # Only try to get existing session if session_id is provided and not empty
            session = None
            if session_id and session_id.strip() and session_id != "null":
                logger.info(f"Attempting to find existing session: {session_id}")
                session = await self.db.get_chat_session(session_id)
                
                if session:
                    logger.info(f"Found existing session: {session['id']} for curriculum: {session.get('curriculum_name', 'Unknown')}")
                    return session
                else:
                    logger.warning(f"Session {session_id} not found in database, will create new session")
            else:
                logger.info(f"No valid session_id provided (got: '{session_id}'), creating new session")
            
            # Create new session for curriculum - for now use the first book in the curriculum
            logger.info(f"Creating new session for curriculum: {curriculum}")
            
            # Get curriculum info
            curriculum_info = await self.db.get_curriculum_by_name(curriculum)
            if not curriculum_info:
                raise ValueError(f"Curriculum '{curriculum}' not found")
            
            # Get a book from this curriculum (for now, get the first one)
            books_in_curriculum = await self.db.get_books_by_curriculum(curriculum_info['id'])
            if not books_in_curriculum:
                raise ValueError(f"No books found in curriculum '{curriculum}'")
            
            first_book = books_in_curriculum[0]
            
            # Create new session using the first book
            new_session_id = await self.db.create_chat_session(
                user_id="550e8400-e29b-41d4-a716-446655440000",  # Default UUID for demo
                book_id=first_book['id'],
                session_name=f"Chat about {curriculum}"
            )
            
            # Get the newly created session
            session = await self.db.get_chat_session(new_session_id)
            if not session:
                raise RuntimeError(f"Failed to retrieve newly created session {new_session_id}")
                
            logger.info(f"Created new session: {session['id']} for curriculum: {curriculum}")
            return session
            
        except Exception as e:
            logger.error(f"Error getting/creating curriculum session: {e}")
            raise

    async def _handle_curriculum_question_answering(self, request: ChatRequest, session: Dict[str, Any]) -> str:
        """Handle question answering for curriculum-based chat"""
        try:
            # Get or create chat history for the session (like in the regular method)
            session_id = str(session['id'])
            if session_id not in self.chat_histories:
                self.chat_histories[session_id] = ConversationBufferMemory(
                    memory_key="chat_history", 
                    return_messages=True
                )
            memory = self.chat_histories[session_id]
            
            # Load existing messages from database into memory if memory is empty
            if len(memory.chat_memory.messages) == 0:
                await self.memory_manager.load_chat_history_to_memory(session_id, memory, limit=50)
            
            # DIRECT VECTOR SEARCH APPROACH - Let's directly search the curriculum first
            logger.info(f"🔍 DIRECT SEARCH: Starting curriculum search for '{request.curriculum}' with query: {request.user_message[:50]}...")
            
            # Search curriculum embeddings directly
            search_results = await self._search_curriculum_embeddings(request.curriculum, request.user_message, k=6)
            
            if search_results:
                combined_content = "\n\n".join([r['content'] for r in search_results])
                logger.info(f"✅ DIRECT SEARCH SUCCESS: Found {len(search_results)} chunks from curriculum '{request.curriculum}'")
                
                # Now use this content with a simple LLM call
                simple_prompt = ChatPromptTemplate.from_messages([
                    ("system", f"""You are an expert educational assistant. You have been provided with relevant content from the {request.curriculum} curriculum to answer the user's question.

Use the provided curriculum content to give a comprehensive, well-structured answer.

**RESPONSE STRUCTURE:**
🎯 **DIRECT ANSWER**
Start with a clear, direct answer to the user's question.

📚 **DETAILED EXPLANATION**
Provide thorough explanation using the curriculum content.

🔑 **KEY CONCEPTS**
Highlight important concepts and terms.

💡 **PRACTICAL EXAMPLES**
Include relevant examples from the content.

Always end with: (Source: Internal Knowledge Base)

**CURRICULUM CONTENT:**
{combined_content}"""),
                    MessagesPlaceholder(variable_name="chat_history"),
                    ("human", "{user_message}")
                ])
                
                # Get chat history for context
                chat_history = memory.chat_memory.messages if memory.chat_memory.messages else []
                
                chain = simple_prompt | self.llm | StrOutputParser()
                response = await chain.ainvoke({
                    "user_message": request.user_message,
                    "chat_history": chat_history
                })
                
                # Save context to memory
                memory.save_context(
                    inputs={"input": request.user_message},
                    outputs={"output": response}
                )
                
                logger.info(f"✅ CURRICULUM RESPONSE GENERATED: Using {len(search_results)} chunks from vector database")
                return response
                
            else:
                logger.warning(f"❌ NO CONTENT FOUND: No curriculum content found for query: {request.user_message[:50]}...")
                return f"I couldn't find specific information about your question in the {request.curriculum} curriculum. This might be because the content hasn't been properly indexed or your question is outside the curriculum scope. Please try rephrasing your question or ask about topics covered in the {request.curriculum} curriculum."
            
        except Exception as e:
            logger.error(f"Error handling curriculum question answering: {e}")
            return f"I apologize, but I encountered an error while processing your question about {request.curriculum}. Please try again."

    # Session management methods
    async def create_session(self, user_id: str, book_title: str, session_name: str = None) -> ChatSessionModel:
        """Create new chat session"""
        try:
            # Get book info
            book = await self.db.get_book_by_title(book_title)
            if not book:
                raise ValueError(f"Book '{book_title}' not found")
            
            # Create session
            session_id = await self.db.create_chat_session(
                user_id=user_id,
                book_id=book['id'],
                session_name=session_name or f"Chat about {book_title}"
            )
            
            # Get created session
            session_data = await self.db.get_chat_session(session_id)
            
            # Create response manually with string conversion
            return ChatSessionModel(
                id=str(session_data['id']),
                user_id=str(session_data['user_id']),
                book_id=session_data['book_id'],
                session_name=session_data['session_name'],
                created_at=session_data['created_at'],
                updated_at=session_data['updated_at']
            )
            
        except Exception as e:
            logger.error(f"Error creating session: {e}")
            raise

    async def create_curriculum_session(self, user_id: str, curriculum_name: str, session_name: str = None) -> ChatSessionModel:
        """Create new curriculum-based chat session"""
        try:
            # Ensure user exists (create if not)
            await self._ensure_user_exists(user_id)
            
            # Get curriculum info
            curriculum_info = await self.db.get_curriculum_by_name(curriculum_name)
            if not curriculum_info:
                raise ValueError(f"Curriculum '{curriculum_name}' not found")
            
            # Get books in this curriculum
            books_in_curriculum = await self.db.get_books_by_curriculum(curriculum_info['id'])
            if not books_in_curriculum:
                raise ValueError(f"No books found in curriculum '{curriculum_name}'")
            
            # Use the first book for session creation (the system will search across all books in the curriculum)
            first_book = books_in_curriculum[0]
            
            # Create session
            session_id = await self.db.create_chat_session(
                user_id=user_id,
                book_id=first_book['id'],
                session_name=session_name or f"Chat with {curriculum_name} Curriculum"
            )
            
            # Get created session
            session_data = await self.db.get_chat_session(session_id)
            
            # Create response manually with string conversion
            return ChatSessionModel(
                id=str(session_data['id']),
                user_id=str(session_data['user_id']),
                book_id=session_data['book_id'],
                session_name=session_data['session_name'],
                created_at=session_data['created_at'],
                updated_at=session_data['updated_at']
            )
            
        except Exception as e:
            logger.error(f"Error creating curriculum session: {e}")
            raise

    async def _ensure_user_exists(self, user_id: str):
        """Ensure user exists in database, create if not"""
        try:
            # Check if user exists
            async with self.db.get_connection() as conn:
                user_exists = await conn.fetchval(
                    "SELECT EXISTS(SELECT 1 FROM users WHERE id = $1)",
                    user_id
                )
                
                if not user_exists:
                    # Create a demo user
                    await conn.execute(
                        "INSERT INTO users (id, full_name, email, password_hash) VALUES ($1, $2, $3, $4)",
                        user_id,
                        f"User {user_id[:8]}",
                        f"user_{user_id[:8]}@zakerly.com",
                        "demo_hash"
                    )
                    logger.info(f"Created demo user: {user_id}")
                    
        except Exception as e:
            logger.error(f"Error ensuring user exists: {e}")
            raise

    async def get_session(self, session_id: str) -> Optional[ChatSessionModel]:
        """Get session by ID"""
        try:
            session_data = await self.db.get_chat_session(session_id)
            if session_data:
                # Create response manually with string conversion
                return ChatSessionModel(
                    id=str(session_data['id']),
                    user_id=session_data['user_id'],
                    book_id=session_data['book_id'],
                    session_name=session_data['session_name'],
                    created_at=session_data['created_at'],
                    updated_at=session_data['updated_at']
                )
            return None
            
        except Exception as e:
            logger.error(f"Error getting session: {e}")
            raise

    async def get_user_sessions(self, user_id: str) -> List[ChatSessionModel]:
        """Get all sessions for a user"""
        try:
            sessions_data = await self.db.get_user_sessions(user_id)
            return [ChatSessionModel(**session_data) for session_data in sessions_data]
            
        except Exception as e:
            logger.error(f"Error getting user sessions: {e}")
            raise

    async def get_chat_history(self, session_id: str, limit: int = 50) -> List[ChatMessageModel]:
        """Get chat history for session"""
        try:
            history_data = await self.db.get_chat_history(session_id, limit)
            return [ChatMessageModel(**msg_data) for msg_data in history_data]
            
        except Exception as e:
            logger.error(f"Error getting chat history: {e}")
            raise

    async def delete_session(self, session_id: str) -> bool:
        """Delete chat session"""
        try:
            # Clear in-memory chat history
            if session_id in self.chat_histories:
                del self.chat_histories[session_id]
            
            # Clear database messages
            await self.memory_manager.clear_session_history(session_id)
            
            result = await self.db.execute_command(
                "DELETE FROM chat_sessions WHERE id = $1", session_id
            )
            return "DELETE 1" in result
            
        except Exception as e:
            logger.error(f"Error deleting session: {e}")
            raise

    # Memory management methods
    async def get_memory_stats(self, session_id: str) -> Dict[str, Any]:
        """Get memory statistics for a session"""
        try:
            message_count = await self.memory_manager.get_message_count(session_id)
            recent_messages = await self.memory_manager.get_recent_messages(session_id, limit=10)
            
            return {
                "session_id": session_id,
                "total_messages": message_count,
                "recent_messages_count": len(recent_messages),
                "memory_type": "conversation_buffer"
            }
        except Exception as e:
            logger.error(f"Error getting memory stats: {e}")
            return {}

    async def clear_session_memory(self, session_id: str) -> bool:
        """Clear memory for a specific session"""
        try:
            # Clear in-memory chat history
            if session_id in self.chat_histories:
                self.chat_histories[session_id].clear()
            
            # Clear database messages
            return await self.memory_manager.clear_session_history(session_id)
            
        except Exception as e:
            logger.error(f"Error clearing session memory: {e}")
            return False

    async def get_recent_messages(self, session_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent messages for a session"""
        try:
            messages = await self.memory_manager.get_recent_messages(session_id, limit)
            
            # Convert to dict format
            result = []
            for msg in messages:
                result.append({
                    "type": "user" if msg.__class__.__name__ == "HumanMessage" else "assistant",
                    "content": msg.content
                })
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting recent messages: {e}")
            return []

    async def get_session_entities(self, session_id: str) -> Dict[str, Any]:
        """Get extracted entities for a session (simplified - returns empty for compatibility)"""
        try:
            # Since we simplified the memory system, we don't extract entities anymore
            # Return empty dict for API compatibility
            return {
                "message": "Entity extraction not available in simplified memory system",
                "entities": {}
            }
        except Exception as e:
            logger.error(f"Error getting session entities: {e}")
            return {"entities": {}}

    async def get_session_summary(self, session_id: str) -> Dict[str, Any]:
        """Get conversation summary for a session (simplified - returns message count)"""
        try:
            # Since we simplified the memory system, we don't create summaries anymore
            # Return basic info for API compatibility
            message_count = await self.memory_manager.get_message_count(session_id)
            return {
                "message": "Conversation summarization not available in simplified memory system",
                "summary": f"Session has {message_count} total messages",
                "message_count": message_count
            }
        except Exception as e:
            logger.error(f"Error getting session summary: {e}")
            return {"summary": ""}

    async def cleanup_expired_memories(self) -> Dict[str, Any]:
        """Clean up expired memories (simplified - no complex memory to clean)"""
        try:
            # Since we simplified the memory system, there are no expired memories to clean
            # Return success message for API compatibility
            return {
                "status": "success", 
                "message": "No expired memories to clean in simplified memory system"
            }
        except Exception as e:
            logger.error(f"Error cleaning up expired memories: {e}")
            return {"status": "error", "message": str(e)}

    # Lecture Scripts methods
    async def create_lecture_script(self, user_id: str, request) -> dict:
        """Create a new lecture script"""
        try:
            # Insert into database
            query = """
                INSERT INTO lecture_scripts 
                (user_id, book_id, title, scope, specific_topics, detail_level, difficulty, duration, content)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                RETURNING id, user_id, book_id, title, scope, specific_topics, detail_level, difficulty, duration, content, created_at, updated_at
            """
            
            result = await self.db.execute_query(
                query,
                user_id, request.book_id, request.title, request.scope,
                request.specific_topics, request.detail_level, request.difficulty,
                request.duration, request.content
            )
            
            if result:
                row = result[0]
                return {
                    "id": str(row["id"]),
                    "user_id": str(row["user_id"]),
                    "book_id": row["book_id"],
                    "title": row["title"],
                    "scope": row["scope"],
                    "specific_topics": row["specific_topics"],
                    "detail_level": row["detail_level"],
                    "difficulty": row["difficulty"],
                    "duration": row["duration"],
                    "content": row["content"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"]
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error creating lecture script: {e}")
            raise e

    async def get_lecture_script(self, script_id: str, user_id: str) -> dict:
        """Get a specific lecture script by ID"""
        try:
            query = """
                SELECT id, user_id, book_id, title, scope, specific_topics, detail_level, difficulty, duration, content, created_at, updated_at
                FROM lecture_scripts
                WHERE id = $1 AND user_id = $2
            """
            
            result = await self.db.execute_query(query, script_id, user_id)
            
            if result:
                row = result[0]
                return {
                    "id": str(row["id"]),
                    "user_id": str(row["user_id"]),
                    "book_id": row["book_id"],
                    "title": row["title"],
                    "scope": row["scope"],
                    "specific_topics": row["specific_topics"],
                    "detail_level": row["detail_level"],
                    "difficulty": row["difficulty"],
                    "duration": row["duration"],
                    "content": row["content"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"]
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting lecture script {script_id}: {e}")
            raise e

    async def get_user_scripts(self, user_id: str) -> List[dict]:
        """Get all lecture scripts for a user"""
        try:
            query = """
                SELECT ls.id, ls.user_id, ls.book_id, ls.title, ls.scope, ls.specific_topics, 
                       ls.detail_level, ls.difficulty, ls.duration, ls.content, ls.created_at, ls.updated_at,
                       b.title as book_title
                FROM lecture_scripts ls
                LEFT JOIN books b ON ls.book_id = b.id
                WHERE ls.user_id = $1
                ORDER BY ls.created_at DESC
            """
            
            result = await self.db.execute_query(query, user_id)
            
            scripts = []
            if result:
                for row in result:
                    scripts.append({
                        "id": str(row["id"]),
                        "user_id": str(row["user_id"]),
                        "book_id": row["book_id"],
                        "title": row["title"],
                        "scope": row["scope"],
                        "specific_topics": row["specific_topics"],
                        "detail_level": row["detail_level"],
                        "difficulty": row["difficulty"],
                        "duration": row["duration"],
                        "content": row["content"],
                        "created_at": row["created_at"],
                        "updated_at": row["updated_at"],
                        "book_title": row["book_title"]
                    })
            
            return scripts
            
        except Exception as e:
            logger.error(f"Error getting user scripts: {e}")
            raise e

    async def update_lecture_script(self, script_id: str, user_id: str, request) -> dict:
        """Update a lecture script"""
        try:
            # Build dynamic update query
            update_fields = []
            values = []
            param_count = 1
            
            if request.title is not None:
                update_fields.append(f"title = ${param_count}")
                values.append(request.title)
                param_count += 1
                
            if request.content is not None:
                update_fields.append(f"content = ${param_count}")
                values.append(request.content)
                param_count += 1
                
            if request.scope is not None:
                update_fields.append(f"scope = ${param_count}")
                values.append(request.scope)
                param_count += 1
                
            if request.specific_topics is not None:
                update_fields.append(f"specific_topics = ${param_count}")
                values.append(request.specific_topics)
                param_count += 1
                
            if request.detail_level is not None:
                update_fields.append(f"detail_level = ${param_count}")
                values.append(request.detail_level)
                param_count += 1
                
            if request.difficulty is not None:
                update_fields.append(f"difficulty = ${param_count}")
                values.append(request.difficulty)
                param_count += 1
                
            if request.duration is not None:
                update_fields.append(f"duration = ${param_count}")
                values.append(request.duration)
                param_count += 1
            
            if not update_fields:
                # Nothing to update, return existing script
                return await self.get_lecture_script(script_id, user_id)
            
            update_fields.append(f"updated_at = ${param_count}")
            values.append(datetime.utcnow())
            param_count += 1
            
            # Add WHERE clause parameters
            values.extend([script_id, user_id])
            
            query = f"""
                UPDATE lecture_scripts 
                SET {', '.join(update_fields)}
                WHERE id = ${param_count} AND user_id = ${param_count + 1}
                RETURNING id, user_id, book_id, title, scope, specific_topics, detail_level, difficulty, duration, content, created_at, updated_at
            """
            
            result = await self.db.execute_query(query, *values)
            
            if result:
                row = result[0]
                return {
                    "id": str(row["id"]),
                    "user_id": str(row["user_id"]),
                    "book_id": row["book_id"],
                    "title": row["title"],
                    "scope": row["scope"],
                    "specific_topics": row["specific_topics"],
                    "detail_level": row["detail_level"],
                    "difficulty": row["difficulty"],
                    "duration": row["duration"],
                    "content": row["content"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"]
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error updating lecture script {script_id}: {e}")
            raise e

    async def delete_lecture_script(self, script_id: str, user_id: str) -> bool:
        """Delete a lecture script"""
        try:
            query = """
                DELETE FROM lecture_scripts 
                WHERE id = $1 AND user_id = $2
            """
            
            result = await self.db.execute_query(query, script_id, user_id)
            return result is not None
            
        except Exception as e:
            logger.error(f"Error deleting lecture script {script_id}: {e}")
            raise e