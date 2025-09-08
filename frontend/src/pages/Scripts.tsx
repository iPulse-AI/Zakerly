import React, { useState, useEffect } from 'react';
import { Header } from '@/components/ui/header';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { BooksService, ChatService, ScriptsService } from '@/lib/services';
import { useAuth } from '@/contexts/AuthContext';
import { LectureScript, LectureScriptRequest, LectureScriptUpdate } from '@/lib/types';
import { 
  Presentation, 
  Plus, 
  Search, 
  Download, 
  Copy, 
  Eye,
  Clock,
  Sparkles,
  Edit,
  Trash2,
  Loader2,
  CheckCircle,
  X
} from 'lucide-react';

interface Category {
  id: number;
  name: string;
  created_at: string;
}

interface Book {
  id: number;
  category_id: number;
  title: string;
  author?: string;
  publication_year?: number;
  file_hash: string;
  file_name: string;
  created_at: string;
}

export default function Scripts() {
  const { user } = useAuth();
  const [scripts, setScripts] = useState<LectureScript[]>([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterDifficulty, setFilterDifficulty] = useState('all');
  const [filterAuthor, setFilterAuthor] = useState('all');
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [selectedScript, setSelectedScript] = useState<LectureScript | null>(null);
  const [editingScript, setEditingScript] = useState<LectureScript | null>(null);
  const [showSuccessNotification, setShowSuccessNotification] = useState(false);
  
  // Database data
  const [categories, setCategories] = useState<Category[]>([]);
  const [books, setBooks] = useState<Book[]>([]);
  const [filteredBooks, setFilteredBooks] = useState<Book[]>([]);
  const [loading, setLoading] = useState(false);
  const [categoriesLoading, setCategoriesLoading] = useState(true);
  const [booksLoading, setBooksLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [scriptsLoading, setScriptsLoading] = useState(true);

  const [newScript, setNewScript] = useState({
    categoryId: '',
    bookId: '',
    title: '',
    scope: 'whole_book' as 'whole_book' | 'specific_topics',
    specificTopics: '',
    detailLevel: 'overview' as 'overview' | 'detailed' | 'in-depth'
  });

  const authors = Array.from(new Set(scripts.map(script => script.book_title || 'Unknown')));

  // Fetch data on component mount
  useEffect(() => {
    fetchCategories();
    fetchBooks();
    if (user?.sub) {
      fetchUserScripts();
    }
  }, [user?.sub]);

  // Filter books when category changes
  useEffect(() => {
    if (newScript.categoryId) {
      const filtered = books.filter(book => book.category_id.toString() === newScript.categoryId);
      setFilteredBooks(filtered);
    } else {
      setFilteredBooks(books);
    }
  }, [newScript.categoryId, books]);

  const fetchCategories = async () => {
    try {
      setCategoriesLoading(true);
      const data = await BooksService.getCategories();
      setCategories(data);
    } catch (error) {
      console.error('Error fetching categories:', error);
    } finally {
      setCategoriesLoading(false);
    }
  };

  const fetchBooks = async () => {
    try {
      setBooksLoading(true);
      const data = await BooksService.getBooks();
      setBooks(data);
      setFilteredBooks(data);
    } catch (error) {
      console.error('Error fetching books:', error);
    } finally {
      setBooksLoading(false);
    }
  };

  const fetchUserScripts = async () => {
    if (!user?.sub) return;
    
    try {
      setScriptsLoading(true);
      const data = await ScriptsService.getUserScripts(user.sub);
      setScripts(data);
    } catch (error) {
      console.error('Error fetching user scripts:', error);
    } finally {
      setScriptsLoading(false);
    }
  };

  const getSelectedCategory = () => {
    return categories.find(cat => cat.id.toString() === newScript.categoryId);
  };

  const getSelectedBook = () => {
    return books.find(book => book.id.toString() === newScript.bookId);
  };

  const filteredScripts = scripts.filter(script => {
    const matchesSearch = script.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         (script.book_title || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
                         (script.specific_topics || '').toLowerCase().includes(searchTerm.toLowerCase());
    const matchesDifficulty = filterDifficulty === 'all' || script.difficulty === filterDifficulty;
    const matchesAuthor = filterAuthor === 'all' || (script.book_title || 'Unknown') === filterAuthor;
    
    return matchesSearch && matchesDifficulty && matchesAuthor;
  });

  const getDifficultyColor = (difficulty: string) => {
    switch (difficulty) {
      case 'beginner': return 'bg-green-100 text-green-800';
      case 'intermediate': return 'bg-yellow-100 text-yellow-800';
      case 'advanced': return 'bg-red-100 text-red-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  const handleCreateScript = async () => {
    if (!user?.sub) {
      console.error('User not authenticated:', user);
      alert('User not authenticated. Please log in.');
      return;
    }
    
    console.log('Starting script generation for user:', user.sub);
    setGenerating(true);
    try {
      const selectedCategory = getSelectedCategory();
      const selectedBook = getSelectedBook();
      
      if (!selectedCategory || !selectedBook) {
        alert('Please select both category and book');
        return;
      }

      if (!newScript.title.trim()) {
        alert('Please enter a lecture title');
        return;
      }

      if (newScript.scope === 'specific_topics' && !newScript.specificTopics.trim()) {
        alert('Please specify the topics for focused lecture');
        return;
      }

      // Prepare the lecture request with all parameters
      const lectureRequest = {
        book_title: selectedBook.title,
        user_message: `Generate a comprehensive ${newScript.detailLevel} lecture script titled "${newScript.title}" for the ${selectedCategory.name} category. ${
          newScript.scope === 'specific_topics' 
            ? `Focus specifically on these topics: ${newScript.specificTopics}` 
            : 'Cover the entire book content comprehensively.'
        }`,
        category: selectedCategory.name,
        title: newScript.title,
        scope: newScript.scope,
        specific_topics: newScript.scope === 'specific_topics' ? newScript.specificTopics : undefined,
        detail_level: newScript.detailLevel
      };

      console.log('Generating lecture with request:', lectureRequest);

      // Generate lecture using ChatService
      const data = await ChatService.generateLecture(lectureRequest);
      
      // Create script request for database
      const scriptRequest: LectureScriptRequest = {
        book_id: selectedBook.id,
        title: newScript.title,
        scope: newScript.scope,
        specific_topics: newScript.scope === 'specific_topics' ? newScript.specificTopics : undefined,
        detail_level: newScript.detailLevel,
        difficulty: newScript.detailLevel === 'overview' ? 'beginner' : newScript.detailLevel === 'detailed' ? 'intermediate' : 'advanced',
        duration: newScript.detailLevel === 'overview' ? 30 : newScript.detailLevel === 'detailed' ? 60 : 90,
        content: data.lecture || 'Generated lecture content...'
      };
      
      // Save script to database
      const savedScript = await ScriptsService.createScript(user.sub, scriptRequest);
      
      // Add book title for display
      const scriptWithBookTitle = {
        ...savedScript,
        book_title: selectedBook.title
      };
      
      setScripts([scriptWithBookTitle, ...scripts]);
      setShowCreateForm(false);
      setNewScript({
        categoryId: '',
        bookId: '',
        title: '',
        scope: 'whole_book',
        specificTopics: '',
        detailLevel: 'overview'
      });

      // Show success notification
      setShowSuccessNotification(true);
      setTimeout(() => setShowSuccessNotification(false), 5000);
      
    } catch (error) {
      console.error('Error generating lecture:', error);
      
      // Enhanced error handling with more details
      let errorMessage = 'Failed to generate lecture. Please try again.';
      
      if (error instanceof Error) {
        console.error('Error details:', error.message);
        errorMessage = `Failed to generate lecture: ${error.message}`;
      }
      
      if (error && typeof error === 'object' && 'response' in error) {
        console.error('API Error response:', error);
      }
      
      alert(errorMessage);
    } finally {
      setGenerating(false);
    }
  };

  const handleEditScript = (script: LectureScript) => {
    setEditingScript(script);
  };

  const handleSaveEdit = async () => {
    if (!editingScript || !user?.sub) return;
    
    try {
      const updateRequest: LectureScriptUpdate = {
        title: editingScript.title,
        content: editingScript.content,
        scope: editingScript.scope,
        specific_topics: editingScript.specific_topics,
        detail_level: editingScript.detail_level,
        difficulty: editingScript.difficulty,
        duration: editingScript.duration
      };
      
      const updatedScript = await ScriptsService.updateScript(editingScript.id, user.sub, updateRequest);
      
      // Update local state
      setScripts(scripts.map(script => 
        script.id === editingScript.id ? { ...updatedScript, book_title: script.book_title } : script
      ));
      setEditingScript(null);
      
    } catch (error) {
      console.error('Error updating script:', error);
      alert('Failed to update script. Please try again.');
    }
  };

  const handleDeleteScript = async (id: string) => {
    if (!user?.sub) return;
    
    try {
      await ScriptsService.deleteScript(id, user.sub);
      setScripts(scripts.filter(script => script.id !== id));
    } catch (error) {
      console.error('Error deleting script:', error);
      alert('Failed to delete script. Please try again.');
    }
  };

  const copyToClipboard = (content: string) => {
    navigator.clipboard.writeText(content);
  };

  const downloadScript = (script: LectureScript) => {
    const blob = new Blob([script.content], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${script.title}.txt`;
    a.click();
  };

  if (selectedScript) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-background via-background to-accent/5">
        <Header />
        
        <div className="container mx-auto px-4 py-8">
          <div className="max-w-4xl mx-auto">
              <div className="flex items-center gap-4 mb-6">
                <Button 
                  variant="outline" 
                  onClick={() => setSelectedScript(null)}
                >
                  ← Back to Scripts
                </Button>
                <div className="flex-1">
                  <h1 className="text-2xl font-bold">{selectedScript.title}</h1>
                  <p className="text-muted-foreground">{selectedScript.book_title} • {selectedScript.scope === 'specific_topics' ? selectedScript.specific_topics : 'Whole Book'}</p>
                  <p className="text-sm text-muted-foreground">by {user?.full_name || 'User'}</p>
                </div>
                <div className="flex gap-2">
                  <Button variant="outline" onClick={() => copyToClipboard(selectedScript.content)}>
                    <Copy className="w-4 h-4 mr-2" />
                    Copy
                  </Button>
                  <Button variant="outline" onClick={() => downloadScript(selectedScript)}>
                    <Download className="w-4 h-4 mr-2" />
                    Download
                  </Button>
                </div>
              </div>            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <Badge className={getDifficultyColor(selectedScript.difficulty)}>
                        {selectedScript.difficulty}
                      </Badge>
                      <Badge variant="outline">
                        <Clock className="w-3 h-3 mr-1" />
                        {selectedScript.duration} min
                      </Badge>
                    </div>
                  </div>
                  <div className="text-sm text-muted-foreground">
                    Last modified: {new Date(selectedScript.updated_at).toLocaleDateString()}
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                <div className="prose max-w-none">
                  <div className="whitespace-pre-wrap text-base leading-relaxed">
                    {selectedScript.content}
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    );
  }

  if (showCreateForm) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-background via-background to-accent/5">
        <Header />
        
        <div className="container mx-auto px-4 py-8">
          <div className="max-w-2xl mx-auto">
            <div className="flex items-center gap-4 mb-6">
              <Button 
                variant="outline" 
                onClick={() => setShowCreateForm(false)}
              >
                ← Back to Scripts
              </Button>
              <h1 className="text-2xl font-bold">Create New Lecture Script</h1>
            </div>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Sparkles className="w-5 h-5 text-primary" />
                  Script Configuration
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="space-y-2">
                  <label className="text-sm font-medium">Category</label>
                  <Select
                    value={newScript.categoryId}
                    onValueChange={(value) => setNewScript({...newScript, categoryId: value, bookId: ''})}
                    disabled={categoriesLoading}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder={categoriesLoading ? "Loading categories..." : "Select a category..."} />
                    </SelectTrigger>
                    <SelectContent>
                      {categories.map((category) => (
                        <SelectItem key={category.id} value={category.id.toString()}>
                          {category.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium">Book</label>
                  <Select
                    value={newScript.bookId}
                    onValueChange={(value) => setNewScript({...newScript, bookId: value})}
                    disabled={!newScript.categoryId || booksLoading || filteredBooks.length === 0}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder={
                        !newScript.categoryId 
                          ? "Select a category first..." 
                          : booksLoading 
                            ? "Loading books..."
                            : filteredBooks.length === 0 
                              ? "No books available in this category"
                              : "Select a book..."
                      } />
                    </SelectTrigger>
                    <SelectContent>
                      {filteredBooks.map((book) => (
                        <SelectItem key={book.id} value={book.id.toString()}>
                          {book.title} {book.author && `by ${book.author}`}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium">Title</label>
                  <Input
                    value={newScript.title}
                    onChange={(e) => setNewScript({...newScript, title: e.target.value})}
                    placeholder="Enter lecture title..."
                  />
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium">Scope</label>
                  <Select
                    value={newScript.scope}
                    onValueChange={(value) => setNewScript({...newScript, scope: value as 'whole_book' | 'specific_topics'})}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="whole_book">Whole Book</SelectItem>
                      <SelectItem value="specific_topics">Specific Topics</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                {newScript.scope === 'specific_topics' && (
                  <div className="space-y-2">
                    <label className="text-sm font-medium">Specific Topics</label>
                    <Textarea
                      value={newScript.specificTopics}
                      onChange={(e) => setNewScript({...newScript, specificTopics: e.target.value})}
                      placeholder="Enter specific topics separated by commas..."
                      rows={3}
                    />
                  </div>
                )}

                <div className="space-y-2">
                  <label className="text-sm font-medium">Detail Level</label>
                  <Select
                    value={newScript.detailLevel}
                    onValueChange={(value) => setNewScript({...newScript, detailLevel: value as 'overview' | 'detailed' | 'in-depth'})}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="overview">Overview - High-level concepts</SelectItem>
                      <SelectItem value="detailed">Detailed - Comprehensive coverage</SelectItem>
                      <SelectItem value="in-depth">In-depth - Extensive analysis</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <Button 
                  onClick={handleCreateScript}
                  className="w-full bg-gradient-primary"
                  disabled={!newScript.categoryId || !newScript.bookId || !newScript.title || generating}
                >
                  {generating ? (
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  ) : (
                    <Sparkles className="w-4 h-4 mr-2" />
                  )}
                  {generating ? 'Generating Lecture...' : 'Generate Lecture'}
                </Button>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    );
  }

  if (editingScript) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-background via-background to-accent/5">
        <Header />
        
        <div className="container mx-auto px-4 py-8">
          <div className="max-w-2xl mx-auto">
            <div className="flex items-center gap-4 mb-6">
              <Button 
                variant="outline" 
                onClick={() => setEditingScript(null)}
              >
                ← Back to Scripts
              </Button>
              <h1 className="text-2xl font-bold">Edit Script</h1>
            </div>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Edit className="w-5 h-5 text-primary" />
                  Edit Script Details
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="space-y-2">
                  <label className="text-sm font-medium">Title</label>
                  <Input
                    value={editingScript.title}
                    onChange={(e) => setEditingScript({...editingScript, title: e.target.value})}
                    placeholder="Enter lecture title..."
                  />
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium">Scope</label>
                  <Select
                    value={editingScript.scope}
                    onValueChange={(value) => setEditingScript({...editingScript, scope: value as 'whole_book' | 'specific_topics'})}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="whole_book">Whole Book</SelectItem>
                      <SelectItem value="specific_topics">Specific Topics</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                {editingScript.scope === 'specific_topics' && (
                  <div className="space-y-2">
                    <label className="text-sm font-medium">Specific Topics</label>
                    <Input
                      value={editingScript.specific_topics || ''}
                      onChange={(e) => setEditingScript({...editingScript, specific_topics: e.target.value})}
                      placeholder="Specific topics..."
                    />
                  </div>
                )}

                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <label className="text-sm font-medium">Duration (minutes)</label>
                    <Input
                      type="number"
                      value={editingScript.duration}
                      onChange={(e) => setEditingScript({...editingScript, duration: parseInt(e.target.value) || 45})}
                      min="15"
                      max="180"
                    />
                  </div>

                  <div className="space-y-2">
                    <label className="text-sm font-medium">Detail Level</label>
                    <Select
                      value={editingScript.detail_level}
                      onValueChange={(value) => setEditingScript({...editingScript, detail_level: value as 'overview' | 'detailed' | 'in-depth'})}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="overview">Overview</SelectItem>
                        <SelectItem value="detailed">Detailed</SelectItem>
                        <SelectItem value="in-depth">In-depth</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium">Content</label>
                  <Textarea
                    value={editingScript.content}
                    onChange={(e) => setEditingScript({...editingScript, content: e.target.value})}
                    placeholder="Script content..."
                    rows={10}
                  />
                </div>

                <div className="flex gap-2">
                  <Button 
                    onClick={handleSaveEdit}
                    className="flex-1 bg-gradient-primary"
                    disabled={!editingScript.title || !editingScript.content}
                  >
                    <Edit className="w-4 h-4 mr-2" />
                    Update Script
                  </Button>
                  <Button 
                    variant="outline"
                    onClick={() => setEditingScript(null)}
                  >
                    Cancel
                  </Button>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-background via-background to-accent/5">
      <Header />
      
      {/* Success Notification */}
      {showSuccessNotification && (
        <div className="fixed top-4 right-4 z-50 animate-in slide-in-from-top-2">
          <Alert className="w-96 bg-green-50 border-green-200 text-green-800 shadow-lg">
            <CheckCircle className="h-4 w-4 text-green-600" />
            <AlertDescription className="font-medium">
              <div className="flex items-center justify-between">
                <span>Lecture script generated successfully!</span>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-6 w-6 text-green-600 hover:text-green-800"
                  onClick={() => setShowSuccessNotification(false)}
                >
                  <X className="h-3 w-3" />
                </Button>
              </div>
            </AlertDescription>
          </Alert>
        </div>
      )}
      
      <div className="container mx-auto px-4 py-8">
        <div className="max-w-6xl mx-auto">
          {/* Header Section */}
          <div className="flex items-center justify-between mb-8">
            <div>
              <h1 className="text-3xl font-bold text-gradient-primary mb-2">
                Lecture Scripts
              </h1>
              <p className="text-muted-foreground">
                AI-generated lecture scripts for presentations and teaching
              </p>
            </div>
            <div className="flex gap-3">
              <Button 
                onClick={() => setShowCreateForm(true)}
                className="bg-gradient-primary"
              >
                <Plus className="w-4 h-4 mr-2" />
                Create Script
              </Button>
            </div>
          </div>

          {/* Filters and Search */}
          <Card className="mb-6">
            <CardContent className="pt-6">
              <div className="flex flex-col md:flex-row gap-4">
                <div className="flex-1 relative">
                  <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                  <Input
                    placeholder="Search scripts by title, book, author, or topic..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    className="pl-10"
                  />
                </div>
                <Select value={filterDifficulty} onValueChange={setFilterDifficulty}>
                  <SelectTrigger className="w-full md:w-48">
                    <SelectValue placeholder="Filter by difficulty" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Difficulties</SelectItem>
                    <SelectItem value="beginner">Beginner</SelectItem>
                    <SelectItem value="intermediate">Intermediate</SelectItem>
                    <SelectItem value="advanced">Advanced</SelectItem>
                  </SelectContent>
                </Select>
                <Select value={filterAuthor} onValueChange={setFilterAuthor}>
                  <SelectTrigger className="w-full md:w-48">
                    <SelectValue placeholder="Filter by author" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Authors</SelectItem>
                    {authors.map(author => (
                      <SelectItem key={author} value={author}>{author}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </CardContent>
          </Card>

          {/* Stats Cards */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
            <Card>
              <CardContent className="pt-6">
                <div className="text-center">
                  <div className="text-2xl font-bold text-primary">{filteredScripts.length}</div>
                  <div className="text-sm text-muted-foreground">Your Scripts</div>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="text-center">
                  <div className="text-2xl font-bold text-secondary">
                    {Math.round(filteredScripts.reduce((sum, s) => sum + s.duration, 0) / filteredScripts.length) || 0}
                  </div>
                  <div className="text-sm text-muted-foreground">Avg Duration (min)</div>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="text-center">
                  <div className="text-2xl font-bold text-accent">
                    {new Set(filteredScripts.map(s => s.book_title)).size}
                  </div>
                  <div className="text-sm text-muted-foreground">Books Covered</div>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="text-center">
                  <div className="text-2xl font-bold text-success">
                    {Math.round(filteredScripts.reduce((sum, s) => sum + s.duration, 0) / 60)}
                  </div>
                  <div className="text-sm text-muted-foreground">Total Hours</div>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Scripts Grid */}
          {scriptsLoading ? (
            <Card>
              <CardContent className="pt-8 pb-8">
                <div className="text-center">
                  <Loader2 className="w-16 h-16 text-muted-foreground mx-auto mb-4 animate-spin" />
                  <h3 className="text-lg font-semibold mb-2">Loading your scripts...</h3>
                  <p className="text-muted-foreground">Please wait while we fetch your lecture scripts</p>
                </div>
              </CardContent>
            </Card>
          ) : filteredScripts.length === 0 ? (
            <Card>
              <CardContent className="pt-8 pb-8">
                <div className="text-center">
                  <Presentation className="w-16 h-16 text-muted-foreground mx-auto mb-4" />
                  <h3 className="text-lg font-semibold mb-2">No scripts found</h3>
                  <p className="text-muted-foreground mb-4">
                    {searchTerm || filterDifficulty !== 'all' || filterAuthor !== 'all'
                      ? 'Try adjusting your search or filters'
                      : 'Create your first lecture script to get started'}
                  </p>
                  <Button onClick={() => setShowCreateForm(true)}>
                    <Plus className="w-4 h-4 mr-2" />
                    Create Script
                  </Button>
                </div>
              </CardContent>
            </Card>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {filteredScripts.map((script) => (
                <Card key={script.id} className="hover:shadow-lg transition-shadow duration-200">
                  <CardHeader className="pb-3">
                    <div className="flex items-start justify-between">
                      <div className="flex-1 min-w-0">
                        <CardTitle className="text-lg leading-tight mb-1 break-words">{script.title}</CardTitle>
                        <p className="text-sm text-muted-foreground truncate">{script.book_title}</p>
                        <p className="text-xs text-muted-foreground truncate">by {user?.full_name || 'User'}</p>
                      </div>
                      <div className="flex gap-1 ml-2">
                        <Button 
                          variant="ghost" 
                          size="icon" 
                          className="w-8 h-8"
                          onClick={() => handleEditScript(script)}
                        >
                          <Edit className="w-3 h-3" />
                        </Button>
                        <Button 
                          variant="ghost" 
                          size="icon" 
                          className="w-8 h-8 text-destructive hover:text-destructive"
                          onClick={() => handleDeleteScript(script.id)}
                        >
                          <Trash2 className="w-3 h-3" />
                        </Button>
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="flex items-center justify-between">
                      <Badge variant="secondary">{script.scope === 'specific_topics' ? script.specific_topics : 'Whole Book'}</Badge>
                      <Badge className={getDifficultyColor(script.difficulty)}>
                        {script.difficulty}
                      </Badge>
                    </div>
                    
                    <div className="flex items-center justify-between text-sm text-muted-foreground">
                      <div className="flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        <span>{script.duration} minutes</span>
                      </div>
                      <span>{new Date(script.created_at).toLocaleDateString()}</span>
                    </div>
                    
                    <div className="flex gap-2 pt-2">
                      <Button 
                        variant="outline" 
                        size="sm" 
                        className="flex-1"
                        onClick={() => setSelectedScript(script)}
                      >
                        <Eye className="w-3 h-3 mr-2" />
                        View
                      </Button>
                      <Button 
                        variant="outline" 
                        size="sm" 
                        onClick={() => copyToClipboard(script.content)}
                      >
                        <Copy className="w-3 h-3" />
                      </Button>
                      <Button 
                        variant="outline" 
                        size="sm" 
                        onClick={() => downloadScript(script)}
                      >
                        <Download className="w-3 h-3" />
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}