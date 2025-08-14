import React from 'react';
import {
  Container,
  Typography,
  Box,
  Grid,
  Card,
  CardContent,
  CardActions,
  Button,
  Paper,
} from '@mui/material';
import {
  Upload as UploadIcon,
  Chat as ChatIcon,
  Book as BookIcon,
  QuestionAnswer as QuestionIcon,
  School as LectureIcon,
  Analytics as AnalyticsIcon,
} from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';

const HomePage = () => {
  const navigate = useNavigate();

  const features = [
    {
      title: 'Upload Documents',
      description: 'Upload PDF and text documents to create your knowledge base',
      icon: <UploadIcon sx={{ fontSize: 40 }} />,
      action: () => navigate('/upload'),
      color: '#1976d2',
    },
    {
      title: 'Browse Books',
      description: 'Explore your uploaded documents organized by categories',
      icon: <BookIcon sx={{ fontSize: 40 }} />,
      action: () => navigate('/books'),
      color: '#388e3c',
    },
    {
      title: 'AI Chat',
      description: 'Chat with your documents using advanced AI technology',
      icon: <ChatIcon sx={{ fontSize: 40 }} />,
      action: () => navigate('/chat'),
      color: '#f57c00',
    },
    {
      title: 'Generate Questions',
      description: 'Automatically generate quiz questions from your documents',
      icon: <QuestionIcon sx={{ fontSize: 40 }} />,
      action: () => navigate('/chat'),
      color: '#7b1fa2',
    },
    {
      title: 'Create Lectures',
      description: 'Generate structured lectures and presentations',
      icon: <LectureIcon sx={{ fontSize: 40 }} />,
      action: () => navigate('/chat'),
      color: '#c2185b',
    },
    {
      title: 'Analytics',
      description: 'Track usage and performance metrics',
      icon: <AnalyticsIcon sx={{ fontSize: 40 }} />,
      action: () => {},
      color: '#455a64',
    },
  ];

  return (
    <Container maxWidth="lg">
      <Box sx={{ py: 4 }}>
        {/* Hero Section */}
        <Paper
          elevation={3}
          sx={{
            p: 6,
            mb: 6,
            background: 'linear-gradient(135deg, #1976d2 0%, #42a5f5 100%)',
            color: 'white',
            textAlign: 'center',
          }}
        >
          <Typography variant="h1" component="h1" gutterBottom>
            Welcome to Zakerly
          </Typography>
          <Typography variant="h5" component="h2" sx={{ mb: 3, opacity: 0.9 }}>
            Enterprise AI-Powered Document Intelligence Platform
          </Typography>
          <Typography variant="body1" sx={{ mb: 4, fontSize: '1.1rem' }}>
            Transform your documents into intelligent, interactive knowledge bases.
            Upload, chat, generate questions, and create lectures with advanced AI technology.
          </Typography>
          <Button
            variant="contained"
            size="large"
            onClick={() => navigate('/upload')}
            sx={{
              backgroundColor: 'white',
              color: '#1976d2',
              px: 4,
              py: 1.5,
              fontSize: '1.1rem',
              '&:hover': {
                backgroundColor: '#f5f5f5',
              },
            }}
          >
            Get Started
          </Button>
        </Paper>

        {/* Features Grid */}
        <Typography variant="h2" component="h2" gutterBottom sx={{ mb: 4, textAlign: 'center' }}>
          Platform Features
        </Typography>

        <Grid container spacing={4}>
          {features.map((feature, index) => (
            <Grid item xs={12} md={6} lg={4} key={index}>
              <Card
                elevation={2}
                sx={{
                  height: '100%',
                  display: 'flex',
                  flexDirection: 'column',
                  transition: 'transform 0.2s, box-shadow 0.2s',
                  '&:hover': {
                    transform: 'translateY(-4px)',
                    boxShadow: 4,
                  },
                }}
              >
                <CardContent sx={{ flexGrow: 1, textAlign: 'center', p: 3 }}>
                  <Box
                    sx={{
                      color: feature.color,
                      mb: 2,
                    }}
                  >
                    {feature.icon}
                  </Box>
                  <Typography variant="h6" component="h3" gutterBottom>
                    {feature.title}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    {feature.description}
                  </Typography>
                </CardContent>
                <CardActions sx={{ justifyContent: 'center', pb: 2 }}>
                  <Button
                    size="small"
                    onClick={feature.action}
                    sx={{ color: feature.color }}
                  >
                    Learn More
                  </Button>
                </CardActions>
              </Card>
            </Grid>
          ))}
        </Grid>

        {/* Stats Section */}
        <Paper elevation={1} sx={{ mt: 6, p: 4, textAlign: 'center' }}>
          <Typography variant="h4" component="h3" gutterBottom>
            Enterprise Ready
          </Typography>
          <Grid container spacing={4} sx={{ mt: 2 }}>
            <Grid item xs={12} sm={4}>
              <Typography variant="h3" color="primary" gutterBottom>
                99.9%
              </Typography>
              <Typography variant="body1">Uptime</Typography>
            </Grid>
            <Grid item xs={12} sm={4}>
              <Typography variant="h3" color="primary" gutterBottom>
              </Typography>
              <Typography variant="body1">Response Time</Typography>
            </Grid>
            <Grid item xs={12} sm={4}>
              <Typography variant="h3" color="primary" gutterBottom>
                24/7
              </Typography>
              <Typography variant="body1">Support</Typography>
            </Grid>
          </Grid>
        </Paper>
      </Box>
    </Container>
  );
};

export default HomePage;