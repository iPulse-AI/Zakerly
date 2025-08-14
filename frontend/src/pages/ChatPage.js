import React, { useState, useEffect, useRef } from 'react';
import {
  Container,
  Box,
  Paper,
  TextField,
  Button,
  Typography,
  Avatar,
  Chip,
  Alert,
  CircularProgress,
  MenuItem,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  IconButton,
  Divider,
} from '@mui/material';
import {
  Send as SendIcon,
  Person as UserIcon,
  SmartToy as BotIcon,
  QuestionAnswer as QuestionIcon,
  School as LectureIcon,
  Chat as ChatIcon,
  Settings as SettingsIcon,
} from '@mui/icons-material';
import { useSearchParams, useNavigate } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import axios from 'axios';
import { v4 as uuidv4 } from 'uuid';

const ChatPage = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const messagesEndRef = useRef(null);

  // State
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [sessionId, setSessionId] = useState('');
  const [selectedBook, setSelectedBook] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('');
  const [books, setBooks] = useState([]);
  const [categories, setCategories] = useState([]);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [chatIntent, setChatIntent] = useState('answer_question');

  // Initialize
  useEffect(() => {
    initializeChat();
    fetchCategories();
  }, []);

  useEffect(() => {
    if (selectedCategory) {
      fetchBooksByCategory(selectedCategory);
    }
  }, [selectedCategory]);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const initializeChat = () => {
    // Get parameters from URL
    const bookFromUrl = searchParams.get('book');
    const categoryFromUrl = searchParams.get('category');
    
    if (bookFromUrl) {
      setSelectedBook(bookFromUrl);
    }
    if (categoryFromUrl) {
      setSelectedCategory(categoryFromUrl);
    }

    // Generate or get session ID
    const existingSessionId = sessionStorage.getItem('chatSessionId');
    if (existingSessionId) {
      setSessionId(existingSessionId);
      loadChatHistory(existingSessionId);
    } else {
      const newSessionId = uuidv4();
      setSessionId(newSessionId);
      sessionStorage.setItem('chatSessionId', newSessionId);
    }
  };

  const fetchCategories = async () => {
    try {
      const response = await axios.get('/api/v1/categories');
      setCategories(response.data);
    } catch (err) {
      console.error('Failed to fetch categories:', err);
    }
  };

  const fetchBooksByCategory = async (categoryId) => {
    try {
      const response = await axios.get(`/api/v1/books?category_id=${categoryId}`);
      setBooks(response.data);
    } catch (err) {
      console.error('Failed to fetch books:', err);
    }
  };

  const loadChatHistory = async (sessionId) => {
    try {
      const response = await axios.get(`/api/v1/sessions/${sessionId}/history`);
      const history = response.data.history || [];
      
      const formattedMessages = history.map(msg => ({
        id: uuidv4(),
        type: msg.message_type,
        content: msg.content,
        timestamp: new Date(msg.created_at),
      }));
      
      setMessages(formattedMessages);
    } catch (err) {
      console.error('Failed to load chat history:', err);
    }
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const handleSendMessage = async () => {
    if (!inputMessage.trim() || !selectedBook || !selectedCategory) {
      setError('Please select a category and book, then enter a message');
      return;
    }

    const userMessage = {
      id: uuidv4(),
      type: 'user',
      content: inputMessage,
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMessage]);
    setInputMessage('');
    setLoading(true);
    setError('');

    try {
      const response = await axios.post('/api/v1/chat', {
        category: getCategoryName(selectedCategory),
        book_title: selectedBook,
        session_id: sessionId,
        user_message: inputMessage,
        intent: chatIntent,
      });

      const botMessage = {
        id: uuidv4(),
        type: 'assistant',
        content: response.data.response,
        timestamp: new Date(),
        intent: response.data.intent,
      };

      setMessages(prev => [...prev, botMessage]);
      
    } catch (err) {
      setError('Failed to send message: ' + (err.response?.data?.detail || err.message));
    } finally {
      setLoading(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const getCategoryName = (categoryId) => {
    const category = categories.find(cat => cat.id === parseInt(categoryId));
    return category ? category.name : '';
  };

  const getIntentColor = (intent) => {
    switch (intent) {
      case 'generate_questions': return 'secondary';
      case 'generate_lecture': return 'warning';
      default: return 'primary';
    }
  };

  const getIntentIcon = (intent) => {
    switch (intent) {
      case 'generate_questions': return <QuestionIcon />;
      case 'generate_lecture': return <LectureIcon />;
      default: return <ChatIcon />;
    }
  };

  const startNewSession = () => {
    const newSessionId = uuidv4();
    setSessionId(newSessionId);
    sessionStorage.setItem('chatSessionId', newSessionId);
    setMessages([]);
    setError('');
  };

  return (
    <Container maxWidth="lg">
      <Box sx={{ py: 2, height: 'calc(100vh - 100px)', display: 'flex', flexDirection: 'column' }}>
        
        {/* Header */}
        <Paper elevation={1} sx={{ p: 2, mb: 2 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Typography variant="h5" component="h1">
              AI Chat Assistant
            </Typography>
            <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
              {selectedBook && (
                <Chip
                  label={`${getCategoryName(selectedCategory)} - ${selectedBook}`}
                  color="primary"
                  variant="outlined"
                />
              )}
              <IconButton onClick={() => setSettingsOpen(true)}>
                <SettingsIcon />
              </IconButton>
              <Button variant="outlined" size="small" onClick={startNewSession}>
                New Chat
              </Button>
            </Box>
          </Box>
        </Paper>

        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}

        {/* Chat Messages */}
        <Paper 
          elevation={1} 
          sx={{ 
            flexGrow: 1, 
            p: 2, 
            mb: 2, 
            overflow: 'auto',
            display: 'flex',
            flexDirection: 'column',
          }}
        >
          {messages.length === 0 ? (
            <Box sx={{ 
              display: 'flex', 
              flexDirection: 'column', 
              alignItems: 'center', 
              justifyContent: 'center',
              height: '100%',
              color: 'text.secondary'
            }}>
              <BotIcon sx={{ fontSize: 64, mb: 2 }} />
              <Typography variant="h6" gutterBottom>
                Welcome to Zakerly AI Chat
              </Typography>
              <Typography variant="body1" align="center">
                Select a category and book, then start chatting to get answers, 
                generate questions, or create lectures from your documents.
              </Typography>
            </Box>
          ) : (
            <Box>
              {messages.map((message) => (
                <Box
                  key={message.id}
                  sx={{
                    display: 'flex',
                    mb: 2,
                    justifyContent: message.type === 'user' ? 'flex-end' : 'flex-start',
                  }}
                >
                  <Box
                    sx={{
                      display: 'flex',
                      maxWidth: '80%',
                      flexDirection: message.type === 'user' ? 'row-reverse' : 'row',
                      alignItems: 'flex-start',
                      gap: 1,
                    }}
                  >
                    <Avatar
                      sx={{
                        bgcolor: message.type === 'user' ? 'primary.main' : 'secondary.main',
                        width: 32,
                        height: 32,
                      }}
                    >
                      {message.type === 'user' ? <UserIcon /> : <BotIcon />}
                    </Avatar>
                    
                    <Paper
                      elevation={1}
                      sx={{
                        p: 2,
                        bgcolor: message.type === 'user' ? 'primary.light' : 'grey.100',
                        color: message.type === 'user' ? 'primary.contrastText' : 'text.primary',
                      }}
                    >
                      {message.intent && message.type === 'assistant' && (
                        <Chip
                          icon={getIntentIcon(message.intent)}
                          label={message.intent.replace('_', ' ')}
                          color={getIntentColor(message.intent)}
                          size="small"
                          sx={{ mb: 1 }}
                        />
                      )}
                      
                      <ReactMarkdown>{message.content}</ReactMarkdown>
                      
                      <Typography variant="caption" sx={{ display: 'block', mt: 1, opacity: 0.7 }}>
                        {message.timestamp.toLocaleTimeString()}
                      </Typography>
                    </Paper>
                  </Box>
                </Box>
              ))}
              
              {loading && (
                <Box sx={{ display: 'flex', justifyContent: 'flex-start', mb: 2 }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <Avatar sx={{ bgcolor: 'secondary.main', width: 32, height: 32 }}>
                      <BotIcon />
                    </Avatar>
                    <Paper elevation={1} sx={{ p: 2, bgcolor: 'grey.100' }}>
                      <CircularProgress size={20} />
                      <Typography variant="body2" sx={{ ml: 1, display: 'inline' }}>
                        Thinking...
                      </Typography>
                    </Paper>
                  </Box>
                </Box>
              )}
              
              <div ref={messagesEndRef} />
            </Box>
          )}
        </Paper>

        {/* Input Area */}
        <Paper elevation={1} sx={{ p: 2 }}>
          <Box sx={{ display: 'flex', gap: 1, alignItems: 'flex-end' }}>
            <TextField
              fullWidth
              multiline
              maxRows={4}
              placeholder="Type your message..."
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              onKeyPress={handleKeyPress}
              disabled={loading || !selectedBook}
            />
            <Button
              variant="contained"
              endIcon={<SendIcon />}
              onClick={handleSendMessage}
              disabled={loading || !inputMessage.trim() || !selectedBook}
              sx={{ minWidth: 100 }}
            >
              Send
            </Button>
          </Box>
        </Paper>

        {/* Settings Dialog */}
        <Dialog open={settingsOpen} onClose={() => setSettingsOpen(false)} maxWidth="sm" fullWidth>
          <DialogTitle>Chat Settings</DialogTitle>
          <DialogContent>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
              <TextField
                select
                label="Category"
                value={selectedCategory}
                onChange={(e) => setSelectedCategory(e.target.value)}
                fullWidth
              >
                {categories.map((category) => (
                  <MenuItem key={category.id} value={category.id}>
                    {category.name}
                  </MenuItem>
                ))}
              </TextField>

              <TextField
                select
                label="Book"
                value={selectedBook}
                onChange={(e) => setSelectedBook(e.target.value)}
                fullWidth
                disabled={!selectedCategory}
              >
                {books.map((book) => (
                  <MenuItem key={book.id} value={book.title}>
                    {book.title}
                  </MenuItem>
                ))}
              </TextField>

              <Divider />

              <TextField
                select
                label="Chat Mode"
                value={chatIntent}
                onChange={(e) => setChatIntent(e.target.value)}
                fullWidth
                helperText="Choose the type of interaction you want"
              >
                <MenuItem value="answer_question">Answer Questions</MenuItem>
                <MenuItem value="generate_questions">Generate Questions</MenuItem>
                <MenuItem value="generate_lecture">Generate Lecture</MenuItem>
              </TextField>
            </Box>
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setSettingsOpen(false)}>Close</Button>
          </DialogActions>
        </Dialog>
      </Box>
    </Container>
  );
};

export default ChatPage;