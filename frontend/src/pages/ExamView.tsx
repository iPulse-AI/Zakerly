import React from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Header } from '@/components/ui/header';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { Clock, BookOpen, Play, Download, Printer, Copy } from 'lucide-react';

interface Question {
  id: string;
  type: 'multiple-choice' | 'true-false' | 'short-answer' | 'essay';
  question: string;
  options?: string[];
  points: number;
}

interface ExamData {
  id: string;
  title: string;
  book: string;
  difficulty: string;
  timeLimit: number;
  totalQuestions: number;
  totalPoints: number;
  questions: Question[];
  createdAt: Date;
}

const sampleExam: ExamData = {
  id: '1',
  title: 'Psychology Fundamentals Quiz',
  book: 'Introduction to Psychology',
  difficulty: 'Medium',
  timeLimit: 30,
  totalQuestions: 15,
  totalPoints: 100,
  createdAt: new Date(),
  questions: [
    {
      id: '1',
      type: 'multiple-choice',
      question: 'What is the primary focus of cognitive psychology?',
      options: [
        'Mental processes and thinking',
        'Observable behaviors only',
        'Unconscious motivations',
        'Social interactions'
      ],
      points: 5
    },
    {
      id: '2',
      type: 'true-false',
      question: 'Classical conditioning was first discovered by Ivan Pavlov.',
      points: 3
    },
    {
      id: '3',
      type: 'short-answer',
      question: 'Define the term "neuroplasticity" and explain its significance in psychology.',
      points: 10
    },
    {
      id: '4',
      type: 'essay',
      question: 'Discuss the major differences between behaviorism and cognitive psychology. Provide examples to support your arguments.',
      points: 15
    },
    {
      id: '5',
      type: 'multiple-choice',
      question: 'Which part of the brain is primarily responsible for processing emotions?',
      options: [
        'Cerebellum',
        'Amygdala',
        'Hippocampus',
        'Frontal lobe'
      ],
      points: 5
    }
  ]
};

export default function ExamView() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  
  const examData = sampleExam; // In real app, this would come from URL params or API

  const getDifficultyColor = (difficulty: string) => {
    switch (difficulty.toLowerCase()) {
      case 'easy': return 'bg-green-100 text-green-800';
      case 'medium': return 'bg-yellow-100 text-yellow-800';
      case 'hard': return 'bg-red-100 text-red-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  const getQuestionTypeLabel = (type: string) => {
    switch (type) {
      case 'multiple-choice': return 'Multiple Choice';
      case 'true-false': return 'True/False';
      case 'short-answer': return 'Short Answer';
      case 'essay': return 'Essay';
      default: return type;
    }
  };

  const handleStartRehearsal = () => {
    navigate(`/exam?id=${examData.id}`);
  };

  const handleSaveAsPDF = () => {
    // In a real app, this would generate and download a PDF
    console.log('Saving exam as PDF...');
  };

  const handlePrint = () => {
    window.print();
  };

  const handleCopyToClipboard = () => {
    const examText = `${examData.title}\n\n${examData.questions.map((q, i) => 
      `${i + 1}. ${q.question}${q.options ? '\n' + q.options.map((opt, j) => `   ${String.fromCharCode(97 + j)}) ${opt}`).join('\n') : ''}\n`
    ).join('\n')}`;
    
    navigator.clipboard.writeText(examText);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-background via-background to-accent/5">
      <Header />
      
      <div className="container mx-auto px-4 py-8">
        <div className="max-w-4xl mx-auto">
          {/* Exam Header */}
          <Card className="mb-6">
            <CardHeader>
              <div className="flex items-start justify-between">
                <div className="space-y-2">
                  <CardTitle className="text-2xl">{examData.title}</CardTitle>
                  <div className="flex items-center gap-2 text-muted-foreground">
                    <BookOpen className="w-4 h-4" />
                    <span>Book: {examData.book}</span>
                  </div>
                  <div className="text-sm text-muted-foreground">
                    Generated on {examData.createdAt.toLocaleDateString()}
                  </div>
                </div>
                <div className="flex flex-col items-end gap-2">
                  <Badge className={getDifficultyColor(examData.difficulty)}>
                    {examData.difficulty}
                  </Badge>
                </div>
              </div>
            </CardHeader>
          </Card>

          {/* Exam Details */}
          <Card className="mb-6">
            <CardHeader>
              <CardTitle className="text-lg">Exam Details</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="text-center p-4 bg-primary/5 rounded-lg">
                  <div className="text-2xl font-bold text-primary">{examData.totalQuestions}</div>
                  <div className="text-sm text-muted-foreground">Questions</div>
                </div>
                <div className="text-center p-4 bg-secondary/5 rounded-lg">
                  <div className="text-2xl font-bold text-secondary">{examData.totalPoints}</div>
                  <div className="text-sm text-muted-foreground">Total Points</div>
                </div>
                <div className="text-center p-4 bg-accent/5 rounded-lg">
                  <div className="text-2xl font-bold text-accent flex items-center justify-center gap-1">
                    <Clock className="w-5 h-5" />
                    {examData.timeLimit}
                  </div>
                  <div className="text-sm text-muted-foreground">Minutes</div>
                </div>
                <div className="text-center p-4 bg-muted/50 rounded-lg">
                  <div className="text-2xl font-bold">
                    {Math.round((examData.totalPoints / examData.totalQuestions) * 10) / 10}
                  </div>
                  <div className="text-sm text-muted-foreground">Avg Points/Q</div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Action Buttons */}
          <Card className="mb-6">
            <CardContent className="pt-6">
              <div className="flex flex-wrap gap-3 justify-center">
                <Button onClick={handleStartRehearsal} className="flex-1 max-w-xs">
                  <Play className="w-4 h-4 mr-2" />
                  Start Rehearsal
                </Button>
                <Button variant="outline" onClick={handleSaveAsPDF} className="flex-1 max-w-xs">
                  <Download className="w-4 h-4 mr-2" />
                  Save as PDF
                </Button>
                <Button variant="outline" onClick={handlePrint} className="flex-1 max-w-xs">
                  <Printer className="w-4 h-4 mr-2" />
                  Print
                </Button>
                <Button variant="outline" onClick={handleCopyToClipboard} className="flex-1 max-w-xs">
                  <Copy className="w-4 h-4 mr-2" />
                  Copy Text
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* Questions Preview */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Questions Preview</CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              {examData.questions.map((question, index) => (
                <div key={question.id}>
                  <div className="space-y-3">
                    <div className="flex items-start justify-between">
                      <h3 className="font-semibold text-lg">
                        Question {index + 1}
                      </h3>
                      <div className="flex items-center gap-2">
                        <Badge variant="secondary">
                          {getQuestionTypeLabel(question.type)}
                        </Badge>
                        <Badge variant="outline">
                          {question.points} pts
                        </Badge>
                      </div>
                    </div>
                    
                    <p className="text-base leading-relaxed">{question.question}</p>
                    
                    {question.options && (
                      <div className="mt-3 space-y-2">
                        {question.options.map((option, optionIndex) => (
                          <div key={optionIndex} className="flex items-center gap-2 text-sm">
                            <span className="flex items-center justify-center w-6 h-6 rounded-full bg-muted text-muted-foreground font-medium">
                              {String.fromCharCode(97 + optionIndex)}
                            </span>
                            <span>{option}</span>
                          </div>
                        ))}
                      </div>
                    )}
                    
                    {question.type === 'true-false' && (
                      <div className="flex gap-4 text-sm">
                        <div className="flex items-center gap-2">
                          <span className="flex items-center justify-center w-6 h-6 rounded-full bg-muted text-muted-foreground font-medium">
                            T
                          </span>
                          <span>True</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className="flex items-center justify-center w-6 h-6 rounded-full bg-muted text-muted-foreground font-medium">
                            F
                          </span>
                          <span>False</span>
                        </div>
                      </div>
                    )}
                    
                    {(question.type === 'short-answer' || question.type === 'essay') && (
                      <div className="p-3 bg-muted/30 rounded border-2 border-dashed border-muted-foreground/30">
                        <p className="text-sm text-muted-foreground italic">
                          {question.type === 'essay' 
                            ? 'Extended response required (multiple paragraphs expected)'
                            : 'Short written response required'
                          }
                        </p>
                      </div>
                    )}
                  </div>
                  
                  {index < examData.questions.length - 1 && (
                    <Separator className="mt-6" />
                  )}
                </div>
              ))}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}