'use client';

import React, { useState } from 'react';
import axios from 'axios';
import { Check, Edit2, X, AlertCircle } from 'lucide-react';
import { StatusBadge } from './ui/StatusBadge';
import { PrimaryButton } from './ui/PrimaryButton';
import { Select } from './ui/Select';
import { useRouter } from 'next/navigation';

const VALID_CATEGORIES = [
    "ALM",
    "Shareholding Pattern",
    "Borrowing Profile",
    "Annual Report",
    "Portfolio Performance"
];

interface ReviewRowProps {
    document: {
        document_id: string;
        filename: string;
        model_prediction: string;
        confidence: number;
        final_category: string | null;
        status: 'awaiting_review' | 'approved' | 'corrected_by_user' | 'extraction_complete';
    };
    onReviewActionComplete: () => void;
}

export function ReviewRow({ document, onReviewActionComplete }: ReviewRowProps) {
    const router = useRouter();
    const [isEditing, setIsEditing] = useState(false);
    const [selectedCategory, setSelectedCategory] = useState(document.model_prediction);
    const [isLoading, setIsLoading] = useState(false);

    const isReviewComplete = document.status !== 'awaiting_review';
    const displayCategory = document.final_category || document.model_prediction;

    const handleApprove = async () => {
        setIsLoading(true);
        try {
            await axios.post(`http://127.0.0.1:8000/review`, {
                document_id: document.document_id,
                final_category: document.model_prediction
            });
            onReviewActionComplete();
        } catch (error) {
            console.error("Approval failed", error);
            alert("Failed to approve classification.");
        } finally {
            setIsLoading(false);
        }
    };

    const handleCorrect = async () => {
        setIsLoading(true);
        try {
            await axios.post(`http://127.0.0.1:8000/review`, {
                document_id: document.document_id,
                final_category: selectedCategory
            });
            setIsEditing(false);
            onReviewActionComplete();
        } catch (error) {
            console.error("Correction failed", error);
            alert("Failed to correct classification.");
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <tr className="hover:bg-slate-50 transition-colors border-b border-slate-100 last:border-0 group">
            <td className="px-6 py-4 whitespace-nowrap">
                <div className="flex items-center">
                    <div className="ml-0">
                        <div className="text-sm font-medium text-slate-900">{document.filename}</div>
                        <div className="text-xs text-slate-500 font-mono">ID: {document.document_id.substring(0, 8)}...</div>
                    </div>
                </div>
            </td>
            <td className="px-6 py-4 whitespace-nowrap">
                {isEditing ? (
                    <div className="w-56">
                        <Select
                            label=""
                            value={selectedCategory}
                            onChange={(e) => setSelectedCategory(e.target.value)}
                            options={VALID_CATEGORIES.map(cat => ({ label: cat, value: cat }))}
                        />
                    </div>
                ) : (
                    <div className="text-sm text-slate-900 font-medium">
                        {displayCategory}
                    </div>
                )}
            </td>
            <td className="px-6 py-4 whitespace-nowrap">
                <div className="flex items-center">
                    <div className="w-16 h-2 bg-slate-200 rounded-full mr-2 overflow-hidden">
                        <div
                            className={`h-full rounded-full ${document.confidence > 0.8 ? 'bg-emerald-500' : document.confidence > 0.5 ? 'bg-amber-500' : 'bg-red-500'}`}
                            style={{ width: `${Math.round(document.confidence * 100)}%` }}
                        ></div>
                    </div>
                    <span className="text-sm text-slate-600">{Math.round(document.confidence * 100)}%</span>
                </div>
            </td>
            <td className="px-6 py-4 whitespace-nowrap">
                <StatusBadge status={document.status} />
            </td>
            <td className="px-6 py-4 whitespace-nowrap">
                <button
                    onClick={() => router.push(`/extraction/${document.document_id}`)}
                    style={{ backgroundColor: '#fc5639' }}
                    className="text-white text-xs font-semibold px-3 py-1.5 rounded-lg hover:opacity-90 transition-opacity shadow-sm whitespace-nowrap"
                >
                    Review Extraction
                </button>
            </td>
            <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                {!isReviewComplete && !isEditing && (
                    <div className="flex items-center justify-end gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                        <button
                            onClick={() => setIsEditing(true)}
                            className="px-3 py-1.5 text-slate-600 bg-white border border-slate-200 rounded hover:bg-slate-50 hover:text-primary-600 transition flex items-center text-xs font-semibold"
                        >
                            <Edit2 className="w-3.5 h-3.5 mr-1" /> Edit
                        </button>
                        <PrimaryButton
                            size="sm"
                            variant="accent"
                            isLoading={isLoading}
                            onClick={handleApprove}
                        >
                            <Check className="w-3.5 h-3.5 mr-1" /> Approve
                        </PrimaryButton>
                    </div>
                )}

                {!isReviewComplete && isEditing && (
                    <div className="flex items-center justify-end gap-2">
                        <button
                            onClick={() => { setIsEditing(false); setSelectedCategory(document.model_prediction); }}
                            className="p-1.5 text-slate-400 hover:text-red-500 transition rounded"
                            disabled={isLoading}
                        >
                            <X className="w-4 h-4" />
                        </button>
                        <PrimaryButton
                            size="sm"
                            variant="primary"
                            isLoading={isLoading}
                            onClick={handleCorrect}
                        >
                            Save
                        </PrimaryButton>
                    </div>
                )}

                {isReviewComplete && (
                    <div className="flex items-center justify-end gap-3">
                        <span className="text-slate-400 text-xs italic flex items-center">
                            <Check className="w-3.5 h-3.5 mr-1" /> Reviewed
                        </span>
                    </div>
                )}
            </td>
        </tr>
    );
}
