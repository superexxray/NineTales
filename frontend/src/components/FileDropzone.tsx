'use client';

import React, { useState, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { UploadCloud, File, X, Loader2 } from 'lucide-react';
import axios from 'axios';

interface FileDropzoneProps {
    onUploadComplete?: () => void;
}

export function FileDropzone({ onUploadComplete }: FileDropzoneProps) {
    const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
    const [isUploading, setIsUploading] = useState(false);
    const [uploadProgress, setUploadProgress] = useState(0);
    const [errorMsg, setErrorMsg] = useState<string | null>(null);

    const onDrop = useCallback((acceptedFiles: File[]) => {
        setSelectedFiles(prev => {
            const fileMap = new Map();
            [...prev, ...acceptedFiles].forEach(f => {
                fileMap.set(f.name, f);
            });
            return Array.from(fileMap.values());
        });
        setErrorMsg(null);
    }, []);

    const { getRootProps, getInputProps, isDragActive } = useDropzone({
        onDrop,
        accept: {
            'application/pdf': ['.pdf'],
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
            'application/vnd.ms-excel': ['.xls'],
            'text/csv': ['.csv']
        }
    });

    const removeFile = (index: number) => {
        setSelectedFiles(prev => prev.filter((_, i) => i !== index));
    };

    const handleUpload = async () => {
        if (selectedFiles.length === 0) return;

        setIsUploading(true);
        setErrorMsg(null);
        setUploadProgress(0);

        try {
            // We upload files sequentially to simulate individual progress
            for (let i = 0; i < selectedFiles.length; i++) {
                const file = selectedFiles[i];
                const formData = new FormData();
                formData.append('file', file);

                await axios.post('http://127.0.0.1:8000/classify', formData, {
                    headers: {
                        'Content-Type': 'multipart/form-data'
                    }
                });

                setUploadProgress(Math.round(((i + 1) / selectedFiles.length) * 100));
            }

            setSelectedFiles([]);
            if (onUploadComplete) onUploadComplete();
        } catch (error: any) {
            console.error('Upload failed', error);
            setErrorMsg(error.response?.data?.detail || 'An error occurred while uploading. Please try again.');
        } finally {
            setIsUploading(false);
            setUploadProgress(0);
        }
    };

    return (
        <div className="w-full">
            <div
                {...getRootProps()}
                className={`
          border-2 border-dashed rounded-xl p-10 flex flex-col items-center justify-center transition-all cursor-pointer
          ${isDragActive ? 'border-primary-500 bg-primary-50' : 'border-slate-300 bg-slate-50 hover:bg-slate-100 hover:border-slate-400'}
          ${isUploading ? 'opacity-50 pointer-events-none' : ''}
        `}
            >
                <input {...getInputProps()} />
                <div className="w-16 h-16 rounded-full bg-primary-100 flex items-center justify-center mb-4">
                    <UploadCloud className="w-8 h-8 text-primary-600" />
                </div>
                <h3 className="text-lg font-semibold text-slate-800 mb-1">
                    {isDragActive ? 'Drop files here' : 'Drag & drop files here'}
                </h3>
                <p className="text-sm text-slate-500 mb-4 text-center">
                    Support formats: PDF, XLSX, XLS, CSV. Maximum file size 50MB.
                </p>
                <div className="px-6 py-2 bg-white rounded-lg border border-slate-200 text-sm font-medium text-slate-700 shadow-sm">
                    Browse Files
                </div>
            </div>

            {/* Selected Files List */}
            {selectedFiles.length > 0 && (
                <div className="mt-6">
                    <h4 className="text-sm font-semibold text-slate-700 mb-3">Selected Files ({selectedFiles.length})</h4>
                    <div className="space-y-2 mb-6">
                        {selectedFiles.map((file, idx) => (
                            <div key={`${file.name}-${idx}`} className="flex items-center justify-between p-3 bg-white border border-slate-200 rounded-lg">
                                <div className="flex items-center">
                                    <File className="w-5 h-5 text-slate-400 mr-3" />
                                    <div>
                                        <p className="text-sm font-medium text-slate-800 truncate max-w-xs sm:max-w-md">{file.name}</p>
                                        <p className="text-xs text-slate-500">{(file.size / 1024 / 1024).toFixed(2)} MB</p>
                                    </div>
                                </div>
                                {!isUploading && (
                                    <button
                                        onClick={() => removeFile(idx)}
                                        className="p-1 text-slate-400 hover:text-red-500 hover:bg-red-50 rounded transition-colors"
                                    >
                                        <X className="w-4 h-4" />
                                    </button>
                                )}
                            </div>
                        ))}
                    </div>

                    {errorMsg && (
                        <div className="mb-4 p-3 bg-red-50 text-red-700 text-sm rounded-lg border border-red-200">
                            {errorMsg}
                        </div>
                    )}

                    {isUploading && uploadProgress > 0 && (
                        <div className="mb-4">
                            <div className="flex justify-between text-xs mb-1 font-medium text-primary-700">
                                <span>Uploading...</span>
                                <span>{uploadProgress}%</span>
                            </div>
                            <div className="w-full h-2 bg-slate-200 rounded-full overflow-hidden">
                                <div
                                    className="h-full bg-primary-500 rounded-full transition-all duration-300"
                                    style={{ width: `${uploadProgress}%` }}
                                ></div>
                            </div>
                        </div>
                    )}

                    <div className="flex justify-end">
                        <button
                            onClick={handleUpload}
                            disabled={isUploading}
                            className="bg-accent-500 text-white font-semibold flex items-center py-2.5 px-6 rounded-lg hover:bg-accent-600 transition shadow-sm disabled:opacity-70 disabled:cursor-not-allowed"
                        >
                            {isUploading ? (
                                <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Uploading</>
                            ) : (
                                'Upload All Files'
                            )}
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
}
