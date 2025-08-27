import React, { useState, useRef, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Header } from '@/components/ui/header';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Textarea } from '@/components/ui/textarea';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Send, BookOpen, Download, Copy, ExternalLink, Loader2, AlertCircle, ArrowLeft, Brain } from 'lucide-react';
import { cn } from '@/lib/utils';
import { BooksService, ChatService, SessionService, Utils } from '@/lib/services';
import type { Book as BookType, ChatMessage, ChatSession, ChatResponse } from '@/lib/types';

interface Message {
  id: string;
  type: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  metadata?: any;
}

export default function Chat() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const bookParam = searchParams.get('book');
  
  const [books, setBooks] = useState<BookType[]>([]);
  const [selectedBook, setSelectedBook] = useState<string>('');
  const [messages, setMessages] = useState<Message[]>([]);
  const [currentMessage, setCurrentMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isLoadingBooks, setIsLoadingBooks] = useState(true);
  const [error, setError] = useState('');
  const [currentSession, setCurrentSession] = useState<ChatSession | null>(null);
  
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const userId = Utils.generateUserId();

  const selectedBookData = books.find(book => book.title === selectedBook);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Load books on component mount
  useEffect(() => {
    loadBooks();
  }, []);

  // Set selected book from URL param
  useEffect(() => {
    if (bookParam && books.length > 0) {
      const decodedBook = decodeURIComponent(bookParam);
      const book = books.find(b => b.title === decodedBook);
      if (book) {
        setSelectedBook(book.title);
        loadChatSession(book.title);
      }
    }
  }, [bookParam, books]);

  const loadBooks = async () => {
    try {
      setIsLoadingBooks(true);
      const booksData = await BooksService.getBooks();
      setBooks(booksData);
    } catch (err) {
      console.error('Error loading books:', err);
      setError('Failed to load books');
    } finally {
      setIsLoadingBooks(false);
    }
  };

  const loadChatSession = async (bookTitle: string) => {
    try {
      // Try to get existing sessions for this user and book
      const sessions = await SessionService.getUserSessions(userId);
      const existingSession = sessions.find(session => 
        session.session_name?.includes(bookTitle) || session.book_id
      );

      if (existingSession) {
        setCurrentSession(existingSession);
        const history = await SessionService.getChatHistory(existingSession.id);
        const formattedMessages: Message[] = history.history.map(msg => ({
          id: msg.id.toString(),
          type: msg.message_type,
          content: msg.content,
          timestamp: new Date(msg.created_at),
          metadata: msg.metadata
        }));
        setMessages(formattedMessages);
      }
    } catch (err) {
      console.error('Error loading chat session:', err);
      // Continue without existing session
    }
  };

  const handleBookChange = async (bookTitle: string) => {
    setSelectedBook(bookTitle);
    setMessages([]);
    setCurrentSession(null);
    
    // Update URL
    const params = new URLSearchParams();
    params.set('book', encodeURIComponent(bookTitle));
    navigate(`/chat?${params.toString()}`, { replace: true });
    
    // Load session for this book
    await loadChatSession(bookTitle);
  };

  const handleSendMessage = async () => {
    if (!currentMessage.trim() || !selectedBook || isLoading) return;

    const book = selectedBookData;
    if (!book) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      type: 'user',
      content: currentMessage,
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMessage]);
    const messageToSend = currentMessage;
    setCurrentMessage('');
    setIsLoading(true);
    setError('');

    try {
      // Create session if needed
      let sessionId = currentSession?.id || '';
      if (!currentSession) {
        const newSession = await SessionService.createSession(
          userId,
          book.title,
          `Chat with ${book.title}`
        );
        setCurrentSession(newSession);
        sessionId = newSession.id;
      }

      // Send chat request
      const chatRequest = {
        category: Utils.getCategoryName(book.category_id),
        book_title: book.title,
        session_id: sessionId,
        user_message: messageToSend,
        intent: 'answer_question'
      };

      const response = await ChatService.sendMessage(chatRequest);

      const aiMessage: Message = {
        id: (Date.now() + 1).toString(),
        type: 'assistant',
        content: response.response,
        timestamp: new Date(),
        metadata: response.metadata
      };

      setMessages(prev => [...prev, aiMessage]);

    } catch (err) {
      console.error('Error sending message:', err);
      setError(err instanceof Error ? err.message : 'Failed to send message');
      
      // Add error message to chat
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        type: 'assistant',
        content: 'I apologize, but I encountered an error processing your message. Please try again.',
        timestamp: new Date(),
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const exportChat = () => {
    const chatContent = messages.map(msg => 
      `[${msg.timestamp.toLocaleTimeString()}] ${msg.type === 'user' ? 'You' : 'AI'}: ${msg.content}`
    ).join('\n\n');
    
    const blob = new Blob([chatContent], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `chat-${selectedBookData?.title || 'conversation'}.txt`;
    a.click();
  };

  const copyToClipboard = () => {
    const chatContent = messages.map(msg => 
      `${msg.type === 'user' ? 'You' : 'AI'}: ${msg.content}`
    ).join('\n\n');
    
    navigator.clipboard.writeText(chatContent);
  };

  if (isLoadingBooks) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-background via-background to-accent/5">
        <Header />
        <div className="container mx-auto px-4 py-8">
          <div className="flex items-center justify-center h-64">
            <div className="text-center">
              <Loader2 className="w-8 h-8 animate-spin mx-auto mb-4 text-primary" />
              <p className="text-muted-foreground">Loading your books...</p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-background via-background to-accent/5">
      <Header />
      
      <div className="container mx-auto px-4 py-8">
        <div className="max-w-4xl mx-auto">
          {/* Header Section */}
          <div className="flex items-center gap-4 mb-8">
            <Button 
              variant="outline" 
              onClick={() => navigate('/books')}
              className="flex items-center gap-2"
            >
              <ArrowLeft className="w-4 h-4" />
              Back to Library
            </Button>
            <div>
              <h1 className="text-3xl font-bold text-gradient-primary mb-2">
                Chat with Your Books
              </h1>
              <p className="text-muted-foreground">
                Ask questions and get AI-powered insights from your academic materials
              </p>
            </div>
          </div>

          {books.length === 0 ? (
            <Card>
              <CardContent className="pt-8 pb-8">
                <div className="text-center">
                  <BookOpen className="w-16 h-16 text-muted-foreground mx-auto mb-4" />
                  <h3 className="text-lg font-semibold mb-2">No books available</h3>
                  <p className="text-muted-foreground mb-4">
                    Add some books to your library first to start chatting with them.
                  </p>
                  <Button onClick={() => navigate('/books/add')} className="bg-gradient-primary">
                    Add Your First Book
                  </Button>
                </div>
              </CardContent>
            </Card>
          ) : (
            <>
              {/* Book Selection */}
              <Card className="mb-6">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <BookOpen className="w-5 h-5 text-primary" />
                    Select a Book
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <Select value={selectedBook} onValueChange={handleBookChange}>
                    <SelectTrigger className="w-full">
                      <SelectValue placeholder="Choose a book to chat with..." />
                    </SelectTrigger>
                    <SelectContent>
                      {books.map((book) => (
                        <SelectItem key={book.id} value={book.title}>
                          <div className="flex flex-col">
                            <span className="font-medium">{book.title}</span>
                            <span className="text-sm text-muted-foreground">
                              {book.author ? `by ${book.author}` : 'Author unknown'}
                            </span>
                          </div>
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  
                  {selectedBookData && (
                    <div className="mt-4 p-4 bg-primary/5 rounded-lg border border-primary/20">
                      <div className="flex items-center gap-3">
                        <div className="w-12 h-16 bg-gradient-to-br from-primary to-secondary rounded shadow-sm flex items-center justify-center">
                          <BookOpen className="w-6 h-6 text-white" />
                        </div>
                        <div>
                          <h3 className="font-semibold">{selectedBookData.title}</h3>
                          <p className="text-sm text-muted-foreground">
                            {selectedBookData.author ? `by ${selectedBookData.author}` : 'Author unknown'}
                          </p>
                          <div className="flex gap-2 mt-1">
                            <Badge variant="secondary">
                              {Utils.getCategoryName(selectedBookData.category_id)}
                            </Badge>
                            <Badge variant="outline" className="text-xs">
                              <Brain className="w-3 h-3 mr-1" />
                              AI Enhanced
                            </Badge>
                          </div>
                        </div>
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* Error Alert */}
              {error && (
                <Alert variant="destructive" className="mb-6">
                  <AlertCircle className="w-4 h-4" />
                  <AlertDescription>{error}</AlertDescription>
                </Alert>
              )}

              {/* Chat Interface */}
              {selectedBook && (
                <Card className="h-[600px] flex flex-col">
                  <CardHeader className="border-b">
                    <div className="flex items-center justify-between">
                      <CardTitle>Chat Session</CardTitle>
                      <div className="flex gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={copyToClipboard}
                          disabled={messages.length === 0}
                        >
                          <Copy className="w-4 h-4 mr-2" />
                          Copy
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={exportChat}
                          disabled={messages.length === 0}
                        >
                          <Download className="w-4 h-4 mr-2" />
                          Export
                        </Button>
                      </div>
                    </div>
                  </CardHeader>
                  
                  <CardContent className="flex-1 flex flex-col p-0">
                    {/* Messages Area */}
                    <ScrollArea className="flex-1 p-6">
                      {messages.length === 0 ? (
                        <div className="flex items-center justify-center h-full text-center">
                          <div className="space-y-3">
                            <div className="w-16 h-16 bg-gradient-to-br from-primary to-secondary rounded-full flex items-center justify-center mx-auto">
                              <Brain className="w-8 h-8 text-white" />
                            </div>
                            <h3 className="text-lg font-semibold">Start Your Conversation</h3>
                            <p className="text-muted-foreground max-w-md">
                              Ask questions about "{selectedBookData?.title}", request explanations, or explore specific topics in detail.
                            </p>
                          </div>
                        </div>
                      ) : (
                        <div className="space-y-6">
                          {messages.map((message) => (
                            <div
                              key={message.id}
                              className={cn(
                                'flex gap-3',
                                message.type === 'user' ? 'justify-end' : 'justify-start'
                              )}
                            >
                              <div
                                className={cn(
                                  'max-w-[80%] rounded-lg px-4 py-3',
                                  message.type === 'user'
                                    ? 'bg-primary text-primary-foreground'
                                    : 'bg-muted border'
                                )}
                              >
                                <p className="whitespace-pre-wrap">{message.content}</p>
                                {message.metadata && (
                                  <div className="mt-2 flex items-center gap-1 text-xs opacity-75">
                                    <ExternalLink className="w-3 h-3" />
                                    <span>Contains external information</span>
                                  </div>
                                )}
                                <div className="text-xs opacity-50 mt-2">
                                  {message.timestamp.toLocaleTimeString()}
                                </div>
                              </div>
                            </div>
                          ))}
                          
                          {isLoading && (
                            <div className="flex gap-3">
                              <div className="max-w-[80%] rounded-lg px-4 py-3 bg-muted border">
                                <div className="flex items-center gap-2">
                                  <div className="flex gap-1">
                                    <div className="w-2 h-2 bg-primary rounded-full animate-pulse"></div>
                                    <div className="w-2 h-2 bg-primary rounded-full animate-pulse delay-75"></div>
                                    <div className="w-2 h-2 bg-primary rounded-full animate-pulse delay-150"></div>
                                  </div>
                                  <span className="text-sm text-muted-foreground">AI is thinking...</span>
                                </div>
                              </div>
                            </div>
                          )}
                          
                          <div ref={messagesEndRef} />
                        </div>
                      )}
                    </ScrollArea>
                    
                    {/* Input Area */}
                    <div className="border-t p-4">
                      <div className="flex gap-3">
                        <Textarea
                          ref={textareaRef}
                          value={currentMessage}
                          onChange={(e) => setCurrentMessage(e.target.value)}
                          onKeyDown={handleKeyPress}
                          placeholder="Ask a question about the book..."
                          className="min-h-[60px] resize-none"
                          disabled={isLoading}
                        />
                        <Button
                          onClick={handleSendMessage}
                          disabled={!currentMessage.trim() || isLoading}
                          className="px-6"
                        >
                          {isLoading ? (
                            <Loader2 className="w-4 h-4 animate-spin" />
                          ) : (
                            <Send className="w-4 h-4" />
                          )}
                        </Button>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
