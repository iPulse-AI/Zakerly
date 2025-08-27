import React, { useState } from 'react';
import TranscriptionUploader from '@/components/ui/transcription-uploader';
import { Header } from '@/components/ui/header';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { 
  Presentation, 
  Plus, 
  Search, 
  Download, 
  Copy, 
  Eye,
  Calendar,
  Clock,
  BookOpen,
  Sparkles,
  FileText,
  Edit,
  Trash2,
  Upload,
  Mic
} from 'lucide-react';

interface Script {
  id: string;
  title: string;
  author: string;
  book: string;
  topic: string;
  duration: number; // minutes
  difficulty: 'beginner' | 'intermediate' | 'advanced';
  content: string;
  createdDate: Date;
  lastModified: Date;
}

const sampleScripts: Script[] = [
  {
    id: '1',
    title: 'Introduction to Cognitive Psychology',
    author: 'Dr. Sarah Johnson',
    book: 'Introduction to Psychology',
    topic: 'Cognitive Processes',
    duration: 45,
    difficulty: 'beginner',
    content: 'Welcome to our exploration of cognitive psychology...',
    createdDate: new Date('2024-01-15'),
    lastModified: new Date('2024-01-16')
  },
  {
    id: '2',
    title: 'Limits and Continuity in Calculus',
    author: 'Prof. Michael Chen',
    book: 'Calculus: Early Transcendentals',
    topic: 'Mathematical Foundations',
    duration: 60,
    difficulty: 'intermediate',
    content: 'Today we will dive into the fundamental concepts of limits...',
    createdDate: new Date('2024-01-12'),
    lastModified: new Date('2024-01-14')
  },
  {
    id: '3',
    title: 'Cell Biology Fundamentals',
    author: 'Dr. Emily Rodriguez',
    book: 'Campbell Biology',
    topic: 'Cellular Structure',
    duration: 90,
    difficulty: 'advanced',
    content: 'Understanding cellular mechanisms is crucial for biology...',
    createdDate: new Date('2024-01-10'),
    lastModified: new Date('2024-01-11')
  }
];

export default function Scripts() {
  const [scripts, setScripts] = useState<Script[]>(sampleScripts);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterDifficulty, setFilterDifficulty] = useState('all');
  const [filterAuthor, setFilterAuthor] = useState('all');
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [showTranscriptionUploader, setShowTranscriptionUploader] = useState(false);
  const [selectedScript, setSelectedScript] = useState<Script | null>(null);
  const [editingScript, setEditingScript] = useState<Script | null>(null);

  const [newScript, setNewScript] = useState({
    title: '',
    author: '',
    book: '',
    topic: '',
    duration: 45,
    difficulty: 'beginner' as const,
    detailLevel: 'overview' as 'overview' | 'detailed' | 'in-depth'
  });

  const authors = Array.from(new Set(scripts.map(script => script.author)));

  const filteredScripts = scripts.filter(script => {
    const matchesSearch = script.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         script.book.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         script.author.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         script.topic.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesDifficulty = filterDifficulty === 'all' || script.difficulty === filterDifficulty;
    const matchesAuthor = filterAuthor === 'all' || script.author === filterAuthor;
    
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

  const handleCreateScript = () => {
    // Simulate script generation
    const script: Script = {
      id: Date.now().toString(),
      title: newScript.title,
      author: newScript.author,
      book: newScript.book,
      topic: newScript.topic,
      duration: newScript.duration,
      difficulty: newScript.difficulty,
      content: `Generated lecture script for "${newScript.title}" - ${newScript.detailLevel} level content covering ${newScript.topic}...`,
      createdDate: new Date(),
      lastModified: new Date()
    };
    
    setScripts([script, ...scripts]);
    setShowCreateForm(false);
    setNewScript({
      title: '',
      author: '',
      book: '',
      topic: '',
      duration: 45,
      difficulty: 'beginner',
      detailLevel: 'overview'
    });
  };

  const copyToClipboard = (content: string) => {
    navigator.clipboard.writeText(content);
  };

  const downloadScript = (script: Script) => {
    const blob = new Blob([script.content], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${script.title}.txt`;
    a.click();
  };

  const handleTranscriptionComplete = (transcription: string, metadata: { fileName: string; duration?: number; fileType: string; author?: string }) => {
    const script: Script = {
      id: Date.now().toString(),
      title: metadata.fileName.replace(/\.[^/.]+$/, ''), // Remove file extension
      author: metadata.author || 'Unknown', // Use provided author or default
      book: 'Transcribed Media',
      topic: 'Audio/Video Transcription',
      duration: metadata.duration ? Math.ceil(metadata.duration / 60) : 30, // Convert to minutes
      difficulty: 'beginner',
      content: transcription,
      createdDate: new Date(),
      lastModified: new Date()
    };
    
    setScripts([script, ...scripts]);
    setShowTranscriptionUploader(false);
  };

  const handleEditScript = (script: Script) => {
    setEditingScript(script);
  };

  const handleUpdateScript = () => {
    if (!editingScript) return;
    
    const updatedScript = {
      ...editingScript,
      lastModified: new Date()
    };
    
    setScripts(scripts.map(s => s.id === editingScript.id ? updatedScript : s));
    setEditingScript(null);
  };

  const handleDeleteScript = (scriptId: string) => {
    if (confirm('Are you sure you want to delete this script?')) {
      setScripts(scripts.filter(s => s.id !== scriptId));
    }
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
                <p className="text-muted-foreground">{selectedScript.book} • {selectedScript.topic}</p>
                <p className="text-sm text-muted-foreground">by {selectedScript.author}</p>
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
            </div>

            <Card>
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
                    Last modified: {selectedScript.lastModified.toLocaleDateString()}
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
                  <label className="text-sm font-medium">Title</label>
                  <Input
                    value={newScript.title}
                    onChange={(e) => setNewScript({...newScript, title: e.target.value})}
                    placeholder="Enter lecture title..."
                  />
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium">Author</label>
                  <Input
                    value={newScript.author}
                    onChange={(e) => setNewScript({...newScript, author: e.target.value})}
                    placeholder="Enter author name..."
                  />
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium">Book/Source</label>
                  <Select
                    value={newScript.book}
                    onValueChange={(value) => setNewScript({...newScript, book: value})}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Select a book..." />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="Introduction to Psychology">Introduction to Psychology</SelectItem>
                      <SelectItem value="Calculus: Early Transcendentals">Calculus: Early Transcendentals</SelectItem>
                      <SelectItem value="Campbell Biology">Campbell Biology</SelectItem>
                      <SelectItem value="General Chemistry">General Chemistry</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium">Topic/Chapter</label>
                  <Input
                    value={newScript.topic}
                    onChange={(e) => setNewScript({...newScript, topic: e.target.value})}
                    placeholder="Specific topic or chapter to focus on..."
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <label className="text-sm font-medium">Duration (minutes)</label>
                    <Input
                      type="number"
                      value={newScript.duration}
                      onChange={(e) => setNewScript({...newScript, duration: parseInt(e.target.value) || 45})}
                      min="15"
                      max="180"
                    />
                  </div>

                  <div className="space-y-2">
                    <label className="text-sm font-medium">Difficulty Level</label>
                    <Select
                      value={newScript.difficulty}
                      onValueChange={(value) => setNewScript({...newScript, difficulty: value as any})}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="beginner">Beginner</SelectItem>
                        <SelectItem value="intermediate">Intermediate</SelectItem>
                        <SelectItem value="advanced">Advanced</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium">Detail Level</label>
                  <Select
                    value={newScript.detailLevel}
                    onValueChange={(value) => setNewScript({...newScript, detailLevel: value as any})}
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
                  disabled={!newScript.title || !newScript.book || !newScript.topic}
                >
                  <Sparkles className="w-4 h-4 mr-2" />
                  Generate Script
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
                  <label className="text-sm font-medium">Author</label>
                  <Input
                    value={editingScript.author}
                    onChange={(e) => setEditingScript({...editingScript, author: e.target.value})}
                    placeholder="Enter author name..."
                  />
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium">Book/Source</label>
                  <Input
                    value={editingScript.book}
                    onChange={(e) => setEditingScript({...editingScript, book: e.target.value})}
                    placeholder="Enter book or source..."
                  />
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium">Topic/Chapter</label>
                  <Input
                    value={editingScript.topic}
                    onChange={(e) => setEditingScript({...editingScript, topic: e.target.value})}
                    placeholder="Specific topic or chapter..."
                  />
                </div>

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
                    <label className="text-sm font-medium">Difficulty Level</label>
                    <Select
                      value={editingScript.difficulty}
                      onValueChange={(value) => setEditingScript({...editingScript, difficulty: value as any})}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="beginner">Beginner</SelectItem>
                        <SelectItem value="intermediate">Intermediate</SelectItem>
                        <SelectItem value="advanced">Advanced</SelectItem>
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
                    onClick={handleUpdateScript}
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

  if (showTranscriptionUploader) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-background via-background to-accent/5">
        <Header />
        
        <div className="container mx-auto px-4 py-8">
          <div className="max-w-4xl mx-auto">
            <TranscriptionUploader
              onTranscriptionComplete={handleTranscriptionComplete}
              onClose={() => setShowTranscriptionUploader(false)}
            />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-background via-background to-accent/5">
      <Header />
      
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
              <Button 
                onClick={() => setShowTranscriptionUploader(true)}
                variant="outline"
                className="border-primary text-primary hover:bg-primary/10"
              >
                <Mic className="w-4 h-4 mr-2" />
                Transcribe Media
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
                  <div className="text-2xl font-bold text-primary">{scripts.length}</div>
                  <div className="text-sm text-muted-foreground">Total Scripts</div>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="text-center">
                  <div className="text-2xl font-bold text-secondary">
                    {Math.round(scripts.reduce((sum, s) => sum + s.duration, 0) / scripts.length) || 0}
                  </div>
                  <div className="text-sm text-muted-foreground">Avg Duration (min)</div>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="text-center">
                  <div className="text-2xl font-bold text-accent">
                    {new Set(scripts.map(s => s.book)).size}
                  </div>
                  <div className="text-sm text-muted-foreground">Books Covered</div>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="text-center">
                  <div className="text-2xl font-bold text-success">
                    {scripts.reduce((sum, s) => sum + s.duration, 0)}
                  </div>
                  <div className="text-sm text-muted-foreground">Total Hours</div>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Scripts Grid */}
          {filteredScripts.length === 0 ? (
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
                      <div className="flex-1">
                        <CardTitle className="text-lg leading-tight mb-1">{script.title}</CardTitle>
                        <p className="text-sm text-muted-foreground">{script.book}</p>
                        <p className="text-xs text-muted-foreground">by {script.author}</p>
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
                      <Badge variant="secondary">{script.topic}</Badge>
                      <Badge className={getDifficultyColor(script.difficulty)}>
                        {script.difficulty}
                      </Badge>
                    </div>
                    
                    <div className="flex items-center justify-between text-sm text-muted-foreground">
                      <div className="flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        <span>{script.duration} minutes</span>
                      </div>
                      <span>{script.createdDate.toLocaleDateString()}</span>
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