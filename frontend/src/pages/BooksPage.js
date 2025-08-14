import React, { useState, useEffect } from 'react';
import {
  Container,
  Typography,
  Box,
  Grid,
  Card,
  CardContent,
  CardActions,
  Button,
  Chip,
  TextField,
  MenuItem,
  Alert,
  CircularProgress,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  IconButton,
} from '@mui/material';
import {
  Book as BookIcon,
  Chat as ChatIcon,
  Delete as DeleteIcon,
  Search as SearchIcon,
  Person as AuthorIcon,
  DateRange as DateIcon,
  Category as CategoryIcon,
} from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';

const BooksPage = () => {
  const navigate = useNavigate();
  const [books, setBooks] = useState([]);
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('');
  const [deleteDialog, setDeleteDialog] = useState({ open: false, book: null });

  useEffect(() => {
    fetchData();
  }, [selectedCategory]);

  const fetchData = async () => {
    try {
      setLoading(true);
      
      // Fetch categories
      const categoriesResponse = await axios.get('/api/v1/categories');
      setCategories(categoriesResponse.data);

      // Fetch books
      const booksUrl = selectedCategory 
        ? `/api/v1/books?category_id=${selectedCategory}`
        : '/api/v1/books';
      const booksResponse = await axios.get(booksUrl);
      setBooks(booksResponse.data);
      
    } catch (err) {
      setError('Failed to fetch data: ' + (err.response?.data?.detail || err.message));
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteBook = async (book) => {
    try {
      await axios.delete(`/api/v1/books/${book.id}`);
      setBooks(books.filter(b => b.id !== book.id));
      setDeleteDialog({ open: false, book: null });
    } catch (err) {
      setError('Failed to delete book: ' + (err.response?.data?.detail || err.message));
    }
  };

  const handleStartChat = (book) => {
    // Create a new chat session for this book
    navigate(`/chat?book=${encodeURIComponent(book.title)}&category=${book.category_id}`);
  };

  const filteredBooks = books.filter(book =>
    book.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
    (book.author && book.author.toLowerCase().includes(searchTerm.toLowerCase()))
  );

  const getCategoryName = (categoryId) => {
    const category = categories.find(cat => cat.id === categoryId);
    return category ? category.name : 'Unknown';
  };

  const getCategoryColor = (categoryId) => {
    const colors = {
      1: 'primary',    // math
      2: 'secondary',  // science
      3: 'success',    // physics
      4: 'warning',    // chemistry
      5: 'info',       // history
      6: 'error',      // geology
      7: 'default',    // general
    };
    return colors[categoryId] || 'default';
  };

  if (loading) {
    return (
      <Container maxWidth="lg">
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
          <CircularProgress size={60} />
        </Box>
      </Container>
    );
  }

  return (
    <Container maxWidth="lg">
      <Box sx={{ py: 4 }}>
        <Typography variant="h2" component="h1" gutterBottom align="center">
          Document Library
        </Typography>
        <Typography variant="body1" align="center" sx={{ mb: 4, color: 'text.secondary' }}>
          Browse and manage your uploaded documents
        </Typography>

        {error && (
          <Alert severity="error" sx={{ mb: 3 }}>
            {error}
          </Alert>
        )}

        {/* Filters */}
        <Box sx={{ mb: 4, display: 'flex', gap: 2, flexWrap: 'wrap' }}>
          <TextField
            label="Search books..."
            variant="outlined"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            InputProps={{
              startAdornment: <SearchIcon sx={{ mr: 1, color: 'text.secondary' }} />,
            }}
            sx={{ minWidth: 300 }}
          />
          
          <TextField
            select
            label="Category"
            value={selectedCategory}
            onChange={(e) => setSelectedCategory(e.target.value)}
            sx={{ minWidth: 200 }}
          >
            <MenuItem value="">All Categories</MenuItem>
            {categories.map((category) => (
              <MenuItem key={category.id} value={category.id}>
                {category.name}
              </MenuItem>
            ))}
          </TextField>
        </Box>

        {/* Books Grid */}
        {filteredBooks.length === 0 ? (
          <Box sx={{ textAlign: 'center', py: 8 }}>
            <BookIcon sx={{ fontSize: 64, color: 'text.secondary', mb: 2 }} />
            <Typography variant="h5" color="text.secondary" gutterBottom>
              No books found
            </Typography>
            <Typography variant="body1" color="text.secondary" sx={{ mb: 3 }}>
              {searchTerm || selectedCategory 
                ? 'Try adjusting your search criteria'
                : 'Upload your first document to get started'
              }
            </Typography>
            <Button
              variant="contained"
              onClick={() => navigate('/upload')}
              startIcon={<BookIcon />}
            >
              Upload Document
            </Button>
          </Box>
        ) : (
          <Grid container spacing={3}>
            {filteredBooks.map((book) => (
              <Grid item xs={12} sm={6} md={4} key={book.id}>
                <Card
                  elevation={2}
                  sx={{
                    height: '100%',
                    display: 'flex',
                    flexDirection: 'column',
                    transition: 'transform 0.2s, box-shadow 0.2s',
                    '&:hover': {
                      transform: 'translateY(-2px)',
                      boxShadow: 4,
                    },
                  }}
                >
                  <CardContent sx={{ flexGrow: 1 }}>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 2 }}>
                      <Chip
                        label={getCategoryName(book.category_id)}
                        color={getCategoryColor(book.category_id)}
                        size="small"
                      />
                      <IconButton
                        size="small"
                        onClick={() => setDeleteDialog({ open: true, book })}
                        sx={{ color: 'error.main' }}
                      >
                        <DeleteIcon />
                      </IconButton>
                    </Box>
                    
                    <Typography variant="h6" component="h3" gutterBottom noWrap>
                      {book.title}
                    </Typography>
                    
                    {book.author && (
                      <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                        <AuthorIcon sx={{ fontSize: 16, mr: 1, color: 'text.secondary' }} />
                        <Typography variant="body2" color="text.secondary" noWrap>
                          {book.author}
                        </Typography>
                      </Box>
                    )}
                    
                    {book.publication_year && (
                      <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                        <DateIcon sx={{ fontSize: 16, mr: 1, color: 'text.secondary' }} />
                        <Typography variant="body2" color="text.secondary">
                          {book.publication_year}
                        </Typography>
                      </Box>
                    )}
                    
                    <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                      <CategoryIcon sx={{ fontSize: 16, mr: 1, color: 'text.secondary' }} />
                      <Typography variant="body2" color="text.secondary" noWrap>
                        {book.file_name}
                      </Typography>
                    </Box>
                    
                    <Typography variant="caption" color="text.secondary">
                      Uploaded: {new Date(book.created_at).toLocaleDateString()}
                    </Typography>
                  </CardContent>
                  
                  <CardActions sx={{ p: 2, pt: 0 }}>
                    <Button
                      fullWidth
                      variant="contained"
                      startIcon={<ChatIcon />}
                      onClick={() => handleStartChat(book)}
                    >
                      Start Chat
                    </Button>
                  </CardActions>
                </Card>
              </Grid>
            ))}
          </Grid>
        )}

        {/* Delete Confirmation Dialog */}
        <Dialog
          open={deleteDialog.open}
          onClose={() => setDeleteDialog({ open: false, book: null })}
        >
          <DialogTitle>Delete Book</DialogTitle>
          <DialogContent>
            <Typography>
              Are you sure you want to delete "{deleteDialog.book?.title}"? 
              This action cannot be undone and will also delete all associated chat sessions.
            </Typography>
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setDeleteDialog({ open: false, book: null })}>
              Cancel
            </Button>
            <Button
              onClick={() => handleDeleteBook(deleteDialog.book)}
              color="error"
              variant="contained"
            >
              Delete
            </Button>
          </DialogActions>
        </Dialog>
      </Box>
    </Container>
  );
};

export default BooksPage;