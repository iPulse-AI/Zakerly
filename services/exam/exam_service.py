import logging
from typing import List, Optional, Dict, Any
import json
import os
import asyncio
from datetime import datetime

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.embeddings import OllamaEmbeddings
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from pydantic import BaseModel, Field

import sys
sys.path.append('/app/shared')

from models import (
    QuestionGenerationRequest, QuestionResponse, Question
)
from database import DatabaseManager
from utils import RedisManager

logger = logging.getLogger(__name__)

class ExamService:
    def __init__(self, db_manager: DatabaseManager, redis_manager: RedisManager):
        self.db = db_manager
        self.redis = redis_manager
        
        # Initialize LangChain components
        self.embeddings = OllamaEmbeddings(
            model=os.getenv("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text:latest"),
            base_url=os.getenv("OLLAMA_BASE_URL")
        )
        
        # Primary LLM (Google Gemini)
        gemini_model = os.getenv("CHAT_MODEL_NAME", "gemini-pro")
        try:
            self.llm = ChatGoogleGenerativeAI(
                model=gemini_model,
                temperature=float(os.getenv("CHAT_MODEL_TEMPERATURE", "0.7")),
                google_api_key=os.getenv("GOOGLE_API_KEY"),
                top_k=40,
                top_p=0.8,
                max_tokens=2048
            )
        except Exception as llm_init_error:
            logger.warning(f"⚠️ Primary LLM initialization failed: {llm_init_error}")
            self.llm = ChatGoogleGenerativeAI(
                model=gemini_model,
                temperature=0.7,
                google_api_key=os.getenv("GOOGLE_API_KEY")
            )
        
        self.connection_string = os.getenv("DATABASE_URL")
        
        # Initialize prompts
        self._setup_prompts()
    
    def _setup_prompts(self):
        """Setup prompt templates for question generation"""
        
        # Question generation prompt
        self.question_generation_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert educational content creator specializing in generating high-quality exam questions. Your task is to create comprehensive, challenging, and pedagogically sound questions based on the provided content.

**Instructions:**
1. Generate {count} questions based on the provided content
2. Question types should be: {question_types}
3. Difficulty levels should be: {difficulty}
4. Include specific topics: {specific_topics}
5. Time limit consideration: {time_limit} minutes total

**Question Format Requirements:**
- Each question must be clear and unambiguous
- Multiple choice questions should have 4 options (A, B, C, D)
- Only one correct answer per question
- Distractors should be plausible but clearly incorrect
- Questions should test understanding, not just memorization

**Content Context:**
Subject: {subject}
Curriculum: {curriculum_name}
Book/Material: {book_title}

**Source Material:**
{content}

**Output Format:**
Return ONLY a JSON array of questions in this exact format:
[
  {
    "difficulty": "medium",
    "type": "multiple_choice_single_answer", 
    "question_text": "What is the primary purpose of...",
    "options": ["Option A", "Option B", "Option C", "Option D"],
    "answer": "Option A"
  }
]

Generate exactly {count} questions covering the key concepts from the provided content."""),
            ("human", "Generate {count} exam questions for {subject} covering: {topics}")
        ])

    async def generate_questions(self, request: QuestionGenerationRequest) -> QuestionResponse:
        """Generate questions using AI for curriculum, book, or topic-specific exams"""
        try:
            logger.info(f"🎯 EXAM SERVICE: Question generation started")
            logger.info(f"Request: curriculum_id={request.curriculum_id}, book={request.book_title}, scope={request.scope_type}")
            
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
                
                # Generate curriculum-wide questions
                all_questions = await self._generate_curriculum_questions(
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
                curriculum_name = book_info.get('curriculum_name') if book_info else 'General Studies'
                
                # Generate book-specific questions
                all_questions = await self._generate_book_questions(
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
                
                # Get curriculum context
                book_title = request.book_title or 'General Book'
                book_info = await self._get_book_curriculum_info(book_title)
                curriculum_name = book_info.get('curriculum_name') if book_info else 'General Studies'
                
                # Generate topic-specific questions
                all_questions = await self._generate_topic_questions(
                    book_title, curriculum_name, request.specific_topics, exam_parameters
                )
                
                logger.info(f"✅ Generated {len(all_questions)} questions for topics: {request.specific_topics}")
                
                return QuestionResponse(
                    chapter=f"{book_title} - {request.specific_topics}",
                    questions_generated=all_questions
                )
            
            else:
                # Fallback: Default generation
                logger.info("🔄 FALLBACK: Using default generation")
                book_title = request.book_title or 'General Content'
                book_info = await self._get_book_curriculum_info(book_title)
                curriculum_name = book_info.get('curriculum_name') if book_info else 'General Studies'
                
                all_questions = await self._generate_book_questions(
                    book_title, curriculum_name, exam_parameters
                )
                
                return QuestionResponse(
                    chapter=f"{book_title} - General Exam",
                    questions_generated=all_questions
                )
            
        except Exception as e:
            logger.error(f"❌ Error in question generation: {e}")
            raise

    async def _generate_curriculum_questions(self, curriculum_name: str, exam_parameters: Dict[str, Any]) -> List[Question]:
        """Generate questions for entire curriculum"""
        try:
            # Get curriculum content chunks
            chunks = await self._get_curriculum_content_chunks(curriculum_name, limit=20)
            
            if not chunks:
                return self._generate_default_questions(exam_parameters, [curriculum_name])
            
            # Combine content for question generation
            content = "\n\n".join([chunk.get('content', '') for chunk in chunks])
            
            # Generate questions using LLM
            questions = await self._generate_questions_with_llm(
                content=content,
                curriculum_name=curriculum_name,
                subject=curriculum_name,
                book_title="Curriculum Content",
                topics=f"Comprehensive {curriculum_name} topics",
                exam_parameters=exam_parameters
            )
            
            return questions[:exam_parameters.get('count', 10)]
            
        except Exception as e:
            logger.error(f"Error generating curriculum questions: {e}")
            return self._generate_default_questions(exam_parameters, [curriculum_name])

    async def _generate_book_questions(self, book_title: str, curriculum_name: str, exam_parameters: Dict[str, Any]) -> List[Question]:
        """Generate questions for specific book"""
        try:
            # Get book content chunks
            chunks = await self._get_book_content_chunks(book_title, curriculum_name, limit=15)
            
            if not chunks:
                return self._generate_default_questions(exam_parameters, [book_title])
            
            # Combine content for question generation
            content = "\n\n".join([chunk.get('content', '') for chunk in chunks])
            
            # Generate questions using LLM
            questions = await self._generate_questions_with_llm(
                content=content,
                curriculum_name=curriculum_name,
                subject=f"{curriculum_name} - {book_title}",
                book_title=book_title,
                topics=f"Content from {book_title}",
                exam_parameters=exam_parameters
            )
            
            return questions[:exam_parameters.get('count', 10)]
            
        except Exception as e:
            logger.error(f"Error generating book questions: {e}")
            return self._generate_default_questions(exam_parameters, [book_title])

    async def _generate_topic_questions(self, book_title: str, curriculum_name: str, topics: str, exam_parameters: Dict[str, Any]) -> List[Question]:
        """Generate questions for specific topics"""
        try:
            # Search for content related to specific topics
            chunks = await self._search_topic_content(curriculum_name, topics, limit=10)
            
            if not chunks:
                return self._generate_default_questions(exam_parameters, [topics])
            
            # Combine content for question generation
            content = "\n\n".join([chunk.get('content', '') for chunk in chunks])
            
            # Generate questions using LLM
            questions = await self._generate_questions_with_llm(
                content=content,
                curriculum_name=curriculum_name,
                subject=f"{curriculum_name} - {topics}",
                book_title=book_title,
                topics=topics,
                exam_parameters=exam_parameters
            )
            
            return questions[:exam_parameters.get('count', 10)]
            
        except Exception as e:
            logger.error(f"Error generating topic questions: {e}")
            return self._generate_default_questions(exam_parameters, [topics])

    async def _generate_questions_with_llm(self, content: str, curriculum_name: str, subject: str, 
                                         book_title: str, topics: str, exam_parameters: Dict[str, Any]) -> List[Question]:
        """Generate questions using LLM"""
        try:
            chain = self.question_generation_prompt | self.llm | StrOutputParser()
            
            response = await chain.ainvoke({
                "count": exam_parameters.get('count', 10),
                "question_types": ", ".join(exam_parameters.get('question_types', ['multiple_choice_single_answer'])),
                "difficulty": ", ".join(exam_parameters.get('difficulty', ['medium'])),
                "specific_topics": exam_parameters.get('specific_topics', ''),
                "time_limit": exam_parameters.get('time_limit', 30),
                "subject": subject,
                "curriculum_name": curriculum_name,
                "book_title": book_title,
                "content": content[:8000],  # Limit content size
                "topics": topics
            })
            
            # Parse the JSON response
            questions_data = self._parse_questions_response(response)
            
            # Convert to Question objects
            questions = []
            for q_data in questions_data:
                question = Question(
                    difficulty=q_data.get('difficulty', 'medium'),
                    type=q_data.get('type', 'multiple_choice_single_answer'),
                    question_text=q_data.get('question_text', ''),
                    options=q_data.get('options', []),
                    answer=q_data.get('answer', '')
                )
                questions.append(question)
            
            return questions
            
        except Exception as e:
            logger.error(f"Error generating questions with LLM: {e}")
            return []

    def _parse_questions_response(self, response: str) -> List[Dict[str, Any]]:
        """Parse LLM response to extract questions"""
        try:
            # Clean the response
            response = response.strip()
            
            # Find JSON array in response
            start_idx = response.find('[')
            end_idx = response.rfind(']')
            
            if start_idx != -1 and end_idx != -1:
                json_str = response[start_idx:end_idx+1]
                return json.loads(json_str)
            
            return []
            
        except Exception as e:
            logger.error(f"Error parsing questions response: {e}")
            return []

    async def _get_curriculum_content_chunks(self, curriculum_name: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Get content chunks from curriculum"""
        try:
            return await self.db.search_curriculum_embeddings(curriculum_name, "comprehensive content", limit)
        except Exception as e:
            logger.error(f"Error getting curriculum chunks: {e}")
            return []

    async def _get_book_content_chunks(self, book_title: str, curriculum_name: str, limit: int = 15) -> List[Dict[str, Any]]:
        """Get content chunks from specific book"""
        try:
            # Get book info
            book_info = await self.db.get_book_by_title(book_title)
            if not book_info:
                return []
            
            book_id = book_info['id']
            return await self.db.search_book_specific_embeddings(curriculum_name, book_id, "book content", limit)
        except Exception as e:
            logger.error(f"Error getting book chunks: {e}")
            return []

    async def _search_topic_content(self, curriculum_name: str, topics: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search for content related to specific topics"""
        try:
            return await self.db.search_curriculum_embeddings(curriculum_name, topics, limit)
        except Exception as e:
            logger.error(f"Error searching topic content: {e}")
            return []

    async def _get_book_curriculum_info(self, book_title: str) -> Optional[Dict[str, Any]]:
        """Get curriculum information for a book"""
        try:
            return await self.db.get_book_by_title(book_title)
        except Exception as e:
            logger.error(f"Error getting book curriculum info: {e}")
            return None

    def _generate_default_questions(self, exam_parameters: Dict[str, Any], topics: List[str]) -> List[Question]:
        """Generate default fallback questions"""
        try:
            questions = []
            count = exam_parameters.get('count', 5)
            difficulty = exam_parameters.get('difficulty', ['medium'])[0]
            
            for i in range(min(count, len(topics) * 2)):
                topic = topics[i % len(topics)]
                question = Question(
                    difficulty=difficulty,
                    type="multiple_choice_single_answer",
                    question_text=f"What is a key concept related to {topic}?",
                    options=[
                        f"Primary aspect of {topic}",
                        f"Secondary feature of {topic}",
                        f"Alternative approach to {topic}",
                        f"Unrelated concept"
                    ],
                    answer=f"Primary aspect of {topic}"
                )
                questions.append(question)
            
            return questions[:count]
            
        except Exception as e:
            logger.error(f"Error generating default questions: {e}")
            return []