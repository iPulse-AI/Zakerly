import React, { useState, useEffect } from 'react';
import { Header } from '@/components/ui/header';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { CurriculumService, ChatService } from '@/lib/services';
import { useAuth } from '@/contexts/AuthContext';
import { Curriculum, BookInCurriculum } from '@/lib/types';
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
  X,
  BookOpen,
  Target,
  FileText,
  ArrowRight,
  BarChart3,
  GraduationCap,
  User,
  Settings,
  Filter
} from 'lucide-react';

interface ScriptGenerationParams {
  curriculumId: string;
  scope: 'whole_curriculum' | 'specific_topics';
  specificBooks?: string[];
  specificTopics?: string;
  detailLevel: 'high_level' | 'detailed' | 'comprehensive';
  duration: number; // in minutes
  scriptStyle: 'lecture' | 'interactive' | 'presentation' | 'workshop';
  targetAudience: 'beginner' | 'intermediate' | 'advanced';
  includeExamples: boolean;
  includeExercises: boolean;
  includeVisualAids: boolean;
}

interface GeneratedScript {
  id?: string;
  title: string;
  content: string;
  scope: string;
  duration: number;
  style: string;
  targetAudience: string;
  createdAt: string;
  analytics?: {
    wordCount: number;
    estimatedReadingTime: number;
    complexityScore: number;
    keyTopics: string[];
  };
}

const Scripts: React.FC = () => {
  const { token } = useAuth();
  
  // State Management
  const [curriculums, setCurriculums] = useState<Curriculum[]>([]);
  const [selectedCurriculum, setSelectedCurriculum] = useState<Curriculum | null>(null);
  const [curriculumBooks, setCurriculumBooks] = useState<BookInCurriculum[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  
  // Generation Parameters
  const [generationParams, setGenerationParams] = useState<ScriptGenerationParams>({
    curriculumId: '',
    scope: 'whole_curriculum',
    specificBooks: [],
    specificTopics: '',
    detailLevel: 'detailed',
    duration: 60,
    scriptStyle: 'lecture',
    targetAudience: 'intermediate',
    includeExamples: true,
    includeExercises: false,
    includeVisualAids: true
  });
  
  // Generated Scripts
  const [generatedScripts, setGeneratedScripts] = useState<GeneratedScript[]>([]);
  const [selectedScript, setSelectedScript] = useState<GeneratedScript | null>(null);
  const [viewMode, setViewMode] = useState<'list' | 'details'>('list');
  
  // UI State
  const [currentStep, setCurrentStep] = useState(1);
  const [searchTerm, setSearchTerm] = useState('');

  // Load curriculums on component mount
  useEffect(() => {
    if (token) {
      loadCurriculums();
    }
  }, [token]);

  // Load curriculum books when curriculum is selected
  useEffect(() => {
    if (selectedCurriculum) {
      loadCurriculumBooks();
    }
  }, [selectedCurriculum]);

  const loadCurriculums = async () => {
    try {
      setLoading(true);
      const data = await CurriculumService.getUserCurriculums();
      setCurriculums(data);
    } catch (err) {
      setError('Failed to load curriculums');
      console.error('Error loading curriculums:', err);
    } finally {
      setLoading(false);
    }
  };

  const loadCurriculumBooks = async () => {
    if (!selectedCurriculum) return;
    
    try {
      const books = await CurriculumService.getCurriculumBooks(selectedCurriculum.id);
      setCurriculumBooks(books);
    } catch (err) {
      setError('Failed to load curriculum books');
      console.error('Error loading curriculum books:', err);
    }
  };

  const handleCurriculumSelect = (curriculum: Curriculum) => {
    setSelectedCurriculum(curriculum);
    setGenerationParams(prev => ({
      ...prev,
      curriculumId: curriculum.id,
      specificBooks: [],
      specificTopics: ''
    }));
    setCurrentStep(2);
  };

  const handleBookSelection = (bookId: string, selected: boolean) => {
    setGenerationParams(prev => ({
      ...prev,
      specificBooks: selected 
        ? [...(prev.specificBooks || []), bookId]
        : (prev.specificBooks || []).filter(id => id !== bookId)
    }));
  };

  const generateScript = async () => {
    if (!selectedCurriculum || !generationParams.curriculumId) {
      setError('Please select a curriculum first');
      return;
    }

    try {
      setLoading(true);
      setError(null);

      const response = await ChatService.generateCurriculumScript({
        curriculum_id: generationParams.curriculumId,
        scope: generationParams.scope,
        specific_books: generationParams.specificBooks,
        specific_topics: generationParams.specificTopics,
        detail_level: generationParams.detailLevel,
        duration: generationParams.duration,
        script_style: generationParams.scriptStyle,
        target_audience: generationParams.targetAudience,
        include_examples: generationParams.includeExamples,
        include_exercises: generationParams.includeExercises,
        include_visual_aids: generationParams.includeVisualAids
      });

      const newScript: GeneratedScript = {
        id: `script_${Date.now()}`,
        title: `${selectedCurriculum.title} - ${generationParams.scriptStyle} Script`,
        content: response.script,
        scope: generationParams.scope === 'whole_curriculum' ? 'Complete Curriculum' : 'Selected Topics',
        duration: generationParams.duration,
        style: generationParams.scriptStyle,
        targetAudience: generationParams.targetAudience,
        createdAt: new Date().toISOString(),
        analytics: response.analytics
      };

      setGeneratedScripts(prev => [newScript, ...prev]);
      setSelectedScript(newScript);
      setViewMode('details');
      setSuccess('Script generated successfully!');
      
    } catch (err: any) {
      setError(err.message || 'Failed to generate script');
      console.error('Error generating script:', err);
    } finally {
      setLoading(false);
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setSuccess('Script copied to clipboard!');
  };

  const downloadScript = (script: GeneratedScript) => {
    const element = document.createElement('a');
    const file = new Blob([script.content], { type: 'text/plain' });
    element.href = URL.createObjectURL(file);
    element.download = `${script.title.replace(/[^a-zA-Z0-9]/g, '_')}.txt`;
    document.body.appendChild(element);
    element.click();
    document.body.removeChild(element);
  };

  const getStyleIcon = (style: string) => {
    switch (style) {
      case 'lecture': return <Presentation className="w-4 h-4" />;
      case 'interactive': return <Target className="w-4 h-4" />;
      case 'presentation': return <FileText className="w-4 h-4" />;
      case 'workshop': return <Settings className="w-4 h-4" />;
      default: return <FileText className="w-4 h-4" />;
    }
  };

  const getAudienceColor = (audience: string) => {
    switch (audience) {
      case 'beginner': return 'bg-green-100 text-green-800';
      case 'intermediate': return 'bg-yellow-100 text-yellow-800';
      case 'advanced': return 'bg-red-100 text-red-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  const filteredCurriculums = curriculums.filter(curriculum =>
    curriculum.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
    curriculum.description?.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const clearAlerts = () => {
    setError(null);
    setSuccess(null);
  };

  if (viewMode === 'details' && selectedScript) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-background via-background to-accent/5">
        <Header />
        
        <div className="container mx-auto px-4 py-8">
          {/* Header */}
          <div className="flex items-center justify-between mb-8">
            <div className="flex items-center gap-4">
              <Button
                variant="outline"
                onClick={() => setViewMode('list')}
                className="flex items-center gap-2"
              >
                <ArrowRight className="w-4 h-4 rotate-180" />
                Back to Scripts
              </Button>
              <div className="flex items-center gap-2">
                <Presentation className="w-6 h-6 text-primary" />
                <h1 className="text-2xl font-bold">Script Details</h1>
              </div>
            </div>
            
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                onClick={() => copyToClipboard(selectedScript.content)}
                className="flex items-center gap-2"
              >
                <Copy className="w-4 h-4" />
                Copy
              </Button>
              <Button
                onClick={() => downloadScript(selectedScript)}
                className="flex items-center gap-2"
              >
                <Download className="w-4 h-4" />
                Download
              </Button>
            </div>
          </div>

          {/* Alerts */}
          {error && (
            <Alert className="mb-6 border-red-200 bg-red-50">
              <X className="h-4 w-4 text-red-600" />
              <AlertDescription className="text-red-800">
                {error}
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={clearAlerts}
                  className="ml-2 h-auto p-0 text-red-600 hover:text-red-800"
                >
                  <X className="w-3 h-3" />
                </Button>
              </AlertDescription>
            </Alert>
          )}

          {success && (
            <Alert className="mb-6 border-green-200 bg-green-50">
              <CheckCircle className="h-4 w-4 text-green-600" />
              <AlertDescription className="text-green-800">
                {success}
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={clearAlerts}
                  className="ml-2 h-auto p-0 text-green-600 hover:text-green-800"
                >
                  <X className="w-3 h-3" />
                </Button>
              </AlertDescription>
            </Alert>
          )}

          {/* Script Details */}
          <div className="grid lg:grid-cols-4 gap-6">
            {/* Script Metadata */}
            <div className="lg:col-span-1">
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <BarChart3 className="w-5 h-5" />
                    Script Information
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div>
                    <label className="text-sm font-medium text-muted-foreground">Style</label>
                    <div className="flex items-center gap-2 mt-1">
                      {getStyleIcon(selectedScript.style)}
                      <span className="capitalize">{selectedScript.style}</span>
                    </div>
                  </div>
                  
                  <div>
                    <label className="text-sm font-medium text-muted-foreground">Target Audience</label>
                    <Badge className={`mt-1 ${getAudienceColor(selectedScript.targetAudience)}`}>
                      {selectedScript.targetAudience}
                    </Badge>
                  </div>
                  
                  <div>
                    <label className="text-sm font-medium text-muted-foreground">Duration</label>
                    <div className="flex items-center gap-2 mt-1">
                      <Clock className="w-4 h-4" />
                      <span>{selectedScript.duration} minutes</span>
                    </div>
                  </div>
                  
                  <div>
                    <label className="text-sm font-medium text-muted-foreground">Scope</label>
                    <p className="mt-1">{selectedScript.scope}</p>
                  </div>
                  
                  {selectedScript.analytics && (
                    <>
                      <div>
                        <label className="text-sm font-medium text-muted-foreground">Word Count</label>
                        <p className="mt-1">{selectedScript.analytics.wordCount}</p>
                      </div>
                      
                      <div>
                        <label className="text-sm font-medium text-muted-foreground">Reading Time</label>
                        <p className="mt-1">{selectedScript.analytics.estimatedReadingTime} min</p>
                      </div>
                      
                      <div>
                        <label className="text-sm font-medium text-muted-foreground">Complexity Score</label>
                        <p className="mt-1">{selectedScript.analytics.complexityScore}/100</p>
                      </div>
                    </>
                  )}
                </CardContent>
              </Card>
            </div>

            {/* Script Content */}
            <div className="lg:col-span-3">
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <FileText className="w-5 h-5" />
                    {selectedScript.title}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="prose max-w-none">
                    <pre className="whitespace-pre-wrap font-sans text-sm leading-relaxed">
                      {selectedScript.content}
                    </pre>
                  </div>
                </CardContent>
              </Card>
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
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div className="flex items-center gap-2">
            <Presentation className="w-6 h-6 text-primary" />
            <h1 className="text-2xl font-bold">Lecture Scripts</h1>
          </div>
          
          {generatedScripts.length > 0 && (
            <Button
              onClick={() => {
                setCurrentStep(1);
                setSelectedCurriculum(null);
                setGenerationParams({
                  curriculumId: '',
                  scope: 'whole_curriculum',
                  specificBooks: [],
                  specificTopics: '',
                  detailLevel: 'detailed',
                  duration: 60,
                  scriptStyle: 'lecture',
                  targetAudience: 'intermediate',
                  includeExamples: true,
                  includeExercises: false,
                  includeVisualAids: true
                });
              }}
              className="flex items-center gap-2"
            >
              <Plus className="w-4 h-4" />
              Generate New Script
            </Button>
          )}
        </div>

        {/* Alerts */}
        {error && (
          <Alert className="mb-6 border-red-200 bg-red-50">
            <X className="h-4 w-4 text-red-600" />
            <AlertDescription className="text-red-800">
              {error}
              <Button
                variant="ghost"
                size="sm"
                onClick={clearAlerts}
                className="ml-2 h-auto p-0 text-red-600 hover:text-red-800"
              >
                <X className="w-3 h-3" />
              </Button>
            </AlertDescription>
          </Alert>
        )}

        {success && (
          <Alert className="mb-6 border-green-200 bg-green-50">
            <CheckCircle className="h-4 w-4 text-green-600" />
            <AlertDescription className="text-green-800">
              {success}
              <Button
                variant="ghost"
                size="sm"
                onClick={clearAlerts}
                className="ml-2 h-auto p-0 text-green-600 hover:text-green-800"
              >
                <X className="w-3 h-3" />
              </Button>
            </AlertDescription>
          </Alert>
        )}

        {/* Progress Steps */}
        <div className="mb-8">
          <div className="flex items-center justify-center space-x-8">
            {[
              { step: 1, title: 'Select Curriculum', icon: BookOpen },
              { step: 2, title: 'Configure Scope', icon: Target },
              { step: 3, title: 'Set Parameters', icon: Settings },
              { step: 4, title: 'Generate Script', icon: Sparkles }
            ].map(({ step, title, icon: Icon }) => (
              <div
                key={step}
                className={`flex items-center gap-2 ${
                  currentStep >= step
                    ? 'text-primary'
                    : 'text-muted-foreground'
                }`}
              >
                <div
                  className={`w-8 h-8 rounded-full flex items-center justify-center border-2 ${
                    currentStep >= step
                      ? 'border-primary bg-primary text-primary-foreground'
                      : 'border-muted-foreground'
                  }`}
                >
                  {currentStep > step ? (
                    <CheckCircle className="w-4 h-4" />
                  ) : (
                    <Icon className="w-4 h-4" />
                  )}
                </div>
                <span className="font-medium">{title}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Main Content */}
        {currentStep === 1 && (
          <div className="space-y-6">
            {/* Search */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Search className="w-5 h-5" />
                  Search Curriculums
                </CardTitle>
              </CardHeader>
              <CardContent>
                <Input
                  placeholder="Search curriculums by name or description..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="w-full"
                />
              </CardContent>
            </Card>

            {/* Curriculum Selection */}
            <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
              {loading ? (
                <div className="col-span-full flex items-center justify-center py-12">
                  <Loader2 className="w-8 h-8 animate-spin" />
                </div>
              ) : filteredCurriculums.length === 0 ? (
                <div className="col-span-full text-center py-12">
                  <GraduationCap className="w-12 h-12 mx-auto text-muted-foreground mb-4" />
                  <h3 className="text-lg font-medium mb-2">No Curriculums Found</h3>
                  <p className="text-muted-foreground">
                    {searchTerm ? 'No curriculums match your search.' : 'You haven\'t created any curriculums yet.'}
                  </p>
                </div>
              ) : (
                filteredCurriculums.map((curriculum) => (
                  <Card
                    key={curriculum.id}
                    className="cursor-pointer hover:shadow-md transition-shadow"
                    onClick={() => handleCurriculumSelect(curriculum)}
                  >
                    <CardHeader>
                      <CardTitle className="flex items-center gap-2">
                        <BookOpen className="w-5 h-5" />
                        {curriculum.title}
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      <p className="text-sm text-muted-foreground mb-4">
                        {curriculum.description || 'No description available'}
                      </p>
                      <div className="flex items-center justify-between">
                        <Badge variant="secondary">
                          {curriculum.book_count || 0} books
                        </Badge>
                        <ArrowRight className="w-4 h-4 text-muted-foreground" />
                      </div>
                    </CardContent>
                  </Card>
                ))
              )}
            </div>
          </div>
        )}

        {currentStep === 2 && selectedCurriculum && (
          <div className="space-y-6">
            {/* Curriculum Info */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <BookOpen className="w-5 h-5" />
                  {selectedCurriculum.title}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-muted-foreground">
                  {selectedCurriculum.description}
                </p>
              </CardContent>
            </Card>

            {/* Scope Selection */}
            <Card>
              <CardHeader>
                <CardTitle>Select Script Scope</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid md:grid-cols-2 gap-4">
                  <Card
                    className={`cursor-pointer transition-colors ${
                      generationParams.scope === 'whole_curriculum'
                        ? 'ring-2 ring-primary bg-primary/5'
                        : 'hover:bg-accent/50'
                    }`}
                    onClick={() => setGenerationParams(prev => ({ ...prev, scope: 'whole_curriculum' }))}
                  >
                    <CardContent className="p-6">
                      <div className="flex items-center gap-3 mb-3">
                        <BookOpen className="w-6 h-6 text-primary" />
                        <h3 className="font-semibold">Whole Curriculum</h3>
                      </div>
                      <p className="text-sm text-muted-foreground">
                        Generate a comprehensive script covering the entire curriculum
                      </p>
                    </CardContent>
                  </Card>

                  <Card
                    className={`cursor-pointer transition-colors ${
                      generationParams.scope === 'specific_topics'
                        ? 'ring-2 ring-primary bg-primary/5'
                        : 'hover:bg-accent/50'
                    }`}
                    onClick={() => setGenerationParams(prev => ({ ...prev, scope: 'specific_topics' }))}
                  >
                    <CardContent className="p-6">
                      <div className="flex items-center gap-3 mb-3">
                        <Target className="w-6 h-6 text-primary" />
                        <h3 className="font-semibold">Specific Topics</h3>
                      </div>
                      <p className="text-sm text-muted-foreground">
                        Generate a focused script on selected books or topics
                      </p>
                    </CardContent>
                  </Card>
                </div>

                {generationParams.scope === 'specific_topics' && (
                  <div className="space-y-4">
                    {/* Book Selection */}
                    <div>
                      <label className="text-sm font-medium mb-2 block">
                        Select Books (optional)
                      </label>
                      <div className="grid md:grid-cols-2 gap-2">
                        {curriculumBooks.map((book) => (
                          <div
                            key={book.book_id}
                            className="flex items-center space-x-2"
                          >
                            <input
                              type="checkbox"
                              id={`book-${book.book_id}`}
                              checked={generationParams.specificBooks?.includes(book.book_id) || false}
                              onChange={(e) => handleBookSelection(book.book_id, e.target.checked)}
                              className="rounded border-gray-300"
                            />
                            <label
                              htmlFor={`book-${book.book_id}`}
                              className="text-sm cursor-pointer"
                            >
                              {book.title}
                            </label>
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* Topic Input */}
                    <div>
                      <label htmlFor="topics" className="text-sm font-medium mb-2 block">
                        Specific Topics (optional)
                      </label>
                      <Textarea
                        id="topics"
                        placeholder="Enter specific topics or chapters you want to focus on..."
                        value={generationParams.specificTopics}
                        onChange={(e) => setGenerationParams(prev => ({ ...prev, specificTopics: e.target.value }))}
                        rows={3}
                      />
                    </div>
                  </div>
                )}

                <Button
                  onClick={() => setCurrentStep(3)}
                  className="w-full"
                  disabled={
                    generationParams.scope === 'specific_topics' &&
                    !generationParams.specificBooks?.length &&
                    !generationParams.specificTopics
                  }
                >
                  Continue to Parameters
                  <ArrowRight className="w-4 h-4 ml-2" />
                </Button>
              </CardContent>
            </Card>
          </div>
        )}

        {currentStep === 3 && (
          <div className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>Script Parameters</CardTitle>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="grid md:grid-cols-2 gap-6">
                  {/* Detail Level */}
                  <div>
                    <label className="text-sm font-medium mb-2 block">Detail Level</label>
                    <Select
                      value={generationParams.detailLevel}
                      onValueChange={(value: 'high_level' | 'detailed' | 'comprehensive') =>
                        setGenerationParams(prev => ({ ...prev, detailLevel: value }))
                      }
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="high_level">High Level Overview</SelectItem>
                        <SelectItem value="detailed">Detailed Explanation</SelectItem>
                        <SelectItem value="comprehensive">Comprehensive Deep Dive</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>

                  {/* Duration */}
                  <div>
                    <label className="text-sm font-medium mb-2 block">Duration (minutes)</label>
                    <Input
                      type="number"
                      min="15"
                      max="180"
                      value={generationParams.duration}
                      onChange={(e) => setGenerationParams(prev => ({ ...prev, duration: parseInt(e.target.value) || 60 }))}
                    />
                  </div>

                  {/* Script Style */}
                  <div>
                    <label className="text-sm font-medium mb-2 block">Script Style</label>
                    <Select
                      value={generationParams.scriptStyle}
                      onValueChange={(value: 'lecture' | 'interactive' | 'presentation' | 'workshop') =>
                        setGenerationParams(prev => ({ ...prev, scriptStyle: value }))
                      }
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="lecture">Traditional Lecture</SelectItem>
                        <SelectItem value="interactive">Interactive Session</SelectItem>
                        <SelectItem value="presentation">Presentation Format</SelectItem>
                        <SelectItem value="workshop">Workshop Style</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>

                  {/* Target Audience */}
                  <div>
                    <label className="text-sm font-medium mb-2 block">Target Audience</label>
                    <Select
                      value={generationParams.targetAudience}
                      onValueChange={(value: 'beginner' | 'intermediate' | 'advanced') =>
                        setGenerationParams(prev => ({ ...prev, targetAudience: value }))
                      }
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

                {/* Additional Options */}
                <div>
                  <label className="text-sm font-medium mb-3 block">Additional Options</label>
                  <div className="space-y-3">
                    <div className="flex items-center space-x-2">
                      <input
                        type="checkbox"
                        id="examples"
                        checked={generationParams.includeExamples}
                        onChange={(e) => setGenerationParams(prev => ({ ...prev, includeExamples: e.target.checked }))}
                        className="rounded border-gray-300"
                      />
                      <label htmlFor="examples" className="text-sm cursor-pointer">
                        Include practical examples
                      </label>
                    </div>
                    
                    <div className="flex items-center space-x-2">
                      <input
                        type="checkbox"
                        id="exercises"
                        checked={generationParams.includeExercises}
                        onChange={(e) => setGenerationParams(prev => ({ ...prev, includeExercises: e.target.checked }))}
                        className="rounded border-gray-300"
                      />
                      <label htmlFor="exercises" className="text-sm cursor-pointer">
                        Include exercises and activities
                      </label>
                    </div>
                    
                    <div className="flex items-center space-x-2">
                      <input
                        type="checkbox"
                        id="visual-aids"
                        checked={generationParams.includeVisualAids}
                        onChange={(e) => setGenerationParams(prev => ({ ...prev, includeVisualAids: e.target.checked }))}
                        className="rounded border-gray-300"
                      />
                      <label htmlFor="visual-aids" className="text-sm cursor-pointer">
                        Include visual aid suggestions
                      </label>
                    </div>
                  </div>
                </div>

                <Button
                  onClick={() => setCurrentStep(4)}
                  className="w-full"
                >
                  Review & Generate
                  <ArrowRight className="w-4 h-4 ml-2" />
                </Button>
              </CardContent>
            </Card>
          </div>
        )}

        {currentStep === 4 && (
          <div className="space-y-6">
            {/* Generation Summary */}
            <Card>
              <CardHeader>
                <CardTitle>Generation Summary</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid md:grid-cols-2 gap-4">
                  <div>
                    <label className="text-sm font-medium text-muted-foreground">Curriculum</label>
                    <p className="font-medium">{selectedCurriculum?.title}</p>
                  </div>
                  
                  <div>
                    <label className="text-sm font-medium text-muted-foreground">Scope</label>
                    <p className="font-medium">
                      {generationParams.scope === 'whole_curriculum' ? 'Complete Curriculum' : 'Selected Topics'}
                    </p>
                  </div>
                  
                  <div>
                    <label className="text-sm font-medium text-muted-foreground">Detail Level</label>
                    <p className="font-medium capitalize">{generationParams.detailLevel.replace('_', ' ')}</p>
                  </div>
                  
                  <div>
                    <label className="text-sm font-medium text-muted-foreground">Duration</label>
                    <p className="font-medium">{generationParams.duration} minutes</p>
                  </div>
                  
                  <div>
                    <label className="text-sm font-medium text-muted-foreground">Style</label>
                    <p className="font-medium capitalize">{generationParams.scriptStyle}</p>
                  </div>
                  
                  <div>
                    <label className="text-sm font-medium text-muted-foreground">Audience</label>
                    <Badge className={getAudienceColor(generationParams.targetAudience)}>
                      {generationParams.targetAudience}
                    </Badge>
                  </div>
                </div>

                {generationParams.scope === 'specific_topics' && (
                  <div>
                    <label className="text-sm font-medium text-muted-foreground">Selected Books</label>
                    <div className="flex flex-wrap gap-2 mt-1">
                      {generationParams.specificBooks?.map(bookId => {
                        const book = curriculumBooks.find(b => b.book_id === bookId);
                        return book ? (
                          <Badge key={bookId} variant="secondary">
                            {book.title}
                          </Badge>
                        ) : null;
                      })}
                    </div>
                  </div>
                )}

                <Button
                  onClick={generateScript}
                  disabled={loading}
                  className="w-full"
                  size="lg"
                >
                  {loading ? (
                    <>
                      <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                      Generating Script...
                    </>
                  ) : (
                    <>
                      <Sparkles className="w-4 h-4 mr-2" />
                      Generate Script
                    </>
                  )}
                </Button>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Generated Scripts List */}
        {generatedScripts.length > 0 && currentStep === 1 && (
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <h2 className="text-xl font-semibold">Generated Scripts</h2>
              <div className="flex items-center gap-2">
                <Input
                  placeholder="Search scripts..."
                  className="w-64"
                />
                <Button variant="outline" size="sm">
                  <Filter className="w-4 h-4" />
                </Button>
              </div>
            </div>

            <div className="grid gap-4">
              {generatedScripts.map((script) => (
                <Card
                  key={script.id}
                  className="cursor-pointer hover:shadow-md transition-shadow"
                  onClick={() => setSelectedScript(script)}
                >
                  <CardContent className="p-6">
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-2">
                          {getStyleIcon(script.style)}
                          <h3 className="font-semibold">{script.title}</h3>
                        </div>
                        
                        <div className="flex items-center gap-4 text-sm text-muted-foreground mb-3">
                          <div className="flex items-center gap-1">
                            <Clock className="w-4 h-4" />
                            {script.duration} min
                          </div>
                          <Badge className={getAudienceColor(script.targetAudience)}>
                            {script.targetAudience}
                          </Badge>
                          <Badge variant="outline">
                            {script.scope}
                          </Badge>
                        </div>
                        
                        {script.analytics && (
                          <div className="flex items-center gap-4 text-sm text-muted-foreground">
                            <span>{script.analytics.wordCount} words</span>
                            <span>{script.analytics.estimatedReadingTime} min read</span>
                            <span>Complexity: {script.analytics.complexityScore}/100</span>
                          </div>
                        )}
                      </div>
                      
                      <div className="flex items-center gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={(e) => {
                            e.stopPropagation();
                            copyToClipboard(script.content);
                          }}
                        >
                          <Copy className="w-4 h-4" />
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={(e) => {
                            e.stopPropagation();
                            downloadScript(script);
                          }}
                        >
                          <Download className="w-4 h-4" />
                        </Button>
                        <Button
                          size="sm"
                          onClick={(e) => {
                            e.stopPropagation();
                            setSelectedScript(script);
                            setViewMode('details');
                          }}
                        >
                          <Eye className="w-4 h-4" />
                        </Button>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        )}

        {/* Empty State */}
        {generatedScripts.length === 0 && currentStep === 1 && !loading && (
          <div className="text-center py-12">
            <Presentation className="w-16 h-16 mx-auto text-muted-foreground mb-4" />
            <h3 className="text-xl font-semibold mb-2">No Scripts Generated Yet</h3>
            <p className="text-muted-foreground mb-6">
              Create your first lecture script by selecting a curriculum and configuring your preferences.
            </p>
            <Button
              onClick={() => setCurrentStep(1)}
              className="flex items-center gap-2"
            >
              <Plus className="w-4 h-4" />
              Generate Your First Script
            </Button>
          </div>
        )}
      </div>
    </div>
  );
};

export default Scripts;
