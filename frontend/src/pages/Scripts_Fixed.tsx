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
import { Curriculum, Book } from '@/lib/types';
import { 
  Presentation, 
  Plus, 
  Search, 
  Download, 
  Copy, 
  Eye,
  Clock,
  Sparkles,
  Loader2,
  CheckCircle,
  X,
  BookOpen,
  Target,
  FileText,
  ArrowRight,
  BarChart3,
  GraduationCap,
  Settings,
  Filter
} from 'lucide-react';

interface ScriptGenerationParams {
  curriculumId: number;
  scope: 'whole_curriculum' | 'whole_book' | 'specific_topics';
  specificBooks?: number[];
  specificTopics?: string;
  detailLevel: 'high_level' | 'detailed' | 'comprehensive';
  duration: number;
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

export default function Scripts() {
  const { token } = useAuth();
  
  // State Management
  const [curriculums, setCurriculums] = useState<Curriculum[]>([]);
  const [selectedCurriculum, setSelectedCurriculum] = useState<Curriculum | null>(null);
  const [curriculumBooks, setCurriculumBooks] = useState<Book[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  
  // UI State - IMPORTANT: This controls what page is shown
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [currentStep, setCurrentStep] = useState(1);
  const [searchTerm, setSearchTerm] = useState('');
  
  // Generation Parameters
  const [generationParams, setGenerationParams] = useState<ScriptGenerationParams>({
    curriculumId: 0,
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

  // Load data on component mount
  useEffect(() => {
    loadCurriculums();
  }, []);

  // Load curriculum books when curriculum is selected
  useEffect(() => {
    if (selectedCurriculum) {
      loadCurriculumBooks();
    }
  }, [selectedCurriculum]);

  const loadCurriculums = async () => {
    try {
      setLoading(true);
      const data = await CurriculumService.getCurriculums();
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
      setLoading(true);
      const books = await CurriculumService.getCurriculumBooks(selectedCurriculum.id);
      setCurriculumBooks(books);
    } catch (err) {
      setError('Failed to load curriculum books');
      console.error('Error loading curriculum books:', err);
    } finally {
      setLoading(false);
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

  const generateScript = async () => {
    if (!selectedCurriculum) {
      setError('Please select a curriculum first.');
      return;
    }

    // Validate scope-specific requirements
    if (generationParams.scope === 'whole_book' && (!generationParams.specificBooks || generationParams.specificBooks.length === 0)) {
      setError('Please select a book for the whole book scope.');
      return;
    }

    if (generationParams.scope === 'specific_topics' && (!generationParams.specificTopics || generationParams.specificTopics.trim() === '')) {
      setError('Please enter specific topics for the specific topics scope.');
      return;
    }

    try {
      setLoading(true);
      setError(null);

      let scopeDescription = '';
      if (generationParams.scope === 'whole_curriculum') {
        scopeDescription = 'Complete curriculum coverage';
      } else if (generationParams.scope === 'whole_book' && generationParams.specificBooks?.length) {
        const selectedBook = curriculumBooks.find(book => book.id === generationParams.specificBooks![0]);
        scopeDescription = `Focus on book: ${selectedBook?.title || 'Selected book'}`;
      } else if (generationParams.scope === 'specific_topics' && generationParams.specificTopics) {
        scopeDescription = `Focus on topics: ${generationParams.specificTopics}`;
      }

      // Create the script generation request
      const scriptRequest = {
        curriculum_id: generationParams.curriculumId,
        title: `${scopeDescription} Script`,
        scope: generationParams.scope,
        specific_books: generationParams.scope === 'whole_book' ? generationParams.specificBooks : null,
        specific_topics: generationParams.scope === 'specific_topics' ? generationParams.specificTopics : null,
        detail_level: generationParams.detailLevel,
        difficulty: generationParams.targetAudience,
        duration: generationParams.duration
      };

      const response = await ChatService.generateCurriculumScript(scriptRequest);

      if (!response || !response.script_content) {
        throw new Error('No script content received from server');
      }

      const newScript: GeneratedScript = {
        id: `script_${Date.now()}`,
        title: response.title || `${selectedCurriculum?.name || 'Curriculum'} - Script`,
        content: response.script_content || 'Script generated successfully',
        scope: scopeDescription,
        duration: generationParams.duration,
        style: generationParams.scriptStyle,
        targetAudience: generationParams.targetAudience,
        createdAt: new Date().toISOString(),
        analytics: {
          wordCount: (response.script_content && typeof response.script_content === 'string') ? response.script_content.split(' ').length : 0,
          estimatedReadingTime: Math.ceil(generationParams.duration / 5),
          complexityScore: generationParams.targetAudience === 'beginner' ? 30 : generationParams.targetAudience === 'intermediate' ? 60 : 90,
          keyTopics: ['Generated Script']
        }
      };

      setGeneratedScripts(prev => [newScript, ...prev]);
      setSelectedScript(newScript);
      setSuccess('Script generated successfully!');
      
      // Reset to main view
      setShowCreateForm(false);
      setCurrentStep(1);
      setSelectedCurriculum(null);
      setGenerationParams({
        curriculumId: 0,
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

    } catch (err: any) {
      setError(err.message || 'Failed to generate script. Please try again.');
      console.error('Error generating script:', err);
    } finally {
      setLoading(false);
    }
  };

  const copyToClipboard = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setSuccess('Content copied to clipboard!');
      setTimeout(() => setSuccess(null), 3000);
    } catch (err) {
      setError('Failed to copy to clipboard');
    }
  };

  const downloadScript = (script: GeneratedScript) => {
    const element = document.createElement('a');
    const file = new Blob([script.content], { type: 'text/plain' });
    element.href = URL.createObjectURL(file);
    element.download = `${script.title.replace(/[^a-z0-9]/gi, '_').toLowerCase()}.txt`;
    document.body.appendChild(element);
    element.click();
    document.body.removeChild(element);
  };

  const clearAlerts = () => {
    setError(null);
    setSuccess(null);
  };

  // Script Details View
  if (viewMode === 'details' && selectedScript) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-background via-background to-accent/5">
        <Header />
        
        <div className="container mx-auto px-4 py-8">
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

          <div className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>{selectedScript.title}</CardTitle>
                <div className="flex items-center gap-4 text-sm text-muted-foreground">
                  <span>📅 {new Date(selectedScript.createdAt).toLocaleDateString()}</span>
                  <span>⏱️ {selectedScript.duration} minutes</span>
                  <span>🎯 {selectedScript.targetAudience}</span>
                  <span>📝 {selectedScript.scope}</span>
                </div>
              </CardHeader>
              <CardContent>
                <div className="prose prose-sm max-w-none">
                  <pre className="whitespace-pre-wrap font-sans text-sm leading-relaxed">
                    {selectedScript.content}
                  </pre>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    );
  }

  // Enhanced Script Creation Flow
  if (showCreateForm) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-background via-background to-accent/5">
        <Header />
        
        <div className="container mx-auto px-4 py-8">
          {/* Header */}
          <div className="flex items-center justify-between mb-8">
            <div className="flex items-center gap-4">
              <Button
                variant="outline"
                onClick={() => {
                  setShowCreateForm(false);
                  setCurrentStep(1);
                  setSelectedCurriculum(null);
                }}
                className="flex items-center gap-2"
              >
                <ArrowRight className="w-4 h-4 rotate-180" />
                Back to Scripts
              </Button>
              <div className="flex items-center gap-2">
                <Presentation className="w-6 h-6 text-primary" />
                <h1 className="text-2xl font-bold">Enhanced Curriculum Scripts</h1>
              </div>
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

          {/* Progress Steps */}
          <div className="mb-8">
            <div className="flex items-center justify-between">
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

          {/* Step 1: Curriculum Selection */}
          {currentStep === 1 && (
            <div className="space-y-6">
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

              <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
                {loading ? (
                  <div className="col-span-full flex items-center justify-center py-12">
                    <Loader2 className="w-8 h-8 animate-spin" />
                  </div>
                ) : curriculums.filter(curriculum =>
                  curriculum.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                  curriculum.description?.toLowerCase().includes(searchTerm.toLowerCase())
                ).length === 0 ? (
                  <div className="col-span-full text-center py-12">
                    <GraduationCap className="w-12 h-12 mx-auto text-muted-foreground mb-4" />
                    <h3 className="text-lg font-medium mb-2">No Curriculums Found</h3>
                    <p className="text-muted-foreground">
                      {searchTerm ? 'No curriculums match your search.' : 'You haven\'t created any curriculums yet.'}
                    </p>
                  </div>
                ) : (
                  curriculums.filter(curriculum =>
                    curriculum.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                    curriculum.description?.toLowerCase().includes(searchTerm.toLowerCase())
                  ).map((curriculum) => (
                    <Card
                      key={curriculum.id}
                      className="cursor-pointer hover:shadow-md transition-shadow"
                      onClick={() => handleCurriculumSelect(curriculum)}
                    >
                      <CardHeader>
                        <CardTitle className="flex items-center gap-2">
                          <BookOpen className="w-5 h-5" />
                          {curriculum.name}
                        </CardTitle>
                      </CardHeader>
                      <CardContent>
                        <p className="text-sm text-muted-foreground mb-4">
                          {curriculum.description || 'No description available'}
                        </p>
                        <div className="flex items-center justify-between">
                          <div className="px-2 py-1 bg-secondary text-secondary-foreground rounded text-xs">
                            Curriculum
                          </div>
                          <ArrowRight className="w-4 h-4 text-muted-foreground" />
                        </div>
                      </CardContent>
                    </Card>
                  ))
                )}
              </div>
            </div>
          )}

          {/* Step 2: Scope Configuration */}
          {currentStep === 2 && selectedCurriculum && (
            <div className="space-y-6">
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <BookOpen className="w-5 h-5" />
                    {selectedCurriculum.name}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-muted-foreground">
                    {selectedCurriculum.description}
                  </p>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Settings className="w-5 h-5" />
                    Choose Script Scope
                  </CardTitle>
                  <p className="text-sm text-muted-foreground">
                    Decide what content to include in your script from the selected curriculum
                  </p>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="space-y-4">
                    {/* Whole Curriculum Option */}
                    <div className={`flex items-start space-x-3 p-4 border-2 rounded-lg cursor-pointer hover:bg-gray-50 transition-colors ${
                      generationParams.scope === 'whole_curriculum' ? 'border-blue-500 bg-blue-50' : 'border-gray-200'
                    }`}
                    onClick={() => setGenerationParams(prev => ({ 
                      ...prev, 
                      scope: 'whole_curriculum',
                      specificBooks: [],
                      specificTopics: ''
                    }))}>
                      <div className={`w-4 h-4 rounded-full border-2 mt-1 ${
                        generationParams.scope === 'whole_curriculum' 
                          ? 'border-blue-500 bg-blue-500' 
                          : 'border-gray-300'
                      }`}>
                        {generationParams.scope === 'whole_curriculum' && (
                          <div className="w-2 h-2 bg-white rounded-full mx-auto mt-0.5"></div>
                        )}
                      </div>
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-2">
                          <GraduationCap className="w-5 h-5 text-blue-600" />
                          <div className="font-semibold text-lg">Whole Curriculum Script</div>
                        </div>
                        <div className="text-sm text-gray-600 mb-2">
                          Generate a comprehensive script covering all {curriculumBooks.length} books in the curriculum
                        </div>
                        <div className="text-xs text-blue-600 font-medium">
                          ✓ Recommended for comprehensive overview across multiple subject areas
                        </div>
                      </div>
                    </div>
                    
                    {/* Single Book Option */}
                    <div className={`flex items-start space-x-3 p-4 border-2 rounded-lg cursor-pointer hover:bg-gray-50 transition-colors ${
                      generationParams.scope === 'whole_book' ? 'border-green-500 bg-green-50' : 'border-gray-200'
                    }`}
                    onClick={() => setGenerationParams(prev => ({ 
                      ...prev, 
                      scope: 'whole_book',
                      specificBooks: [],
                      specificTopics: ''
                    }))}>
                      <div className={`w-4 h-4 rounded-full border-2 mt-1 ${
                        generationParams.scope === 'whole_book' 
                          ? 'border-green-500 bg-green-500' 
                          : 'border-gray-300'
                      }`}>
                        {generationParams.scope === 'whole_book' && (
                          <div className="w-2 h-2 bg-white rounded-full mx-auto mt-0.5"></div>
                        )}
                      </div>
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-2">
                          <BookOpen className="w-5 h-5 text-green-600" />
                          <div className="font-semibold text-lg">Single Book Script</div>
                        </div>
                        <div className="text-sm text-gray-600 mb-2">
                          Generate script focused on one specific book from the curriculum
                        </div>
                        <div className="text-xs text-green-600 font-medium">
                          ✓ Perfect for detailed coverage of specific topics or subject areas
                        </div>
                      </div>
                    </div>
                    
                    {/* Specific Topics Option */}
                    <div className={`flex items-start space-x-3 p-4 border-2 rounded-lg cursor-pointer hover:bg-gray-50 transition-colors ${
                      generationParams.scope === 'specific_topics' ? 'border-purple-500 bg-purple-50' : 'border-gray-200'
                    }`}
                    onClick={() => setGenerationParams(prev => ({ 
                      ...prev, 
                      scope: 'specific_topics',
                      specificBooks: [],
                      specificTopics: ''
                    }))}>
                      <div className={`w-4 h-4 rounded-full border-2 mt-1 ${
                        generationParams.scope === 'specific_topics' 
                          ? 'border-purple-500 bg-purple-500' 
                          : 'border-gray-300'
                      }`}>
                        {generationParams.scope === 'specific_topics' && (
                          <div className="w-2 h-2 bg-white rounded-full mx-auto mt-0.5"></div>
                        )}
                      </div>
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-2">
                          <FileText className="w-5 h-5 text-purple-600" />
                          <div className="font-semibold text-lg">Specific Topics</div>
                        </div>
                        <div className="text-sm text-gray-600 mb-2">
                          Focus on particular topics, chapters, or concepts you specify
                        </div>
                        <div className="text-xs text-purple-600 font-medium">
                          ✓ Ideal for targeted coverage of specific learning objectives
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Book Selection for whole_book and specific_topics */}
                  {(generationParams.scope === 'whole_book' || generationParams.scope === 'specific_topics') && (
                    <div className="space-y-2 mt-4">
                      <label className="text-sm font-medium">Select Book</label>
                      <Select
                        value={generationParams.specificBooks?.[0]?.toString() || ''}
                        onValueChange={(value) => setGenerationParams(prev => ({ 
                          ...prev, 
                          specificBooks: [parseInt(value)] 
                        }))}
                      >
                        <SelectTrigger>
                          <SelectValue placeholder="Choose a book from the curriculum" />
                        </SelectTrigger>
                        <SelectContent>
                          {curriculumBooks.map((book) => (
                            <SelectItem key={book.id} value={book.id.toString()}>
                              <div className="flex items-center gap-2">
                                <BookOpen className="w-4 h-4" />
                                {book.title}
                              </div>
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  )}

                  {/* Topics Input for specific_topics */}
                  {generationParams.scope === 'specific_topics' && (
                    <div className="space-y-2 mt-4">
                      <label htmlFor="topics" className="text-sm font-medium">Specify Topics</label>
                      <Textarea
                        id="topics"
                        placeholder="Enter specific topics, chapters, or concepts you want to focus on..."
                        value={generationParams.specificTopics}
                        onChange={(e) => setGenerationParams(prev => ({ ...prev, specificTopics: e.target.value }))}
                        className="min-h-[100px]"
                      />
                      <p className="text-sm text-gray-500">
                        List the topics, chapters, or concepts you want the script to focus on
                      </p>
                    </div>
                  )}

                  <Button
                    onClick={() => setCurrentStep(3)}
                    className="w-full"
                    disabled={
                      (generationParams.scope === 'whole_book' && !generationParams.specificBooks?.length) ||
                      (generationParams.scope === 'specific_topics' && !generationParams.specificTopics?.trim())
                    }
                  >
                    Continue to Parameters
                    <ArrowRight className="w-4 h-4 ml-2" />
                  </Button>
                </CardContent>
              </Card>
            </div>
          )}

          {/* Step 3: Parameters */}
          {currentStep === 3 && (
            <div className="space-y-6">
              <Card>
                <CardHeader>
                  <CardTitle>Script Parameters</CardTitle>
                </CardHeader>
                <CardContent className="space-y-6">
                  
                  <div className="space-y-2">
                    <label className="text-sm font-medium">Detail Level</label>
                    <Select
                      value={generationParams.detailLevel}
                      onValueChange={(value) => setGenerationParams(prev => ({ 
                        ...prev, 
                        detailLevel: value as 'high_level' | 'detailed' | 'comprehensive'
                      }))}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="high_level">High-level Overview</SelectItem>
                        <SelectItem value="detailed">Detailed Analysis</SelectItem>
                        <SelectItem value="comprehensive">Comprehensive Coverage</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>

                  <div className="space-y-2">
                    <label className="text-sm font-medium">Duration (minutes)</label>
                    <Input
                      type="number"
                      value={generationParams.duration}
                      onChange={(e) => setGenerationParams(prev => ({ 
                        ...prev, 
                        duration: parseInt(e.target.value) || 60
                      }))}
                      min="15"
                      max="240"
                    />
                  </div>

                  <div className="space-y-2">
                    <label className="text-sm font-medium">Target Audience</label>
                    <Select
                      value={generationParams.targetAudience}
                      onValueChange={(value) => setGenerationParams(prev => ({ 
                        ...prev, 
                        targetAudience: value as 'beginner' | 'intermediate' | 'advanced'
                      }))}
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

                  <Button
                    onClick={() => setCurrentStep(4)}
                    className="w-full"
                  >
                    Continue to Generation
                    <ArrowRight className="w-4 h-4 ml-2" />
                  </Button>
                </CardContent>
              </Card>
            </div>
          )}

          {/* Step 4: Generate */}
          {currentStep === 4 && (
            <div className="space-y-6">
              <Card>
                <CardHeader>
                  <CardTitle>Generate Script</CardTitle>
                </CardHeader>
                <CardContent className="space-y-6">
                  <div className="bg-muted p-4 rounded-lg">
                    <h3 className="font-medium mb-2">Script Summary</h3>
                    <div className="text-sm space-y-1">
                      <p><strong>Curriculum:</strong> {selectedCurriculum?.name}</p>
                      <p><strong>Scope:</strong> {generationParams.scope.replace('_', ' ')}</p>
                      <p><strong>Detail Level:</strong> {generationParams.detailLevel.replace('_', ' ')}</p>
                      <p><strong>Duration:</strong> {generationParams.duration} minutes</p>
                      <p><strong>Audience:</strong> {generationParams.targetAudience}</p>
                    </div>
                  </div>

                  <Button
                    onClick={generateScript}
                    className="w-full"
                    disabled={loading}
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
        </div>
      </div>
    );
  }

  // Main Scripts List View
  return (
    <div className="min-h-screen bg-gradient-to-br from-background via-background to-accent/5">
      <Header />
      
      <div className="container mx-auto px-4 py-8">
        <div className="flex items-center justify-between mb-8">
          <div className="flex items-center gap-2">
            <Presentation className="w-6 h-6 text-primary" />
            <h1 className="text-2xl font-bold">Enhanced Curriculum Scripts</h1>
          </div>
          
          <Button
            onClick={() => {
              setShowCreateForm(true);
              setCurrentStep(1);
              setSelectedCurriculum(null);
            }}
            className="flex items-center gap-2"
          >
            <Plus className="w-4 h-4" />
            Create Script
          </Button>
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
            </AlertDescription>
          </Alert>
        )}

        {/* Scripts List */}
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <FileText className="w-5 h-5" />
                Your Scripts ({generatedScripts.length})
              </CardTitle>
            </CardHeader>
            <CardContent>
              {generatedScripts.length === 0 ? (
                <div className="text-center py-12">
                  <Presentation className="w-12 h-12 mx-auto text-muted-foreground mb-4" />
                  <h3 className="text-lg font-medium mb-2">No Scripts Yet</h3>
                  <p className="text-muted-foreground mb-4">
                    Create your first enhanced curriculum script to get started.
                  </p>
                  <Button
                    onClick={() => setShowCreateForm(true)}
                    className="flex items-center gap-2"
                  >
                    <Plus className="w-4 h-4" />
                    Create Your First Script
                  </Button>
                </div>
              ) : (
                <div className="space-y-4">
                  {generatedScripts.map((script, index) => (
                    <div
                      key={script.id || index}
                      className="flex items-center justify-between p-4 border rounded-lg hover:bg-muted/50 transition-colors"
                    >
                      <div className="flex-1">
                        <h3 className="font-medium">{script.title}</h3>
                        <div className="flex items-center gap-4 text-sm text-muted-foreground mt-1">
                          <span>📅 {new Date(script.createdAt).toLocaleDateString()}</span>
                          <span>⏱️ {script.duration} minutes</span>
                          <span>🎯 {script.targetAudience}</span>
                          <Badge variant="outline">{script.scope}</Badge>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => {
                            setSelectedScript(script);
                            setViewMode('details');
                          }}
                          className="flex items-center gap-2"
                        >
                          <Eye className="w-4 h-4" />
                          View
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}