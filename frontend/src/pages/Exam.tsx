import React, { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Header } from '@/components/ui/header';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Clock, CheckCircle, XCircle, RotateCcw, Home } from 'lucide-react';

interface Question {
  id: string;
  type: 'multiple-choice' | 'true-false' | 'short-answer' | 'essay';
  question: string;
  options?: string[];
  correctAnswer?: string;
  userAnswer?: string;
  points: number;
}

interface ExamData {
  id: string;
  title: string;
  book: string;
  difficulty: string;
  timeLimit: number;
  questions: Question[];
}

const sampleExam: ExamData = {
  id: '1',
  title: 'Psychology Fundamentals Quiz',
  book: 'Introduction to Psychology',
  difficulty: 'Medium',
  timeLimit: 30,
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
      correctAnswer: 'Mental processes and thinking',
      points: 5
    },
    {
      id: '2',
      type: 'true-false',
      question: 'Classical conditioning was first discovered by Ivan Pavlov.',
      correctAnswer: 'true',
      points: 3
    },
    {
      id: '3',
      type: 'short-answer',
      question: 'Define the term "neuroplasticity" and explain its significance in psychology.',
      correctAnswer: 'Neuroplasticity refers to the brain\'s ability to reorganize and adapt by forming new neural connections.',
      points: 10
    }
  ]
};

export default function Exam() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [timeRemaining, setTimeRemaining] = useState(1800); // 30 minutes in seconds
  const [isCompleted, setIsCompleted] = useState(false);
  const [showResults, setShowResults] = useState(false);

  const examData = sampleExam; // In real app, this would come from URL params or API
  const currentQuestion = examData.questions[currentQuestionIndex];
  const progress = ((currentQuestionIndex + 1) / examData.questions.length) * 100;

  useEffect(() => {
    if (timeRemaining > 0 && !isCompleted) {
      const timer = setTimeout(() => setTimeRemaining(timeRemaining - 1), 1000);
      return () => clearTimeout(timer);
    } else if (timeRemaining === 0) {
      handleSubmitExam();
    }
  }, [timeRemaining, isCompleted]);

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const handleAnswerChange = (value: string) => {
    setAnswers(prev => ({
      ...prev,
      [currentQuestion.id]: value
    }));
  };

  const handleNext = () => {
    if (currentQuestionIndex < examData.questions.length - 1) {
      setCurrentQuestionIndex(currentQuestionIndex + 1);
    } else {
      handleSubmitExam();
    }
  };

  const handlePrevious = () => {
    if (currentQuestionIndex > 0) {
      setCurrentQuestionIndex(currentQuestionIndex - 1);
    }
  };

  const handleSubmitExam = () => {
    setIsCompleted(true);
    setShowResults(true);
  };

  const calculateScore = () => {
    let totalPoints = 0;
    let earnedPoints = 0;

    examData.questions.forEach(question => {
      totalPoints += question.points;
      const userAnswer = answers[question.id];
      
      if (question.type === 'multiple-choice' || question.type === 'true-false') {
        if (userAnswer === question.correctAnswer) {
          earnedPoints += question.points;
        }
      } else {
        // For short-answer and essay, give partial credit for demo
        if (userAnswer && userAnswer.length > 10) {
          earnedPoints += Math.floor(question.points * 0.8);
        }
      }
    });

    return { earned: earnedPoints, total: totalPoints };
  };

  const retryExam = () => {
    setCurrentQuestionIndex(0);
    setAnswers({});
    setTimeRemaining(examData.timeLimit * 60);
    setIsCompleted(false);
    setShowResults(false);
  };

  if (showResults) {
    const score = calculateScore();
    const percentage = Math.round((score.earned / score.total) * 100);

    return (
      <div className="min-h-screen bg-gradient-to-br from-background via-background to-accent/5">
        <Header />
        
        <div className="container mx-auto px-4 py-8">
          <div className="max-w-4xl mx-auto">
            <Card className="text-center">
              <CardHeader>
                <div className="w-20 h-20 mx-auto mb-4 rounded-full bg-gradient-to-br from-primary to-secondary flex items-center justify-center">
                  <CheckCircle className="w-10 h-10 text-white" />
                </div>
                <CardTitle className="text-2xl">Exam Completed!</CardTitle>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div className="p-4 bg-primary/5 rounded-lg">
                    <div className="text-2xl font-bold text-primary">{score.earned}/{score.total}</div>
                    <div className="text-sm text-muted-foreground">Points Earned</div>
                  </div>
                  <div className="p-4 bg-secondary/5 rounded-lg">
                    <div className="text-2xl font-bold text-secondary">{percentage}%</div>
                    <div className="text-sm text-muted-foreground">Overall Score</div>
                  </div>
                  <div className="p-4 bg-accent/5 rounded-lg">
                    <div className="text-2xl font-bold text-accent">{formatTime(examData.timeLimit * 60 - timeRemaining)}</div>
                    <div className="text-sm text-muted-foreground">Time Taken</div>
                  </div>
                </div>

                <div className="space-y-4">
                  <h3 className="text-lg font-semibold">Review Your Answers</h3>
                  {examData.questions.map((question, index) => (
                    <div key={question.id} className="text-left p-4 border rounded-lg">
                      <div className="flex items-start justify-between mb-2">
                        <h4 className="font-medium">Question {index + 1}</h4>
                        <Badge variant={answers[question.id] === question.correctAnswer ? "default" : "destructive"}>
                          {question.points} pts
                        </Badge>
                      </div>
                      <p className="mb-3 text-sm">{question.question}</p>
                      <div className="space-y-2 text-sm">
                        <div>
                          <span className="font-medium">Your answer: </span>
                          <span className={answers[question.id] === question.correctAnswer ? "text-green-600" : "text-red-600"}>
                            {answers[question.id] || "No answer provided"}
                          </span>
                        </div>
                        {(question.type === 'multiple-choice' || question.type === 'true-false') && (
                          <div>
                            <span className="font-medium">Correct answer: </span>
                            <span className="text-green-600">{question.correctAnswer}</span>
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>

                <div className="flex gap-4 justify-center">
                  <Button onClick={retryExam} variant="outline">
                    <RotateCcw className="w-4 h-4 mr-2" />
                    Try Again
                  </Button>
                  <Button onClick={() => navigate('/')}>
                    <Home className="w-4 h-4 mr-2" />
                    Return to Dashboard
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
      
      <div className="container mx-auto px-4 py-8">
        <div className="max-w-4xl mx-auto">
          {/* Exam Header */}
          <Card className="mb-6">
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>{examData.title}</CardTitle>
                  <p className="text-muted-foreground">Book: {examData.book}</p>
                </div>
                <div className="flex items-center gap-4">
                  <Badge variant="secondary">{examData.difficulty}</Badge>
                  <div className="flex items-center gap-2 text-sm">
                    <Clock className="w-4 h-4" />
                    <span className={timeRemaining < 300 ? "text-red-500 font-bold" : ""}>
                      {formatTime(timeRemaining)}
                    </span>
                  </div>
                </div>
              </div>
              <div className="mt-4">
                <div className="flex items-center justify-between text-sm mb-2">
                  <span>Question {currentQuestionIndex + 1} of {examData.questions.length}</span>
                  <span>{Math.round(progress)}% Complete</span>
                </div>
                <Progress value={progress} className="h-2" />
              </div>
            </CardHeader>
          </Card>

          {/* Question Card */}
          <Card className="mb-6">
            <CardHeader>
              <CardTitle className="text-lg">
                Question {currentQuestionIndex + 1}
                <Badge variant="outline" className="ml-2">{currentQuestion.points} points</Badge>
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              <p className="text-lg">{currentQuestion.question}</p>

              {/* Answer Input Based on Question Type */}
              {currentQuestion.type === 'multiple-choice' && (
                <RadioGroup
                  value={answers[currentQuestion.id] || ''}
                  onValueChange={handleAnswerChange}
                >
                  {currentQuestion.options?.map((option, index) => (
                    <div key={index} className="flex items-center space-x-2">
                      <RadioGroupItem value={option} id={`option-${index}`} />
                      <Label htmlFor={`option-${index}`} className="cursor-pointer">
                        {option}
                      </Label>
                    </div>
                  ))}
                </RadioGroup>
              )}

              {currentQuestion.type === 'true-false' && (
                <RadioGroup
                  value={answers[currentQuestion.id] || ''}
                  onValueChange={handleAnswerChange}
                >
                  <div className="flex items-center space-x-2">
                    <RadioGroupItem value="true" id="true" />
                    <Label htmlFor="true" className="cursor-pointer">True</Label>
                  </div>
                  <div className="flex items-center space-x-2">
                    <RadioGroupItem value="false" id="false" />
                    <Label htmlFor="false" className="cursor-pointer">False</Label>
                  </div>
                </RadioGroup>
              )}

              {(currentQuestion.type === 'short-answer' || currentQuestion.type === 'essay') && (
                <Textarea
                  value={answers[currentQuestion.id] || ''}
                  onChange={(e) => handleAnswerChange(e.target.value)}
                  placeholder="Type your answer here..."
                  className="min-h-[120px]"
                />
              )}

              {/* Navigation Buttons */}
              <div className="flex justify-between pt-4">
                <Button
                  variant="outline"
                  onClick={handlePrevious}
                  disabled={currentQuestionIndex === 0}
                >
                  Previous
                </Button>
                
                <div className="flex gap-2">
                  {currentQuestionIndex === examData.questions.length - 1 ? (
                    <Button onClick={handleSubmitExam} className="bg-green-600 hover:bg-green-700">
                      Submit Exam
                    </Button>
                  ) : (
                    <Button onClick={handleNext}>
                      Next Question
                    </Button>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}