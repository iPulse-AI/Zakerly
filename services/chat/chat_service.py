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

    async def handle_chat(self, request: ChatRequest) -> ChatResponse:
        """Handle chat request with intent routing"""
        try:
            # First, determine the intent
            intent_result = await self._classify_intent(request.book_title, request.user_message)
            intent = intent_result.get('intent', 'answer_question')
            
            # Get or create session
            session = await self._get_or_create_session(request.session_id, request.book_title)
            
            # Route based on intent
            if intent == "generate_questions":
                # Handle question generation
                question_request = QuestionGenerationRequest(
                    book_title=request.book_title,
                    user_message=request.user_message
                )
                question_response = await self.generate_questions(question_request)
                response_text = self._format_questions_response(question_response)
                
            elif intent == "generate_lecture":
                # Handle lecture generation
                lecture_request = LectureRequest(
                    book_title=request.book_title,
                    user_message=request.user_message,
                    topic=None  # Will be determined by the service
                )
                response_text = await self.generate_lecture(lecture_request)
                
            else:
                # Handle regular Q&A
                response_text = await self._handle_question_answering(request, session)
            
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
                metadata={"book_title": request.book_title}
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
        """Create knowledge base search tool"""
        
        def search_knowledge(query: str) -> str:
            try:
                # Use the full book title as table name (no sanitization)
                table_name = book_title.lower()
                
                logger.info(f"Searching for book '{book_title}' using table '{table_name}' with query '{query[:50]}...'")
                
                # Set the current book title for context in search
                self._current_book_title = book_title
                
                # Run the async search in a synchronous context
                import asyncio
                try:
                    # Try to get the current event loop
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # If loop is running, we need to run in a thread
                        import concurrent.futures
                        with concurrent.futures.ThreadPoolExecutor() as executor:
                            future = executor.submit(asyncio.run, self._search_vector_table(table_name, query, k=6))
                            results = future.result()
                    else:
                        # If no loop is running, we can run directly
                        results = loop.run_until_complete(self._search_vector_table(table_name, query, k=6))
                except RuntimeError:
                    # No event loop, create a new one
                    results = asyncio.run(self._search_vector_table(table_name, query, k=6))
                
                if results:
                    combined_results = "\n\n".join(results)
                    logger.info(f"Found {len(results)} relevant chunks for query: {query[:50]}...")
                    return combined_results
                else:
                    logger.warning(f"No relevant information found for query: {query[:50]}...")
                    return f"No relevant information found in the knowledge base for '{book_title}'. The book may not have been properly ingested or the vector table may be missing. Please check if the book has been uploaded and processed correctly."
                
            except Exception as e:
                logger.error(f"Error searching knowledge base for '{book_title}': {e}")
                return f"Error accessing knowledge base for '{book_title}': {str(e)}. This may indicate that the book has not been properly ingested or there's a database connectivity issue."
        
        return Tool(
            name="search_internal_knowledge_base",
            description=f"Search in the knowledge base for the book '{book_title}' to find relevant information. Input should be a search query string only.",
            func=search_knowledge
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
        """Generate questions for a book based on comprehensive exam parameters"""
        try:
            logger.info(f"Question generation request for book: {request.book_title}")
            logger.info(f"Parameters: count={request.count}, difficulty={request.difficulty}, types={request.question_types}")
            logger.info(f"Scope: {request.scope_type}, Topics: {request.specific_topics}, Time: {request.time_limit}min")
            
            # Use user-specified parameters directly
            user_count = request.count or 10
            user_difficulty = request.difficulty or ['medium']
            user_question_types = request.question_types or ['multiple_choice_single_answer']
            
            # Determine content scope for question generation
            if hasattr(request, 'scope_type') and request.scope_type == 'specific_topics' and hasattr(request, 'specific_topics') and request.specific_topics:
                # Focus on specific topics provided by user
                topic_list = [topic.strip() for topic in request.specific_topics.split(',') if topic.strip()]
                if not topic_list:
                    topic_list = [request.specific_topics]
                logger.info(f"Generating questions for specific topics: {topic_list}")
                main_topic = ', '.join(topic_list)
            else:
                # Analyze the request to extract topics if needed, or use whole book approach
                logger.info("Generating questions for whole book content")
                analysis_chain = self.analysis_prompt | self.get_current_llm() | StrOutputParser()
                
                try:
                    analysis_result = await analysis_chain.ainvoke({
                        "user_message": request.user_message
                    })
                except Exception as e:
                    error_str = str(e).lower()
                    if "quota" in error_str or "429" in error_str or "rate limit" in error_str:
                        logger.warning(f"Google Gemini quota exceeded during analysis: {e}")
                        if not self.use_fallback:
                            self.switch_to_fallback()
                            analysis_chain = self.analysis_prompt | self.get_current_llm() | StrOutputParser()
                            analysis_result = await analysis_chain.ainvoke({
                                "user_message": request.user_message
                            })
                        else:
                            raise e
                    else:
                        raise e
                
                # Parse analysis result
                try:
                    analysis_data = json.loads(analysis_result.strip().replace('```json\n', '').replace('\n```', ''))
                    topics = analysis_data.get('topics', [])
                except:
                    topics = []
                
                # If no topics specified, get some from the book or use general approach
                if not topics:
                    topics = await self._extract_topics_from_book(request.book_title)
                
                main_topic = topics[0] if topics else "comprehensive book content and main concepts"
                topic_list = [main_topic]
            
            # Generate all questions with enhanced parameters
            parameters = {
                'count': user_count,
                'difficulty': user_difficulty,
                'question_types': user_question_types,
                'scope_type': getattr(request, 'scope_type', 'whole_book'),
                'specific_topics': getattr(request, 'specific_topics', None),
                'time_limit': getattr(request, 'time_limit', None),
                'user_message': request.user_message
            }
            
            # Generate questions using the determined topic(s)
            all_questions = await self._generate_questions_for_topic(
                request.book_title, 
                main_topic, 
                parameters
            )
            
            logger.info(f"Successfully generated {len(all_questions)} questions for {request.book_title}")
            
            if len(all_questions) == 0:
                logger.warning("No questions were generated - this may indicate an issue with content retrieval or AI generation")
            
            return QuestionResponse(
                chapter=f"{request.book_title} - {main_topic}",
                questions_generated=all_questions
            )
            
        except Exception as e:
            logger.error(f"Error generating questions: {e}")
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

    async def _generate_questions_for_topic(self, book_title: str, topic: str, parameters: Dict[str, Any]) -> List[Question]:
        """Generate questions for a specific topic"""
        try:
            # Set the current book title for context in search
            self._current_book_title = book_title
            
            # Use the full book title as table name (no sanitization)
            table_name = book_title
            
            # Search for content related to the topic
            results = await self._search_vector_table(table_name, topic, k=8)
            content = "\n\n".join(results)
            
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
                user_id=session_data['user_id'],
                book_id=session_data['book_id'],
                session_name=session_data['session_name'],
                created_at=session_data['created_at'],
                updated_at=session_data['updated_at']
            )
            
        except Exception as e:
            logger.error(f"Error creating session: {e}")
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