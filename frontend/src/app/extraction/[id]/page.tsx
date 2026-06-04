'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useRouter } from 'next/navigation';
import axios from 'axios';
import { ExtractionTable } from '@/components/ExtractionTable';
import { PrimaryButton } from '@/components/ui/PrimaryButton';
import { Check, Edit2, ArrowLeft, XCircle } from 'lucide-react';

interface ExtractedRecord {
    [key: string]: any;
}

interface ExtractionResponse {
    document_id: string;
    category: string;
    filename?: string;
    extracted_records: ExtractedRecord[];
}

export default function ExtractionReviewPage() {
    const params = useParams();
    const router = useRouter();
    const documentId = params.id as string;

    const [extractionData, setExtractionData] = useState<ExtractionResponse | null>(null);
    const [records, setRecords] = useState<ExtractedRecord[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [isSaving, setIsSaving] = useState(false);
    const [isApproving, setIsApproving] = useState(false);
    const [errorMsg, setErrorMsg] = useState<string | null>(null);
    const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);

    const fetchExtraction = useCallback(async () => {
        setIsLoading(true);
        setErrorMsg(null);
        try {
            // Updated endpoint per user requirements
            const response = await axios.get(`http://127.0.0.1:8000/documents/${documentId}/extraction`);
            setExtractionData(response.data);
            setRecords(response.data.extracted_records || []);
            setHasUnsavedChanges(false);
        } catch (error: any) {
            console.error('Failed to fetch extraction data', error);
            setErrorMsg('Could not load extraction data. The document might not be extracted yet, or the backend is unreachable.');
        } finally {
            setIsLoading(false);
        }
    }, [documentId]);

    useEffect(() => {
        if (documentId) {
            fetchExtraction();
        }
    }, [documentId, fetchExtraction]);

    const handleUpdateRecord = (rowIndex: number, key: string, newValue: any) => {
        setRecords(currentRecords => {
            const newRecords = [...currentRecords];
            newRecords[rowIndex] = {
                ...newRecords[rowIndex],
                [key]: newValue
            };
            return newRecords;
        });
        setHasUnsavedChanges(true);
    };

    const handleUpdateData = async () => {
        setIsSaving(true);
        setErrorMsg(null);
        try {
            await axios.post(`http://127.0.0.1:8000/documents/${documentId}/update-extraction`, {
                extracted_records: records
            });
            setHasUnsavedChanges(false);
        } catch (error: any) {
            console.error('Failed to update extraction data', error);
            setErrorMsg('Failed to save changes to the backend.');
        } finally {
            setIsSaving(false);
        }
    };

    const handleApproveExtraction = async () => {
        setIsApproving(true);
        setErrorMsg(null);
        try {
            await axios.post(`http://127.0.0.1:8000/documents/${documentId}/approve-extraction`, {
                extracted_records: records
            });

            // Read the entity_id that was stored in localStorage during onboarding
            const entityId = localStorage.getItem('ninetales_entity_id');
            if (entityId) {
                router.push(`/analysis/${entityId}`);
            } else {
                // Fallback: no onboarding entity found — send user back to upload
                // with a helpful message
                alert('Extraction approved. Please complete onboarding first to view the Credit Decision Dashboard.');
                router.push('/upload');
            }
        } catch (error: any) {
            console.error('Failed to approve extraction', error);
            setErrorMsg('Failed to approve extraction. Please try again.');
        } finally {
            setIsApproving(false);
        }
    };

    return (
        <div className="w-full min-h-screen bg-slate-50">
            {/* Header / Branding */}
            <div className="bg-primary-500 shadow-md border-b-4 border-accent-500">
                <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex items-center justify-between">
                    <div>
                        <h1 className="text-2xl font-bold text-white tracking-tight">NineTales</h1>
                        <p className="text-primary-100 text-xs mt-0.5 font-medium tracking-wide uppercase">Enterprise Credit Underwriting System</p>
                    </div>
                </div>
            </div>

            <div className="relative z-10 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-8 pb-24">
                {/* Back Button & Title */}
                <div className="mb-6 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                    <div>
                        <button
                            onClick={() => router.push('/upload')}
                            className="text-sm font-medium text-slate-500 hover:text-primary-600 flex items-center mb-3 transition-colors"
                        >
                            <ArrowLeft className="w-4 h-4 mr-1" /> Back to Dashboard
                        </button>
                        <h2 className="text-2xl font-bold text-slate-900 tracking-tight flex items-center hidden">
                            Extraction Review
                        </h2>

                        {extractionData && (
                            <div className="mt-2 flex flex-wrap items-center gap-3">
                                <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-800 border border-slate-200">
                                    <span className="text-slate-500 mr-1.5 font-normal">File:</span>
                                    {extractionData.filename || 'Unknown'}
                                </span>
                                <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-indigo-50 text-indigo-700 border border-indigo-100">
                                    <span className="text-indigo-400 mr-1.5 font-normal">Category:</span>
                                    {extractionData.category}
                                </span>
                            </div>
                        )}
                    </div>

                    <div className="flex items-center gap-3">
                        <PrimaryButton
                            variant="outline"
                            onClick={handleUpdateData}
                            isLoading={isSaving}
                            disabled={!hasUnsavedChanges || isLoading}
                            leftIcon={<Edit2 className="w-4 h-4" />}
                        >
                            Update Data
                        </PrimaryButton>
                        <PrimaryButton
                            variant="accent"
                            onClick={handleApproveExtraction}
                            isLoading={isApproving}
                            disabled={isLoading}
                            leftIcon={<Check className="w-4 h-4" />}
                        >
                            Approve Extraction
                        </PrimaryButton>
                    </div>
                </div>

                {errorMsg && (
                    <div className="mb-6 p-4 bg-red-50 text-red-700 text-sm rounded-xl border border-red-200 flex items-start">
                        <XCircle className="w-5 h-5 mr-3 shrink-0 mt-0.5" />
                        {errorMsg}
                    </div>
                )}

                {/* Extraction Table Section */}
                <section className="bg-white rounded-2xl shadow-xl shadow-slate-200/40 border border-slate-100 overflow-hidden relative">
                    <div className="p-5 border-b border-slate-100 flex items-center justify-between bg-slate-50">
                        <h3 className="text-base font-semibold text-slate-800">Extracted Key-Value Pairs</h3>
                        {hasUnsavedChanges && (
                            <span className="text-xs font-medium text-amber-600 bg-amber-50 px-2 py-1 rounded-md border border-amber-200">
                                Unsaved changes
                            </span>
                        )}
                    </div>

                    <div className="p-0">
                        <ExtractionTable
                            records={records}
                            onUpdateRecord={handleUpdateRecord}
                            isLoading={isLoading}
                        />
                    </div>
                </section>
            </div>
        </div>
    );
}
