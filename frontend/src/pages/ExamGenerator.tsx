import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Header } from '@/components/ui/header';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { 
  GraduationCap, 
  Settings, 
  Eye, 
  Download, 
  Printer, 
  Play,
  BookOpen,
  Clock,
  Target,
  Sparkles
} from 'lucide-react';

interface ExamConfig {
  bookTitle: string;
  numQuestions: number;
  questionTypes: string[];
  difficulty: string[];
  timeLimit: number;
  topics: string[];
}

const questionTypeOptions = [
  { id: 'multiple-choice', label: 'Multiple Choice', icon: '◉' },
  { id: 'true-false', label: 'True/False', icon: '✓' },
  { id: 'short-answer', label: 'Short Answer', icon: '✎' },
  { id: 'essay', label: 'Essay', icon: '📝' }
];

const difficultyLevels = [
  { id: 'easy', label: 'Easy', color: 'bg-success/20 text-success hover:bg-success/30' },
  { id: 'medium', label: 'Medium', color: 'bg-warning/20 text-warning hover:bg-warning/30' },
  { id: 'hard', label: 'Hard', color: 'bg-destructive/20 text-destructive hover:bg-destructive/30' }
];

const availableBooks = [
  { 
    id: 'psych-intro', 
    title: 'Introduction to Psychology', 
    subject: 'Psychology', 
    chapters: 12,
    author: 'David G. Myers'
  },
  { 
    id: 'calc-basics', 
    title: 'Calculus: Early Transcendentals', 
    subject: 'Mathematics', 
    chapters: 16,
    author: 'James Stewart'
  },
  { 
    id: 'bio-principles', 
    title: 'Campbell Biology', 
    subject: 'Biology', 
    chapters: 56,
    author: 'Jane B. Reece'
  },
  { 
    id: 'hist-world', 
    title: 'A History of World Societies', 
    subject: 'History', 
    chapters: 33,
    author: 'John P. McKay'
  },
  { 
    id: 'chem-general', 
    title: 'General Chemistry', 
    subject: 'Chemistry', 
    chapters: 22,
    author: 'Darrell Ebbing'
  },
  { 
    id: 'physics-principles', 
    title: 'Physics: Principles with Applications', 
    subject: 'Physics', 
    chapters: 35,
    author: 'Douglas C. Giancoli'
  }
];

const ExamGenerator = () => {
  const navigate = useNavigate();
  const [currentStep, setCurrentStep] = useState(1);
  const [examConfig, setExamConfig] = useState<ExamConfig>({
    bookTitle: 'psych-intro',
    numQuestions: 20,
    questionTypes: ['multiple-choice'],
    difficulty: ['medium'],
    timeLimit: 60,
    topics: []
  });
  const [isGenerating, setIsGenerating] = useState(false);
  const [generatedExam, setGeneratedExam] = useState(null);
  const selectedBook = availableBooks.find(book => book.id === examConfig.bookTitle);

  const handleQuestionTypeToggle = (typeId: string) => {
    setExamConfig(prev => ({
      ...prev,
      questionTypes: prev.questionTypes.includes(typeId)
        ? prev.questionTypes.filter(t => t !== typeId)
        : [...prev.questionTypes, typeId]
    }));
  };

  const handleDifficultyToggle = (level: string) => {
    setExamConfig(prev => ({
      ...prev,
      difficulty: prev.difficulty.includes(level)
        ? prev.difficulty.filter(d => d !== level)
        : [...prev.difficulty, level]
    }));
  };

  const generateExam = async () => {
    setIsGenerating(true);
    // Simulate exam generation
    setTimeout(() => {
      setGeneratedExam({
        title: `${selectedBook?.title || 'Selected Book'} - Practice Exam`,
        difficulty: examConfig.difficulty.join('-'),
        questions: examConfig.numQuestions,
        estimatedTime: examConfig.timeLimit
      });
      setIsGenerating(false);
      setCurrentStep(3);
    }, 2000);
  };

  return (
    <div className="min-h-screen bg-background">
      <Header />
      
      <div className="container mx-auto px-4 py-8">
        {/* Page Header */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-primary/10 text-primary text-sm font-medium mb-4">
            <GraduationCap className="w-4 h-4" />
            Smart Exam Generator
          </div>
          <h1 className="text-4xl font-bold mb-4">Create Your Perfect Exam</h1>
          <p className="text-xl text-muted-foreground max-w-2xl mx-auto">
            Generate customized exams tailored to your learning goals with AI-powered question creation
          </p>
        </div>

        {/* Progress Steps */}
        <div className="flex justify-center mb-12">
          <div className="flex items-center gap-4">
            {[1, 2, 3].map((step) => (
              <React.Fragment key={step}>
                <div className={`flex items-center justify-center w-10 h-10 rounded-full font-semibold transition-all duration-300 ${
                  step < currentStep ? 'bg-success text-success-foreground' :
                  step === currentStep ? 'bg-primary text-primary-foreground shadow-soft' :
                  'bg-muted text-muted-foreground'
                }`}>
                  {step < currentStep ? '✓' : step}
                </div>
                {step < 3 && (
                  <div className={`w-16 h-1 rounded-full transition-all duration-300 ${
                    step < currentStep ? 'bg-success' : 'bg-muted'
                  }`} />
                )}
              </React.Fragment>
            ))}
          </div>
        </div>

        {/* Step Content */}
        <div className="max-w-4xl mx-auto">
          {currentStep === 1 && (
            <Card className="shadow-medium">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Settings className="w-5 h-5 text-primary" />
                  Exam Configuration
                </CardTitle>
                <CardDescription>
                  Set up your exam parameters to generate the perfect assessment
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-8">
                {/* Book Selection */}
                <div className="space-y-2">
                  <Label htmlFor="book">Select Book</Label>
                  <Select
                    value={examConfig.bookTitle}
                    onValueChange={(value) => setExamConfig(prev => ({ ...prev, bookTitle: value }))}
                  >
                    <SelectTrigger className="w-full">
                      <SelectValue placeholder="Choose a book to create an exam from">
                        {selectedBook && (
                          <div className="flex items-center gap-3">
                            <BookOpen className="w-4 h-4 text-primary" />
                            <div className="text-left">
                              <div className="font-medium">{selectedBook.title}</div>
                              <div className="text-xs text-muted-foreground">
                                {selectedBook.subject} • {selectedBook.chapters} Chapters • {selectedBook.author}
                              </div>
                            </div>
                          </div>
                        )}
                      </SelectValue>
                    </SelectTrigger>
                    <SelectContent>
                      {availableBooks.map((book) => (
                        <SelectItem key={book.id} value={book.id}>
                          <div className="flex items-center gap-3 py-2">
                            <BookOpen className="w-4 h-4 text-primary flex-shrink-0" />
                            <div>
                              <div className="font-medium">{book.title}</div>
                              <div className="text-xs text-muted-foreground">
                                {book.subject} • {book.chapters} Chapters • {book.author}
                              </div>
                            </div>
                          </div>
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                {/* Number of Questions */}
                <div className="space-y-2">
                  <Label htmlFor="questions">Number of Questions</Label>
                  <div className="flex items-center gap-4">
                    <Input
                      id="questions"
                      type="number"
                      min="5"
                      max="100"
                      value={examConfig.numQuestions}
                      onChange={(e) => setExamConfig(prev => ({ ...prev, numQuestions: parseInt(e.target.value) || 20 }))}
                      className="w-24"
                    />
                    <div className="text-sm text-muted-foreground">
                      Recommended: 15-30 questions for optimal learning
                    </div>
                  </div>
                </div>

                {/* Question Types */}
                <div className="space-y-4">
                  <Label>Question Types</Label>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                    {questionTypeOptions.map((type) => (
                      <Button
                        key={type.id}
                        variant={examConfig.questionTypes.includes(type.id) ? "default" : "outline"}
                        onClick={() => handleQuestionTypeToggle(type.id)}
                        className="h-auto p-4 flex flex-col items-center gap-2"
                      >
                        <span className="text-lg">{type.icon}</span>
                        <span className="text-sm">{type.label}</span>
                      </Button>
                    ))}
                  </div>
                </div>

                {/* Difficulty Levels */}
                <div className="space-y-4">
                  <Label>Difficulty Levels</Label>
                  <div className="flex gap-3">
                    {difficultyLevels.map((level) => (
                      <Button
                        key={level.id}
                        variant="outline"
                        onClick={() => handleDifficultyToggle(level.id)}
                        className={`${
                          examConfig.difficulty.includes(level.id) 
                            ? level.color 
                            : 'hover:bg-muted'
                        }`}
                      >
                        {level.label}
                      </Button>
                    ))}
                  </div>
                </div>

                {/* Time Limit */}
                <div className="space-y-2">
                  <Label htmlFor="time">Time Limit (minutes)</Label>
                  <div className="flex items-center gap-4">
                    <Input
                      id="time"
                      type="number"
                      min="15"
                      max="180"
                      value={examConfig.timeLimit}
                      onChange={(e) => setExamConfig(prev => ({ ...prev, timeLimit: parseInt(e.target.value) || 60 }))}
                      className="w-24"
                    />
                    <Clock className="w-4 h-4 text-muted-foreground" />
                    <span className="text-sm text-muted-foreground">
                      ~{Math.round(examConfig.timeLimit / examConfig.numQuestions)} min per question
                    </span>
                  </div>
                </div>

                <Button 
                  onClick={() => setCurrentStep(2)} 
                  className="w-full bg-gradient-primary floating-action"
                  size="lg"
                >
                  Continue to Review
                </Button>
              </CardContent>
            </Card>
          )}

          {currentStep === 2 && (
            <Card className="shadow-medium">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Eye className="w-5 h-5 text-primary" />
                  Review & Generate
                </CardTitle>
                <CardDescription>
                  Review your exam configuration before generation
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                {/* Configuration Summary */}
                <div className="grid md:grid-cols-2 gap-6">
                  <div className="space-y-4">
                    <div>
                      <h3 className="font-semibold mb-2">Book & Content</h3>
                      <div className="text-sm text-muted-foreground">
                        {selectedBook?.title} • {examConfig.numQuestions} Questions
                      </div>
                    </div>
                    
                    <div>
                      <h3 className="font-semibold mb-2">Question Types</h3>
                      <div className="flex flex-wrap gap-2">
                        {examConfig.questionTypes.map(type => (
                          <Badge key={type} variant="secondary">
                            {questionTypeOptions.find(q => q.id === type)?.label}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  </div>

                  <div className="space-y-4">
                    <div>
                      <h3 className="font-semibold mb-2">Difficulty</h3>
                      <div className="flex flex-wrap gap-2">
                        {examConfig.difficulty.map(level => (
                          <Badge key={level} variant="outline">
                            {level.charAt(0).toUpperCase() + level.slice(1)}
                          </Badge>
                        ))}
                      </div>
                    </div>
                    
                    <div>
                      <h3 className="font-semibold mb-2">Time Limit</h3>
                      <div className="text-sm text-muted-foreground">
                        {examConfig.timeLimit} minutes total
                      </div>
                    </div>
                  </div>
                </div>

                <Separator />

                {/* Generation Preview */}
                <div className="bg-gradient-to-br from-accent/5 to-primary/5 rounded-lg p-6 text-center">
                  <Target className="w-12 h-12 text-primary mx-auto mb-4" />
                  <h3 className="text-lg font-semibold mb-2">Ready to Generate</h3>
                  <p className="text-muted-foreground mb-6">
                    AI will analyze your book and create personalized questions based on your configuration
                  </p>
                  
                  <div className="flex gap-3 justify-center">
                    <Button 
                      variant="outline" 
                      onClick={() => setCurrentStep(1)}
                    >
                      Back to Edit
                    </Button>
                    <Button 
                      onClick={generateExam}
                      disabled={isGenerating}
                      className="bg-gradient-accent floating-action"
                      size="lg"
                    >
                      {isGenerating ? (
                        <>
                          <Sparkles className="w-4 h-4 mr-2 animate-spin" />
                          Generating...
                        </>
                      ) : (
                        'Generate Exam'
                      )}
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}

          {currentStep === 3 && generatedExam && (
            <Card className="shadow-medium">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <GraduationCap className="w-5 h-5 text-success" />
                  Exam Generated Successfully!
                </CardTitle>
                <CardDescription>
                  Your personalized exam is ready for use
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                {/* Exam Details */}
                <div className="bg-gradient-to-br from-success/5 to-accent/5 rounded-lg p-6">
                  <h2 className="text-xl font-bold mb-4">{generatedExam.title}</h2>
                  
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-center">
                    <div>
                      <div className="text-2xl font-bold text-primary">{generatedExam.questions}</div>
                      <div className="text-sm text-muted-foreground">Questions</div>
                    </div>
                    <div>
                      <div className="text-2xl font-bold text-accent">{generatedExam.estimatedTime}m</div>
                      <div className="text-sm text-muted-foreground">Time Limit</div>
                    </div>
                    <div>
                      <div className="text-2xl font-bold text-warning">{generatedExam.difficulty}</div>
                      <div className="text-sm text-muted-foreground">Difficulty</div>
                    </div>
                    <div>
                      <div className="text-2xl font-bold text-success">100%</div>
                      <div className="text-sm text-muted-foreground">AI Generated</div>
                    </div>
                  </div>
                </div>

                {/* Action Buttons */}
                <div className="grid md:grid-cols-3 gap-4">
                  <Button 
                    onClick={() => navigate('/exam')}
                    className="h-auto p-4 flex flex-col items-center gap-2 bg-gradient-primary"
                  >
                    <Play className="w-6 h-6" />
                    <span className="font-medium">Start Rehearsal</span>
                    <span className="text-xs opacity-80">Practice with feedback</span>
                  </Button>
                  
                  <Button 
                    onClick={() => navigate('/exams/view')}
                    variant="outline" 
                    className="h-auto p-4 flex flex-col items-center gap-2 hover:bg-muted/50"
                  >
                    <Eye className="w-6 h-6" />
                    <span className="font-medium">View Exam</span>
                    <span className="text-xs text-muted-foreground">Review questions</span>
                  </Button>
                  
                  <Button variant="outline" className="h-auto p-4 flex flex-col items-center gap-2 hover:bg-muted/50">
                    <Download className="w-6 h-6" />
                    <span className="font-medium">Save as PDF</span>
                    <span className="text-xs text-muted-foreground">Download exam</span>
                  </Button>
                </div>

                <Button 
                  variant="ghost" 
                  onClick={() => {
                    setCurrentStep(1);
                    setGeneratedExam(null);
                  }}
                  className="w-full"
                >
                  Create Another Exam
                </Button>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
};

export default ExamGenerator;