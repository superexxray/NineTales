'use client';

import React from 'react';
import { ReviewRow } from './ReviewRow';

interface Document {
    document_id: string;
    filename: string;
    model_prediction: string;
    confidence: number;
    final_category: string | null;
    status: 'awaiting_review' | 'approved' | 'corrected_by_user' | 'extraction_complete';
}

interface UploadedFilesTableProps {
    documents: Document[];
    onReviewActionComplete: () => void;
    isLoading?: boolean;
}

export function UploadedFilesTable({ documents, onReviewActionComplete, isLoading }: UploadedFilesTableProps) {

    if (isLoading) {
        return (
            <div className="w-full h-48 flex items-center justify-center bg-white rounded-xl border border-slate-200 shadow-sm shadow-slate-200/50">
                <div className="text-slate-400 font-medium flex items-center">
                    <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-primary-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    Loading documents...
                </div>
            </div>
        );
    }

    if (!documents || documents.length === 0) {
        return (
            <div className="w-full h-48 flex flex-col items-center justify-center bg-white rounded-xl border border-slate-200 shadow-sm shadow-slate-200/50 text-center px-6">
                <div className="w-12 h-12 bg-slate-50 rounded-full flex items-center justify-center mb-3">
                    <svg className="w-6 h-6 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
                    </svg>
                </div>
                <h4 className="text-sm font-semibold text-slate-700">No documents found</h4>
                <p className="text-xs text-slate-500 mt-1 max-w-sm">
                    Upload some files above to begin reviewing their classifications.
                </p>
            </div>
        );
    }

    return (
        <div className="w-full bg-white rounded-xl shadow-sm shadow-slate-200/50 overflow-hidden border border-slate-200">
            <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-slate-200">
                    <thead className="bg-slate-50">
                        <tr>
                            <th scope="col" className="px-6 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">
                                File Name
                            </th>
                            <th scope="col" className="px-6 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">
                                Predicted Category
                            </th>
                            <th scope="col" className="px-6 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">
                                Confidence
                            </th>
                            <th scope="col" className="px-6 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">
                                Status
                            </th>
                            <th scope="col" className="px-6 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">
                                Extraction
                            </th>
                            <th scope="col" className="px-6 py-3 text-right text-xs font-semibold text-slate-500 uppercase tracking-wider">
                                Actions
                            </th>
                        </tr>
                    </thead>
                    <tbody className="bg-white divide-y divide-slate-200">
                        {documents.map((doc) => (
                            <ReviewRow
                                key={doc.document_id}
                                document={doc}
                                onReviewActionComplete={onReviewActionComplete}
                            />
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
}
