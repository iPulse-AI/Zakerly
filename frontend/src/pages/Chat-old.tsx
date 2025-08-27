import React, { useState, useRef, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Header } from '@/components/ui/header';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Textarea } from '@/components/ui/textarea';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Send, BookOpen, Download, Copy, ExternalLink, Loader2, AlertCircle, ArrowLeft } from 'lucide-react';
import { cn } from '@/lib/utils';
import { BooksService, ChatService, SessionService, Utils } from '@/lib/services';
import type { Book, ChatMessage, ChatSession, ChatResponse } from '@/lib/types';

interface Message {
  id: string;
  type: 'user' | 'ai';
  content: string;
  timestamp: Date;
  hasExternalInfo?: boolean;
}

interface Book {
  id: string;
  title: string;
  author: string;
  subject: string;
}

const sampleBooks: Book[] = [
  { id: '1', title: 'Introduction to Psychology', author: 'David G. Myers', subject: 'Psychology' },
  { id: '2', title: 'Calculus: Early Transcendentals', author: 'James Stewart', subject: 'Mathematics' },
  { id: '3', title: 'The Elements of Style', author: 'William Strunk Jr.', subject: 'Writing' },
  { id: '4', title: 'Organic Chemistry', author: 'Paula Yurkanis Bruice', subject: 'Chemistry' },
  { id: '5', title: 'A Brief History of Time', author: 'Stephen Hawking', subject: 'Physics' },
];

export default function Chat() {
  const [selectedBook, setSelectedBook] = useState<string>('');
  const [messages, setMessages] = useState<Message[]>([]);
  const [currentMessage, setCurrentMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const selectedBookData = sampleBooks.find(book => book.id === selectedBook);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSendMessage = async () => {
    if (!currentMessage.trim() || !selectedBook) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      type: 'user',
      content: currentMessage,
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMessage]);
    setCurrentMessage('');
    setIsLoading(true);

    // Simulate AI response
    setTimeout(() => {
      const aiMessage: Message = {
        id: (Date.now() + 1).toString(),
        type: 'ai',
        content: `Based on "${selectedBookData?.title}", I can help you understand this concept. This appears to be related to the core principles discussed in Chapter 3 of the book. Would you like me to elaborate on any specific aspect?`,
        timestamp: new Date(),
        hasExternalInfo: Math.random() > 0.7, // Randomly add external info flag for demo
      };
      setMessages(prev => [...prev, aiMessage]);
      setIsLoading(false);
    }, 1500);
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

  return (
    <div className="min-h-screen bg-gradient-to-br from-background via-background to-accent/5">
      <Header />
      
      <div className="container mx-auto px-4 py-8">
        <div className="max-w-4xl mx-auto">
          {/* Header Section */}
          <div className="mb-8">
            <h1 className="text-3xl font-bold text-gradient-primary mb-2">
              Chat with Your Books
            </h1>
            <p className="text-muted-foreground">
              Ask questions and get AI-powered insights from your academic materials
            </p>
          </div>

          {/* Book Selection */}
          <Card className="mb-6">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <BookOpen className="w-5 h-5 text-primary" />
                Select a Book
              </CardTitle>
            </CardHeader>
            <CardContent>
              <Select value={selectedBook} onValueChange={setSelectedBook}>
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Choose a book to chat with..." />
                </SelectTrigger>
                <SelectContent>
                  {sampleBooks.map((book) => (
                    <SelectItem key={book.id} value={book.id}>
                      <div className="flex flex-col">
                        <span className="font-medium">{book.title}</span>
                        <span className="text-sm text-muted-foreground">by {book.author}</span>
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
                      <p className="text-sm text-muted-foreground">by {selectedBookData.author}</p>
                      <Badge variant="secondary" className="mt-1">
                        {selectedBookData.subject}
                      </Badge>
                    </div>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

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
                          <BookOpen className="w-8 h-8 text-white" />
                        </div>
                        <h3 className="text-lg font-semibold">Start Your Conversation</h3>
                        <p className="text-muted-foreground max-w-md">
                          Ask questions about the book content, request explanations, or explore specific topics in detail.
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
                            {message.hasExternalInfo && (
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
                      <Send className="w-4 h-4" />
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}