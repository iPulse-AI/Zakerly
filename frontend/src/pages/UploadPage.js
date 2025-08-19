import React, { useState, useCallback } from 'react';
import {
  Container,
  Typography,
  Box,
  Paper,
  Button,
  Alert,
  CircularProgress,
  LinearProgress,
  Chip,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Divider,
} from '@mui/material';
import {
  CloudUpload as UploadIcon,
  Description as FileIcon,
  CheckCircle as SuccessIcon,
  Error as ErrorIcon,
} from '@mui/icons-material';
import { useDropzone } from 'react-dropzone';
import axios from 'axios';

const UploadPage = () => {
  const [uploadStatus, setUploadStatus] = useState('idle'); // idle, uploading, success, error
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadedFiles, setUploadedFiles] = useState([]);
  const [errorMessage, setErrorMessage] = useState('');
  const [successMessage, setSuccessMessage] = useState('');

  const onDrop = useCallback(async (acceptedFiles) => {
    for (const file of acceptedFiles) {
      await uploadFile(file);
    }
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
      'text/plain': ['.txt'],
      'text/markdown': ['.md'],
      'application/msword': ['.doc'],
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
    },
    multiple: true,
  });

  const uploadFile = async (file) => {
    setUploadStatus('uploading');
    setUploadProgress(0);
    setErrorMessage('');
    setSuccessMessage('');

    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await axios.post('/api/v1/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        onUploadProgress: (progressEvent) => {
          const progress = Math.round(
            (progressEvent.loaded * 100) / progressEvent.total
          );
          setUploadProgress(progress);
        },
      });

      setUploadedFiles(prev => [...prev, {
        ...response.data,
        uploadedAt: new Date().toISOString(),
      }]);
      
      setUploadStatus('success');
      setSuccessMessage(`Successfully uploaded "${file.name}"`);
      
    } catch (error) {
      setUploadStatus('error');
      
      // Handle different error types
      if (error.response?.status === 409) {
        // Duplicate book
        setErrorMessage(
          error.response?.data?.detail || 
          `This book already exists in your library.`
        );
      } else if (error.response?.status === 400) {
        // Bad request (unsupported file type, etc.)
        setErrorMessage(
          error.response?.data?.detail || 
          `Invalid file: ${error.message}`
        );
      } else if (error.response?.status >= 500) {
        // Server error
        setErrorMessage(
          `Server error while processing "${file.name}". Please try again later.`
        );
      } else {
        // Generic error
        setErrorMessage(
          error.response?.data?.detail || 
          `Failed to upload "${file.name}": ${error.message}`
        );
      }
    }
  };

  const supportedFormats = [
    { format: 'PDF', description: 'Portable Document Format (.pdf)' },
    { format: 'TXT', description: 'Plain Text (.txt)' },
    { format: 'MD', description: 'Markdown (.md)' },
    { format: 'DOC', description: 'Microsoft Word (.doc)' },
    { format: 'DOCX', description: 'Microsoft Word (.docx)' },
  ];

  return (
    <Container maxWidth="md">
      <Box sx={{ py: 4 }}>
        <Typography variant="h2" component="h1" gutterBottom align="center">
          Upload Documents
        </Typography>
        <Typography variant="body1" align="center" sx={{ mb: 4, color: 'text.secondary' }}>
          Upload your documents to create an intelligent knowledge base
        </Typography>

        {/* Upload Area */}
        <Paper
          {...getRootProps()}
          elevation={2}
          sx={{
            p: 6,
            mb: 4,
            textAlign: 'center',
            border: '2px dashed',
            borderColor: isDragActive ? 'primary.main' : 'grey.300',
            backgroundColor: isDragActive ? 'action.hover' : 'background.paper',
            cursor: 'pointer',
            transition: 'all 0.2s ease-in-out',
            '&:hover': {
              borderColor: 'primary.main',
              backgroundColor: 'action.hover',
            },
          }}
        >
          <input {...getInputProps()} />
          <UploadIcon sx={{ fontSize: 64, color: 'primary.main', mb: 2 }} />
          <Typography variant="h5" gutterBottom>
            {isDragActive ? 'Drop files here' : 'Drag & drop files here'}
          </Typography>
          <Typography variant="body1" color="text.secondary" sx={{ mb: 2 }}>
            or click to select files
          </Typography>
          <Button variant="contained" size="large">
            Choose Files
          </Button>
        </Paper>

        {/* Upload Progress */}
        {uploadStatus === 'uploading' && (
          <Paper elevation={1} sx={{ p: 3, mb: 3 }}>
            <Typography variant="h6" gutterBottom>
              Uploading... {uploadProgress}%
            </Typography>
            <LinearProgress variant="determinate" value={uploadProgress} />
          </Paper>
        )}

        {/* Status Messages */}
        {uploadStatus === 'success' && successMessage && (
          <Alert severity="success" sx={{ mb: 3 }} icon={<SuccessIcon />}>
            {successMessage}
          </Alert>
        )}

        {uploadStatus === 'error' && errorMessage && (
          <Alert severity="error" sx={{ mb: 3 }} icon={<ErrorIcon />}>
            {errorMessage}
          </Alert>
        )}

        {/* Uploaded Files List */}
        {uploadedFiles.length > 0 && (
          <Paper elevation={1} sx={{ mb: 4 }}>
            <Box sx={{ p: 2 }}>
              <Typography variant="h6" gutterBottom>
                Recently Uploaded Files
              </Typography>
            </Box>
            <Divider />
            <List>
              {uploadedFiles.map((file, index) => (
                <ListItem key={index}>
                  <ListItemIcon>
                    <FileIcon color="primary" />
                  </ListItemIcon>
                  <ListItemText
                    primary={file.title}
                    secondary={
                      <Box>
                        <Typography variant="body2" color="text.secondary">
                          Author: {file.author || 'Unknown'} | 
                          Year: {file.publication_year || 'Unknown'} | 
                          Category: {file.category_id}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          Uploaded: {new Date(file.uploadedAt).toLocaleString()}
                        </Typography>
                      </Box>
                    }
                  />
                  <Chip
                    label="Processed"
                    color="success"
                    size="small"
                    icon={<SuccessIcon />}
                  />
                </ListItem>
              ))}
            </List>
          </Paper>
        )}

        {/* Supported Formats */}
        <Paper elevation={1} sx={{ p: 3 }}>
          <Typography variant="h6" gutterBottom>
            Supported File Formats
          </Typography>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 2 }}>
            {supportedFormats.map((format) => (
              <Chip
                key={format.format}
                label={format.format}
                variant="outlined"
                color="primary"
              />
            ))}
          </Box>
          <List dense>
            {supportedFormats.map((format) => (
              <ListItem key={format.format} sx={{ py: 0.5 }}>
                <ListItemText
                  primary={format.format}
                  secondary={format.description}
                />
              </ListItem>
            ))}
          </List>
        </Paper>

        {/* Upload Guidelines */}
        <Paper elevation={1} sx={{ p: 3, mt: 3, backgroundColor: 'info.light', color: 'info.contrastText' }}>
          <Typography variant="h6" gutterBottom>
            Upload Guidelines
          </Typography>
          <Typography variant="body2" component="div">
            <ul>
              <li>Maximum file size: 50MB per file</li>
              <li>Files are automatically processed and indexed</li>
              <li>Duplicate files (same content) will be detected and rejected</li>
              <li>Processing time depends on file size and complexity</li>
              <li>All uploaded content is encrypted and secure</li>
            </ul>
          </Typography>
        </Paper>
      </Box>
    </Container>
  );
};

export default UploadPage;