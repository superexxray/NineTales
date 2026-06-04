'use client';

import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { FileDropzone } from '@/components/FileDropzone';
import { UploadedFilesTable } from '@/components/UploadedFilesTable';

export default function DocumentUploadPage() {
    const [documents, setDocuments] = useState([]);
    const [isLoading, setIsLoading] = useState(true);
    const [errorMsg, setErrorMsg] = useState<string | null>(null);

    const fetchDocuments = useCallback(async () => {
        setIsLoading(true);
        setErrorMsg(null);
        try {
            const response = await axios.get('http://127.0.0.1:8000/metadata');
            // Replace state entirely with backend response — never append/concat
            setDocuments(response.data);
        } catch (error: any) {
            console.error('Failed to fetch documents', error);
            setErrorMsg('Could not load existing documents. Ensure the backend is running.');
        } finally {
            setIsLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchDocuments();
    }, [fetchDocuments]);

    return (
        <div className="w-full min-h-screen bg-slate-50">
            {/* Decorative top background */}
            <div className="absolute top-0 inset-x-0 h-64 bg-gradient-to-b from-primary-900 mix-blend-multiply to-transparent opacity-5 z-0"></div>

            <div className="relative z-10 max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 pt-10 pb-24">

                {/* Page Header */}
                <div className="mb-10">
                    <h1 className="text-3xl font-bold text-slate-900 tracking-tight sm:text-4xl mb-3">
                        Document Upload & Review
                    </h1>
                    <p className="text-lg text-slate-600 max-w-3xl">
                        Upload enterprise documents to classify them across target categories. Review the ML predictions and approve or manually correct the structural mapping.
                    </p>
                </div>

                {/* Upload Section */}
                <section className="bg-white rounded-2xl shadow-xl shadow-slate-200/40 border border-slate-100 p-6 sm:p-8 mb-8 relative overflow-hidden">
                    <div className="flex items-center justify-between mb-6">
                        <div>
                            <h2 className="text-xl font-bold text-slate-800">1. Upload Documents</h2>
                            <p className="text-sm text-slate-500 mt-1">Add PDF, Excel, or CSV files to the pipeline.</p>
                        </div>
                    </div>

                    <FileDropzone onUploadComplete={fetchDocuments} />
                </section>

                {/* Review Section */}
                <section className="mb-8">
                    <div className="flex items-center justify-between mb-6 px-1">
                        <div>
                            <h2 className="text-xl font-bold text-slate-800">2. Classification Review</h2>
                            <p className="text-sm text-slate-500 mt-1">Review model predictions and provide human-in-the-loop oversight.</p>
                        </div>
                        <div className="flex items-center gap-4">
                            <button
                                onClick={fetchDocuments}
                                className="text-sm font-semibold text-primary-600 hover:text-primary-800 flex items-center transition"
                            >
                                <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path></svg>
                                Refresh
                            </button>
                        </div>
                    </div>

                    {errorMsg && (
                        <div className="mb-6 p-4 bg-red-50 text-red-700 text-sm rounded-xl border border-red-200 flex items-start">
                            <svg className="w-5 h-5 mr-3 shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path></svg>
                            {errorMsg}
                        </div>
                    )}

                    <UploadedFilesTable
                        documents={documents}
                        isLoading={isLoading}
                        onReviewActionComplete={fetchDocuments}
                    />
                </section>

            </div>
        </div>
    );
}
