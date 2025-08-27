import React, { useState, useRef } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { 
  Upload, 
  FileAudio, 
  FileVideo, 
  Loader2, 
  CheckCircle, 
  AlertCircle,
  Play,
  Pause,
  Save,
  X
} from 'lucide-react';
import { transcribeAudio, extractAudioFromVideo } from '@/lib/transcription';

interface TranscriptionUploaderProps {
  onTranscriptionComplete: (transcription: string, metadata: { fileName: string; duration?: number; fileType: string; author?: string }) => void;
  onClose: () => void;
}

export default function TranscriptionUploader({ onTranscriptionComplete, onClose }: TranscriptionUploaderProps) {
  const [file, setFile] = useState<File | null>(null);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [transcription, setTranscription] = useState('');
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState('');
  const [isPlaying, setIsPlaying] = useState(false);
  const [editedTranscription, setEditedTranscription] = useState('');
  const [author, setAuthor] = useState('');
  
  const fileInputRef = useRef<HTMLInputElement>(null);
  const audioRef = useRef<HTMLAudioElement>(null);

  const acceptedFormats = '.mp3,.wav,.ogg,.m4a,.mp4,.webm,.mov,.avi';

  const handleFileSelect = (selectedFile: File) => {
    const maxSize = 100 * 1024 * 1024; // 100MB
    
    if (selectedFile.size > maxSize) {
      setError('File size must be less than 100MB');
      return;
    }

    const isAudio = selectedFile.type.startsWith('audio/');
    const isVideo = selectedFile.type.startsWith('video/');
    
    if (!isAudio && !isVideo) {
      setError('Please select an audio or video file');
      return;
    }

    setFile(selectedFile);
    setError('');
    setTranscription('');
    setEditedTranscription('');
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    const droppedFile = e.dataTransfer.files[0];
    if (droppedFile) {
      handleFileSelect(droppedFile);
    }
  };

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (selectedFile) {
      handleFileSelect(selectedFile);
    }
  };

  const startTranscription = async () => {
    if (!file) return;

    setIsTranscribing(true);
    setProgress(0);
    setError('');

    try {
      // Simulate progress for better UX
      const progressInterval = setInterval(() => {
        setProgress(prev => Math.min(prev + 10, 90));
      }, 500);

      let audioFile = file;
      
      // If it's a video file, extract audio first
      if (file.type.startsWith('video/')) {
        setProgress(20);
        try {
          const audioBlob = await extractAudioFromVideo(file);
          audioFile = new File([audioBlob], file.name.replace(/\.[^/.]+$/, '.wav'), { type: 'audio/wav' });
        } catch (videoError) {
          console.warn('Video audio extraction failed, trying direct transcription:', videoError);
          // Continue with original file if extraction fails
        }
      }

      setProgress(50);
      
      // Transcribe the audio
      const result = await transcribeAudio(audioFile);
      
      clearInterval(progressInterval);
      setProgress(100);
      
      setTranscription(result);
      setEditedTranscription(result);
      
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Transcription failed');
      setProgress(0);
    } finally {
      setIsTranscribing(false);
    }
  };

  const togglePlayback = () => {
    if (!audioRef.current || !file) return;

    if (isPlaying) {
      audioRef.current.pause();
    } else {
      audioRef.current.play();
    }
    setIsPlaying(!isPlaying);
  };

  const saveTranscription = () => {
    if (!file || !editedTranscription.trim()) return;

    const metadata = {
      fileName: file.name,
      fileType: file.type,
      duration: audioRef.current?.duration,
      author: author || 'Unknown'
    };

    onTranscriptionComplete(editedTranscription, metadata);
  };

  const getFileIcon = () => {
    if (!file) return <Upload className="w-8 h-8" />;
    return file.type.startsWith('video/') ? 
      <FileVideo className="w-8 h-8 text-purple-500" /> : 
      <FileAudio className="w-8 h-8 text-blue-500" />;
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">Media Transcription</h2>
          <p className="text-muted-foreground">Upload audio or video files to generate lecture scripts</p>
        </div>
        <Button variant="ghost" size="icon" onClick={onClose}>
          <X className="w-4 h-4" />
        </Button>
      </div>

      {/* File Upload */}
      <Card>
        <CardContent className="pt-6">
          <div
            className="border-2 border-dashed border-muted-foreground/25 rounded-lg p-8 text-center hover:border-primary/50 transition-colors cursor-pointer"
            onDrop={handleDrop}
            onDragOver={(e) => e.preventDefault()}
            onClick={() => fileInputRef.current?.click()}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept={acceptedFormats}
              onChange={handleFileInputChange}
              className="hidden"
            />
            
            <div className="space-y-4">
              {getFileIcon()}
              
              {file ? (
                <div>
                  <p className="font-medium">{file.name}</p>
                  <p className="text-sm text-muted-foreground">
                    {(file.size / (1024 * 1024)).toFixed(2)} MB • {file.type}
                  </p>
                  {file.type.startsWith('audio/') && (
                    <audio
                      ref={audioRef}
                      src={URL.createObjectURL(file)}
                      onLoadedMetadata={() => {
                        if (audioRef.current) {
                          console.log('Audio duration:', audioRef.current.duration);
                        }
                      }}
                      onEnded={() => setIsPlaying(false)}
                      className="hidden"
                    />
                  )}
                </div>
              ) : (
                <div>
                  <p className="font-medium">Drop your audio or video file here</p>
                  <p className="text-sm text-muted-foreground">or click to browse</p>
                  <p className="text-xs text-muted-foreground mt-2">
                    Supports: MP3, WAV, OGG, M4A, MP4, WebM, MOV, AVI (max 100MB)
                  </p>
                </div>
              )}
            </div>
          </div>

          {error && (
            <div className="mt-4 p-3 bg-destructive/10 border border-destructive/20 rounded-lg flex items-center gap-2">
              <AlertCircle className="w-4 h-4 text-destructive" />
              <span className="text-sm text-destructive">{error}</span>
            </div>
          )}

          {file && !isTranscribing && !transcription && (
            <div className="mt-4 flex gap-3">
              <Button onClick={startTranscription} className="bg-gradient-primary">
                <FileAudio className="w-4 h-4 mr-2" />
                Start Transcription
              </Button>
              
              {file.type.startsWith('audio/') && (
                <Button variant="outline" onClick={togglePlayback}>
                  {isPlaying ? <Pause className="w-4 h-4 mr-2" /> : <Play className="w-4 h-4 mr-2" />}
                  {isPlaying ? 'Pause' : 'Preview'}
                </Button>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Transcription Progress */}
      {isTranscribing && (
        <Card>
          <CardContent className="pt-6">
            <div className="space-y-4">
              <div className="flex items-center gap-3">
                <Loader2 className="w-5 h-5 animate-spin text-primary" />
                <span className="font-medium">Transcribing your media...</span>
              </div>
              
              <Progress value={progress} className="h-2" />
              
              <div className="text-sm text-muted-foreground">
                {progress < 20 && "Initializing AI model..."}
                {progress >= 20 && progress < 50 && "Processing media file..."}
                {progress >= 50 && progress < 90 && "Generating transcription..."}
                {progress >= 90 && "Finalizing results..."}
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Transcription Results */}
      {transcription && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="flex items-center gap-2">
                <CheckCircle className="w-5 h-5 text-green-500" />
                Transcription Complete
              </CardTitle>
              <Badge variant="secondary">
                {file?.type.startsWith('video/') ? 'Video' : 'Audio'} → Text
              </Badge>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <label className="text-sm font-medium mb-2 block">
                Author (Optional)
              </label>
              <Input
                value={author}
                onChange={(e) => setAuthor(e.target.value)}
                placeholder="Enter the speaker/lecturer name..."
                className="mb-4"
              />
            </div>

            <div>
              <label className="text-sm font-medium mb-2 block">
                Edit Transcription (Optional)
              </label>
              <Textarea
                value={editedTranscription}
                onChange={(e) => setEditedTranscription(e.target.value)}
                placeholder="Review and edit the transcription if needed..."
                className="min-h-[200px] text-sm leading-relaxed"
              />
              <p className="text-xs text-muted-foreground mt-2">
                {editedTranscription.length} characters • ~{Math.ceil(editedTranscription.split(' ').length / 150)} minutes reading time
              </p>
            </div>

            <div className="flex gap-3 pt-4">
              <Button 
                onClick={saveTranscription}
                disabled={!editedTranscription.trim()}
                className="bg-gradient-primary"
              >
                <Save className="w-4 h-4 mr-2" />
                Save as Script
              </Button>
              
              <Button 
                variant="outline" 
                onClick={() => {
                  setFile(null);
                  setTranscription('');
                  setEditedTranscription('');
                  setProgress(0);
                  setError('');
                }}
              >
                Upload Another File
              </Button>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}