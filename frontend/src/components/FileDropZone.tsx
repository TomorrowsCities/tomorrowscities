import React, { useCallback, useState } from 'react';
import { useDropzone } from 'react-dropzone';
import {
  Box,
  Typography,
  LinearProgress,
  Alert,
  Paper
} from '@mui/material';
import { CloudUpload } from '@mui/icons-material';
import { uploadFile } from '../services/api';

interface FileDropZoneProps {
  onFileUpload: (data: any, fileName: string) => void;
  accept?: Record<string, string[]>;
  multiple?: boolean;
}

const FileDropZone: React.FC<FileDropZoneProps> = ({
  onFileUpload,
  accept = {
    'application/json': ['.json', '.geojson'],
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
    'text/csv': ['.csv']
  },
  multiple = false
}) => {
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const onDrop = useCallback(async (acceptedFiles: File[]) => {
    setUploading(true);
    setError(null);
    setProgress(0);

    try {
      for (const file of acceptedFiles) {
        const formData = new FormData();
        formData.append('file', file);

        const result = await uploadFile(formData, (progressEvent: any) => {
          const percentCompleted = Math.round(
            (progressEvent.loaded * 100) / progressEvent.total
          );
          setProgress(percentCompleted);
        });

        onFileUpload(result.data.data, file.name);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed');
    } finally {
      setUploading(false);
      setProgress(0);
    }
  }, [onFileUpload]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept,
    multiple
  });

  return (
    <Paper
      {...getRootProps()}
      sx={{
        p: 3,
        border: '2px dashed',
        borderColor: isDragActive ? 'primary.main' : 'grey.300',
        backgroundColor: isDragActive ? 'action.hover' : 'background.paper',
        cursor: 'pointer',
        textAlign: 'center',
        mb: 2
      }}
    >
      <input {...getInputProps()} />
      <CloudUpload sx={{ fontSize: 48, color: 'grey.400', mb: 2 }} />
      
      {uploading ? (
        <Box>
          <Typography variant="body2" gutterBottom>
            Uploading... {progress}%
          </Typography>
          <LinearProgress variant="determinate" value={progress} />
        </Box>
      ) : (
        <Typography variant="body1">
          {isDragActive
            ? 'Drop the files here...'
            : 'Drag and drop files here, or click to select files'}
        </Typography>
      )}

      {error && (
        <Alert severity="error" sx={{ mt: 2 }}>
          {error}
        </Alert>
      )}
    </Paper>
  );
};

export default FileDropZone;
