import logging
from typing import List, Optional, Dict, Any
import json
import os
from datetime import datetime

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.embeddings import OllamaEmbeddings
from langchain_community.vectorstores.pgvector import PGVector
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_core.messages import HumanMessage, AIMessage
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.tools import Tool, StructuredTool
from pydantic import BaseModel, Field
import httpx

import sys
sys.path.append('/app/shared')

from models import (
    ChatRequest, ChatResponse, QuestionGenerationRequest, QuestionResponse,
    LectureRequest, ChatSessionModel, ChatMessageModel, MessageType, Question
)
from database import DatabaseManager
from utils import RedisManager, generate_session_id
from memory import PostgreSQLAgentMemory, MemoryManager

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
        
        self.llm = ChatGoogleGenerativeAI(
            model=os.getenv("CHAT_MODEL_NAME", "gemini-1.5-flash"),
            temperature=float(os.getenv("CHAT_MODEL_TEMPERATURE", "0.7")),
            google_api_key=os.getenv("GOOGLE_API_KEY")
        )
        
        self.connection_string = os.getenv("DATABASE_URL")
        
        # Initialize memory manager
        self.memory_manager = MemoryManager(db_manager)
        
        # Initialize prompts
        self._setup_prompts()

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
            ("system", """You are a helpful and knowledgeable research assistant. Your primary goal is to answer the user's question accurately and comprehensively by following a strict, logical process.

You have access to two tools:
1. `search_internal_knowledge_base`: A specialized database of textbooks on academic subjects.
2. `web_search`: A general-purpose internet search engine.

To answer the user's question, you MUST follow this reasoning process:

**STEP 1: INTERNAL SEARCH**
First, you MUST use the `search_internal_knowledge_base` tool. Formulate a concise query based on the user's question.

**STEP 2: CRITICAL EVALUATION**
After the `search_internal_knowledge_base` tool runs, you MUST critically evaluate the text it returns. State your evaluation clearly: "Does this retrieved text contain a direct and sufficient answer to the user's original question?"

**STEP 3: FORCED DECISION & ACTION**
Based on your evaluation:
- **If your evaluation is YES**, then immediately synthesize your final answer based ONLY on that text. Your answer must start with: "Based on the internal knowledge base: ..."
- **If your evaluation is NO**, you MUST state, "The internal knowledge base does not contain the answer. I will now search the web." and then use the `web_search` tool. After the web search, synthesize the final answer based on its results.

**STEP 4: FINAL ANSWER & CITATION**
After gathering information, provide the final, comprehensive answer. Your final answer must end with a citation: `(Source: Internal Knowledge Base)` or `(Source: Web Search)`."""),
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
            ("system", """You are Professor A.I., a specialized AI agent designed to generate clear, engaging, and well-structured lectures. Your entire knowledge base comes from a book that has been embedded in a vector database, which you can access exclusively through your knowledge_retriever_tool.

Your primary goal is to act as an expert educator, transforming raw information from the book into a high-quality lecture tailored to the user's request.

**Your Core Workflow:**

1. **Parse the Request:** Carefully analyze the user's message to identify the topic and audience.

2. **Determine the Topic:**
   - If a topic is specified, use it.
   - If no topic is specified, choose one yourself by searching for "table of contents" or "summary" first.

3. **Determine the Audience:**
   - If an audience is specified (e.g., "kids," "experts," "beginners"), adapt accordingly.
   - If no audience is specified, assume university-level students.

4. **Retrieve Knowledge:** Use the knowledge_retriever_tool with the determined topic as your query.

5. **Synthesize and Structure:** Create a coherent and structured lecture with smooth transitions.

**Required Lecture Structure:**
- **Lecture Title:** A clear and relevant title
- **Introduction:** Hook to grab interest and brief overview
- **Body with Headings:** Break content into logical sections with clear headings (##)
- **Conclusion:** Summarize key takeaways and provide concluding thoughts

**Strict Rules:**
- NEVER invent information outside of what the knowledge_retriever_tool provides
- NEVER mention your tools or internal processes unless announcing a chosen topic
- If no relevant information is found, inform the user politely"""),
            ("human", "book_title: {book_title}\nmessage: {user_message}\naudience: {audience}")
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
        """Handle question answering with sophisticated memory"""
        try:
            # Get memory instance for this session
            memory = self.memory_manager.get_memory(
                session_id=str(session['id']),
                max_conversation_length=20,
                summary_threshold=50,
                entity_extraction_enabled=True,
                memory_ttl_hours=24 * 7  # 7 days
            )
            
            # Load memory variables
            memory_vars = await memory._load_memory_variables_async({})
            
            # Get conversation history from memory
            chat_history = memory_vars.get("history", [])
            
            # Get entities and summary for context
            entities = memory_vars.get("entities", {})
            summary = memory_vars.get("summary", "")
            context = memory_vars.get("context", {})
            
            # Save current context
            await memory.save_context_data("current_book", request.book_title)
            await memory.save_context_data("last_query", request.user_message)
            
            # Create tools
            tools = [
                self._create_knowledge_search_tool(request.book_title),
                self._create_web_search_tool()
            ]
            
            # Enhanced prompt with memory context
            enhanced_prompt = ChatPromptTemplate.from_messages([
                ("system", """You are a helpful and knowledgeable research assistant. Your primary goal is to answer the user's question accurately and comprehensively by following a strict, logical process.

You have access to two tools:
1. `search_internal_knowledge_base`: A specialized database of textbooks on academic subjects.
2. `web_search`: A general-purpose internet search engine.

MEMORY CONTEXT:
- Conversation Summary: {summary}
- Important Entities: {entities}
- Previous Context: {context}

Use this memory context to provide more personalized and contextual responses. Reference previous discussions when relevant.

To answer the user's question, you MUST follow this reasoning process:

**STEP 1: INTERNAL SEARCH**
First, you MUST use the `search_internal_knowledge_base` tool. Formulate a concise query based on the user's question and memory context.

**STEP 2: CRITICAL EVALUATION**
After the `search_internal_knowledge_base` tool runs, you MUST critically evaluate the text it returns. State your evaluation clearly: "Does this retrieved text contain a direct and sufficient answer to the user's original question?"

**STEP 3: FORCED DECISION & ACTION**
Based on your evaluation:
- **If your evaluation is YES**, then immediately synthesize your final answer based ONLY on that text. Your answer must start with: "Based on the internal knowledge base: ..."
- **If your evaluation is NO**, you MUST state, "The internal knowledge base does not contain the answer. I will now search the web." and then use the `web_search` tool. After the web search, synthesize the final answer based on its results.

**STEP 4: FINAL ANSWER & CITATION**
After gathering information, provide the final, comprehensive answer. Your final answer must end with a citation: `(Source: Internal Knowledge Base)` or `(Source: Web Search)`."""),
                MessagesPlaceholder(variable_name="chat_history"),
                ("human", "book_title: {book_title}\nmessage: {user_message}"),
                MessagesPlaceholder(variable_name="agent_scratchpad")
            ])
            
            # Create agent with enhanced prompt
            agent = create_tool_calling_agent(self.llm, tools, enhanced_prompt)
            agent_executor = AgentExecutor(
                agent=agent, 
                tools=tools, 
                verbose=True,
                return_intermediate_steps=True
            )
            
            # Execute with memory context
            result = await agent_executor.ainvoke({
                "book_title": request.book_title,
                "user_message": request.user_message,
                "chat_history": chat_history,
                "summary": summary,
                "entities": str(entities),
                "context": str(context),
                "input": request.user_message  # Required for memory
            })
            
            # Save the interaction to memory
            await memory._save_context_async(
                {"input": request.user_message},
                {"output": result['output']}
            )
            
            return result['output']
            
        except Exception as e:
            logger.error(f"Error in question answering: {e}")
            return f"I apologize, but I encountered an error while processing your question: {str(e)}"

    def _create_knowledge_search_tool(self, book_title: str) -> Tool:
        """Create knowledge base search tool"""
        
        def search_knowledge(query: str) -> str:
            try:
                # Use the full book title as table name (no sanitization)
                table_name = book_title
                
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
                """, table_name)
                
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
                    FROM "{table_name}"
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
        """Generate questions for a book"""
        try:
            # Analyze the request
            analysis_chain = self.analysis_prompt | self.llm | StrOutputParser()
            analysis_result = await analysis_chain.ainvoke({
                "user_message": request.user_message
            })
            
            # Parse analysis result
            analysis_data = json.loads(analysis_result.strip().replace('```json\n', '').replace('\n```', ''))
            
            # If no topics specified, get some from the book
            topics = analysis_data.get('topics', [])
            if not topics:
                topics = await self._extract_topics_from_book(request.book_title)
            
            # Generate questions for each topic
            all_questions = []
            for topic in topics[:3]:  # Limit to 3 topics
                questions = await self._generate_questions_for_topic(
                    request.book_title, 
                    topic, 
                    analysis_data.get('parameters', {})
                )
                all_questions.extend(questions)
            
            return QuestionResponse(
                chapter=", ".join(topics),
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
            
            # Question generation prompt
            question_prompt = ChatPromptTemplate.from_messages([
                ("system", """You are a master educator and professional exam author. Generate high-quality questions based ONLY on the provided content.

Your response MUST be a JSON array of question objects. Each question object must have:
- "difficulty": "easy", "medium", or "hard"
- "type": "multiple_choice_single_answer", "true_false", or "open_ended_question"
- "question_text": The full text of the question
- "options": Array of choices (empty array for open_ended_question)
- "answer": The correct answer as a STRING (for true/false questions use "True" or "False", not boolean values)

IMPORTANT: The "answer" field must ALWAYS be a string, never a boolean or other data type.

Generate {count} questions with varied difficulty and types. Base all questions strictly on the provided content."""),
                ("human", "Content: {content}\nTopic: {topic}\nCount: {count}")
            ])
            
            count = parameters.get('count', 2)
            chain = question_prompt | self.llm | StrOutputParser()
            
            result = await chain.ainvoke({
                "content": content,
                "topic": topic,
                "count": count
            })
            
            # Parse questions
            questions_data = json.loads(result.strip().replace('```json\n', '').replace('\n```', ''))
            
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
        """Generate lecture for a book topic"""
        try:
            # Create knowledge retriever tool
            knowledge_tool = self._create_knowledge_search_tool(request.book_title)
            
            # Create agent for lecture generation
            tools = [knowledge_tool]
            agent = create_tool_calling_agent(self.llm, tools, self.lecture_prompt)
            agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)
            
            # Generate lecture
            result = await agent_executor.ainvoke({
                "book_title": request.book_title,
                "user_message": f"Generate a lecture about {request.topic or 'main topics'}",
                "audience": request.audience or "university"
            })
            
            return result['output']
            
        except Exception as e:
            logger.error(f"Error generating lecture: {e}")
            raise

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
            # Try to get existing session
            session = await self.db.get_chat_session(session_id)
            
            if not session:
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
                
                session = await self.db.get_chat_session(new_session_id)
            
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
            
            return ChatSessionModel(**session_data)
            
        except Exception as e:
            logger.error(f"Error creating session: {e}")
            raise

    async def get_session(self, session_id: str) -> Optional[ChatSessionModel]:
        """Get session by ID"""
        try:
            session_data = await self.db.get_chat_session(session_id)
            if session_data:
                return ChatSessionModel(**session_data)
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
            # Clear memory for this session
            self.memory_manager.clear_memory(session_id)
            
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
            memory = self.memory_manager.get_memory(session_id)
            return await memory.get_memory_stats()
        except Exception as e:
            logger.error(f"Error getting memory stats: {e}")
            return {}

    async def clear_session_memory(self, session_id: str) -> bool:
        """Clear memory for a specific session"""
        try:
            self.memory_manager.clear_memory(session_id)
            return True
        except Exception as e:
            logger.error(f"Error clearing session memory: {e}")
            return False

    async def cleanup_expired_memories(self) -> Dict[str, Any]:
        """Clean up expired memories across all sessions"""
        try:
            await self.memory_manager.cleanup_all_expired()
            return {"status": "success", "message": "Expired memories cleaned up"}
        except Exception as e:
            logger.error(f"Error cleaning up expired memories: {e}")
            return {"status": "error", "message": str(e)}

    async def get_session_entities(self, session_id: str) -> Dict[str, Any]:
        """Get extracted entities for a session"""
        try:
            memory = self.memory_manager.get_memory(session_id)
            memory_vars = await memory._load_memory_variables_async({})
            return memory_vars.get("entities", {})
        except Exception as e:
            logger.error(f"Error getting session entities: {e}")
            return {}

    async def get_session_summary(self, session_id: str) -> str:
        """Get conversation summary for a session"""
        try:
            memory = self.memory_manager.get_memory(session_id)
            memory_vars = await memory._load_memory_variables_async({})
            return memory_vars.get("summary", "")
        except Exception as e:
            logger.error(f"Error getting session summary: {e}")
            return ""
