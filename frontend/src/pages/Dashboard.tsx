import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Header } from '@/components/ui/header';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { 
  BookOpen, 
  GraduationCap, 
  Trophy, 
  Target, 
  Clock, 
  Calendar, 
  TrendingUp, 
  Flame,
  Star,
  Award,
  BarChart3,
  Activity,
  Plus,
  ArrowRight,
  Zap,
  Brain,
  CheckCircle
} from 'lucide-react';

// Mock user data
const userData = {
  name: "John Doe",
  userType: "Student",
  joinDate: "January 2024",
  streak: 12,
  totalPoints: 2850,
  level: 8,
  nextLevelPoints: 3000
};

const stats = [
  { label: "Books Read", value: 15, icon: BookOpen, color: "text-blue-600", bgColor: "bg-blue-100" },
  { label: "Exams Taken", value: 28, icon: GraduationCap, color: "text-purple-600", bgColor: "bg-purple-100" },
  { label: "Scripts Created", value: 8, icon: Trophy, color: "text-green-600", bgColor: "bg-green-100" },
  { label: "Study Hours", value: 127, icon: Clock, color: "text-orange-600", bgColor: "bg-orange-100" }
];

const achievements = [
  { 
    id: 1, 
    title: "First Steps", 
    description: "Added your first book", 
    icon: BookOpen, 
    unlocked: true, 
    date: "Jan 15, 2024",
    rarity: "common"
  },
  { 
    id: 2, 
    title: "Scholar", 
    description: "Read 10 books", 
    icon: GraduationCap, 
    unlocked: true, 
    date: "Feb 20, 2024",
    rarity: "rare"
  },
  { 
    id: 3, 
    title: "Streak Master", 
    description: "10-day study streak", 
    icon: Flame, 
    unlocked: true, 
    date: "Mar 5, 2024",
    rarity: "epic"
  },
  { 
    id: 4, 
    title: "Exam Ace", 
    description: "Score 90%+ on 5 exams", 
    icon: Star, 
    unlocked: true, 
    date: "Mar 12, 2024",
    rarity: "rare"
  },
  { 
    id: 5, 
    title: "Knowledge Seeker", 
    description: "Ask 100 AI questions", 
    icon: Brain, 
    unlocked: false, 
    progress: 78,
    rarity: "epic"
  },
  { 
    id: 6, 
    title: "Master Scholar", 
    description: "Read 25 books", 
    icon: Award, 
    unlocked: false, 
    progress: 60,
    rarity: "legendary"
  }
];

const recentActivity = [
  { type: "exam", title: "Psychology Fundamentals Quiz", score: "92%", time: "2 hours ago" },
  { type: "chat", title: "Asked about cognitive psychology", time: "5 hours ago" },
  { type: "book", title: "Added 'Introduction to Biology'", time: "1 day ago" },
  { type: "script", title: "Created lecture script", time: "2 days ago" },
  { type: "exam", title: "Calculus Practice Test", score: "88%", time: "3 days ago" }
];

const weeklyProgress = [
  { day: "Mon", books: 2, exams: 1, chats: 5 },
  { day: "Tue", books: 1, exams: 2, chats: 8 },
  { day: "Wed", books: 3, exams: 1, chats: 12 },
  { day: "Thu", books: 1, exams: 3, chats: 6 },
  { day: "Fri", books: 2, exams: 2, chats: 9 },
  { day: "Sat", books: 4, exams: 1, chats: 15 },
  { day: "Sun", books: 1, exams: 0, chats: 3 }
];

const getRarityColor = (rarity: string) => {
  switch (rarity) {
    case 'common': return 'text-gray-600 bg-gray-100';
    case 'rare': return 'text-blue-600 bg-blue-100';
    case 'epic': return 'text-purple-600 bg-purple-100';
    case 'legendary': return 'text-yellow-600 bg-yellow-100';
    default: return 'text-gray-600 bg-gray-100';
  }
};

const getActivityIcon = (type: string) => {
  switch (type) {
    case 'exam': return GraduationCap;
    case 'chat': return Brain;
    case 'book': return BookOpen;
    case 'script': return Trophy;
    default: return Activity;
  }
};

export default function Dashboard() {
  const navigate = useNavigate();
  const [selectedTab, setSelectedTab] = useState("overview");

  const progressToNextLevel = ((userData.totalPoints % 500) / 500) * 100;

  return (
    <div className="min-h-screen bg-gradient-to-br from-background via-background to-accent/5">
      <Header />
      
      <div className="container mx-auto px-4 py-8">
        <div className="max-w-7xl mx-auto">
          {/* Welcome Section */}
          <div className="mb-8">
            <div className="flex items-center justify-between mb-6">
              <div>
                <h1 className="text-3xl font-bold text-gradient-primary mb-2">
                  Welcome back, {userData.name}! 👋
                </h1>
                <p className="text-muted-foreground">
                  Here's your learning progress and achievements
                </p>
              </div>
              <div className="text-right">
                <div className="flex items-center gap-2 mb-2">
                  <Flame className="w-5 h-5 text-orange-500" />
                  <span className="font-bold text-orange-500">{userData.streak} day streak</span>
                </div>
                <Badge variant="secondary" className="bg-primary/10 text-primary">
                  Level {userData.level} {userData.userType}
                </Badge>
              </div>
            </div>

            {/* Level Progress */}
            <Card className="mb-6">
              <CardContent className="pt-6">
                <div className="flex items-center justify-between mb-2">
                  <span className="font-medium">Level {userData.level} Progress</span>
                  <span className="text-sm text-muted-foreground">
                    {userData.totalPoints} / {userData.nextLevelPoints} XP
                  </span>
                </div>
                <Progress value={progressToNextLevel} className="h-3" />
                <p className="text-xs text-muted-foreground mt-2">
                  {userData.nextLevelPoints - userData.totalPoints} XP until Level {userData.level + 1}
                </p>
              </CardContent>
            </Card>
          </div>

          {/* Stats Overview */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
            {stats.map((stat, index) => (
              <Card key={index} className="hover:shadow-lg transition-shadow duration-200">
                <CardContent className="pt-6">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm text-muted-foreground">{stat.label}</p>
                      <p className="text-2xl font-bold">{stat.value}</p>
                    </div>
                    <div className={`w-12 h-12 rounded-lg ${stat.bgColor} flex items-center justify-center`}>
                      <stat.icon className={`w-6 h-6 ${stat.color}`} />
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>

          {/* Main Content Tabs */}
          <Tabs value={selectedTab} onValueChange={setSelectedTab}>
            <TabsList className="grid w-full grid-cols-4">
              <TabsTrigger value="overview">Overview</TabsTrigger>
              <TabsTrigger value="achievements">Achievements</TabsTrigger>
              <TabsTrigger value="activity">Activity</TabsTrigger>
              <TabsTrigger value="analytics">Analytics</TabsTrigger>
            </TabsList>

            {/* Overview Tab */}
            <TabsContent value="overview" className="space-y-6">
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Recent Activity */}
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <Activity className="w-5 h-5 text-primary" />
                      Recent Activity
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-4">
                      {recentActivity.slice(0, 5).map((activity, index) => {
                        const Icon = getActivityIcon(activity.type);
                        return (
                          <div key={index} className="flex items-center gap-3 p-3 rounded-lg bg-muted/30">
                            <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center">
                              <Icon className="w-4 h-4 text-primary" />
                            </div>
                            <div className="flex-1">
                              <p className="font-medium text-sm">{activity.title}</p>
                              {activity.score && (
                                <Badge variant="secondary" className="mt-1">
                                  {activity.score}
                                </Badge>
                              )}
                            </div>
                            <span className="text-xs text-muted-foreground">{activity.time}</span>
                          </div>
                        );
                      })}
                    </div>
                  </CardContent>
                </Card>

                {/* Quick Actions */}
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <Zap className="w-5 h-5 text-primary" />
                      Quick Actions
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <Button 
                      onClick={() => navigate('/books/add')}
                      className="w-full justify-start"
                      variant="outline"
                    >
                      <Plus className="w-4 h-4 mr-2" />
                      Add New Book
                    </Button>
                    <Button 
                      onClick={() => navigate('/exams')}
                      className="w-full justify-start"
                      variant="outline"
                    >
                      <GraduationCap className="w-4 h-4 mr-2" />
                      Create Exam
                    </Button>
                    <Button 
                      onClick={() => navigate('/chat')}
                      className="w-full justify-start"
                      variant="outline"
                    >
                      <Brain className="w-4 h-4 mr-2" />
                      Chat with Books
                    </Button>
                    <Button 
                      onClick={() => navigate('/scripts')}
                      className="w-full justify-start"
                      variant="outline"
                    >
                      <Trophy className="w-4 h-4 mr-2" />
                      Create Script
                    </Button>
                  </CardContent>
                </Card>
              </div>

              {/* Goals Section */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Target className="w-5 h-5 text-primary" />
                    This Week's Goals
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div className="space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="text-sm font-medium">Read 3 Books</span>
                        <span className="text-sm text-muted-foreground">2/3</span>
                      </div>
                      <Progress value={67} className="h-2" />
                    </div>
                    <div className="space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="text-sm font-medium">Take 5 Exams</span>
                        <span className="text-sm text-muted-foreground">7/5</span>
                      </div>
                      <Progress value={100} className="h-2" />
                    </div>
                    <div className="space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="text-sm font-medium">Study 10 Hours</span>
                        <span className="text-sm text-muted-foreground">8/10</span>
                      </div>
                      <Progress value={80} className="h-2" />
                    </div>
                  </div>
                </CardContent>
              </Card>
            </TabsContent>

            {/* Achievements Tab */}
            <TabsContent value="achievements">
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Trophy className="w-5 h-5 text-primary" />
                    Achievements & Badges
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {achievements.map((achievement) => (
                      <div 
                        key={achievement.id}
                        className={`p-4 rounded-lg border-2 transition-all duration-200 ${
                          achievement.unlocked 
                            ? 'border-primary/20 bg-primary/5 hover:shadow-lg' 
                            : 'border-muted bg-muted/20 opacity-75'
                        }`}
                      >
                        <div className="flex items-start gap-3">
                          <div className={`w-12 h-12 rounded-lg flex items-center justify-center ${
                            achievement.unlocked ? 'bg-primary/10' : 'bg-muted'
                          }`}>
                            <achievement.icon className={`w-6 h-6 ${
                              achievement.unlocked ? 'text-primary' : 'text-muted-foreground'
                            }`} />
                          </div>
                          <div className="flex-1">
                            <div className="flex items-center gap-2 mb-1">
                              <h3 className="font-semibold">{achievement.title}</h3>
                              <Badge 
                                variant="secondary" 
                                className={`text-xs ${getRarityColor(achievement.rarity)}`}
                              >
                                {achievement.rarity}
                              </Badge>
                            </div>
                            <p className="text-sm text-muted-foreground mb-2">
                              {achievement.description}
                            </p>
                            {achievement.unlocked ? (
                              <div className="flex items-center gap-1 text-xs text-green-600">
                                <CheckCircle className="w-3 h-3" />
                                <span>Unlocked {achievement.date}</span>
                              </div>
                            ) : achievement.progress ? (
                              <div className="space-y-1">
                                <div className="flex justify-between text-xs">
                                  <span>Progress</span>
                                  <span>{achievement.progress}%</span>
                                </div>
                                <Progress value={achievement.progress} className="h-1" />
                              </div>
                            ) : (
                              <span className="text-xs text-muted-foreground">Locked</span>
                            )}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            </TabsContent>

            {/* Activity Tab */}
            <TabsContent value="activity">
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Calendar className="w-5 h-5 text-primary" />
                    Activity History
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    {recentActivity.map((activity, index) => {
                      const Icon = getActivityIcon(activity.type);
                      return (
                        <div key={index} className="flex items-center gap-4 p-4 rounded-lg border">
                          <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center">
                            <Icon className="w-5 h-5 text-primary" />
                          </div>
                          <div className="flex-1">
                            <p className="font-medium">{activity.title}</p>
                            {activity.score && (
                              <Badge variant="secondary" className="mt-1">
                                Score: {activity.score}
                              </Badge>
                            )}
                          </div>
                          <span className="text-sm text-muted-foreground">{activity.time}</span>
                        </div>
                      );
                    })}
                  </div>
                </CardContent>
              </Card>
            </TabsContent>

            {/* Analytics Tab */}
            <TabsContent value="analytics">
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <BarChart3 className="w-5 h-5 text-primary" />
                      Weekly Activity
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-4">
                      {weeklyProgress.map((day, index) => (
                        <div key={index} className="space-y-2">
                          <div className="flex justify-between text-sm">
                            <span className="font-medium">{day.day}</span>
                            <span className="text-muted-foreground">
                              {day.books + day.exams + Math.floor(day.chats / 5)} activities
                            </span>
                          </div>
                          <div className="flex gap-1 h-2">
                            <div 
                              className="bg-blue-500 rounded" 
                              style={{ width: `${(day.books / 5) * 100}%` }}
                            />
                            <div 
                              className="bg-purple-500 rounded" 
                              style={{ width: `${(day.exams / 3) * 100}%` }}
                            />
                            <div 
                              className="bg-green-500 rounded" 
                              style={{ width: `${(day.chats / 15) * 100}%` }}
                            />
                          </div>
                        </div>
                      ))}
                    </div>
                    <div className="flex gap-4 mt-4 text-xs">
                      <div className="flex items-center gap-1">
                        <div className="w-3 h-3 bg-blue-500 rounded" />
                        <span>Books</span>
                      </div>
                      <div className="flex items-center gap-1">
                        <div className="w-3 h-3 bg-purple-500 rounded" />
                        <span>Exams</span>
                      </div>
                      <div className="flex items-center gap-1">
                        <div className="w-3 h-3 bg-green-500 rounded" />
                        <span>AI Chats</span>
                      </div>
                    </div>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <TrendingUp className="w-5 h-5 text-primary" />
                      Learning Insights
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="p-3 rounded-lg bg-green-50 border border-green-200">
                      <h4 className="font-medium text-green-800 mb-1">Strong Performance</h4>
                      <p className="text-sm text-green-700">
                        Your exam scores have improved by 15% this month!
                      </p>
                    </div>
                    <div className="p-3 rounded-lg bg-blue-50 border border-blue-200">
                      <h4 className="font-medium text-blue-800 mb-1">Study Streak</h4>
                      <p className="text-sm text-blue-700">
                        You're on a {userData.streak}-day streak. Keep it up!
                      </p>
                    </div>
                    <div className="p-3 rounded-lg bg-purple-50 border border-purple-200">
                      <h4 className="font-medium text-purple-800 mb-1">Most Active Subject</h4>
                      <p className="text-sm text-purple-700">
                        Psychology accounts for 40% of your study time this week.
                      </p>
                    </div>
                    <div className="p-3 rounded-lg bg-orange-50 border border-orange-200">
                      <h4 className="font-medium text-orange-800 mb-1">Recommendation</h4>
                      <p className="text-sm text-orange-700">
                        Try reviewing Mathematics - it's been 3 days since your last session.
                      </p>
                    </div>
                  </CardContent>
                </Card>
              </div>
            </TabsContent>
          </Tabs>
        </div>
      </div>
    </div>
  );
}