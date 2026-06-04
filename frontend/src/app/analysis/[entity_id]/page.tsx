'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useRouter } from 'next/navigation';
import axios from 'axios';
import { ArrowLeft, Loader2, AlertCircle, Download } from 'lucide-react';
import { RiskScoreCard } from '@/components/analysis/RiskScoreCard';
import { RecommendationCard } from '@/components/analysis/RecommendationCard';
import { SWOTPanel } from '@/components/analysis/SWOTPanel';
import { FinancialSummaryCards } from '@/components/analysis/FinancialSummaryCards';

interface SWOTData {
    strengths: string[];
    weaknesses: string[];
    opportunities: string[];
    threats: string[];
}

interface FinancialSummary {
    revenue: number;
    ebitda: number;
    net_profit: number;
    total_debt: number;
}

interface AnalysisResponse {
    entity_id: string;
    risk_score: number;
    risk_level: string;
    loan_recommendation: string;
    recommended_amount: number;
    swot_analysis: SWOTData;
    financial_summary: FinancialSummary;
}

export default function CreditDecisionDashboard() {
    const params = useParams();
    const router = useRouter();
    const entityId = params.entity_id as string;

    const [data, setData] = useState<AnalysisResponse | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [errorMsg, setErrorMsg] = useState<string | null>(null);

    const fetchAnalysis = useCallback(async () => {
        setIsLoading(true);
        setErrorMsg(null);
        try {
            const response = await axios.get(`http://127.0.0.1:8000/analysis/${entityId}`);
            setData(response.data);
        } catch (error: any) {
            console.error('Failed to load credit analysis', error);
            setErrorMsg(error.response?.data?.detail || 'Failed to generate credit analysis. Ensure backend is running and OPENAI API key is set.');
        } finally {
            setIsLoading(false);
        }
    }, [entityId]);

    useEffect(() => {
        if (entityId) {
            fetchAnalysis();
        }
    }, [entityId, fetchAnalysis]);

    const handleDownloadReport = async () => {
        try {
            const response = await axios.get(`http://127.0.0.1:8000/analysis/${entityId}/report`, {
                responseType: 'blob',
            });
            const url = window.URL.createObjectURL(new Blob([response.data]));
            const link = document.createElement('a');
            link.href = url;
            link.setAttribute('download', `Credit_Report_${entityId.substring(0, 8)}.pdf`);
            document.body.appendChild(link);
            link.click();
            link.parentNode?.removeChild(link);
            window.URL.revokeObjectURL(url);
        } catch (error) {
            console.error('Failed to download report', error);
            alert('Failed to download PDF report. Ensure backend is running.');
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
                <div className="mb-6">
                    <button
                        onClick={() => router.push('/upload')}
                        className="text-sm font-medium text-slate-500 hover:text-primary-600 flex items-center mb-3 transition-colors"
                    >
                        <ArrowLeft className="w-4 h-4 mr-1" /> Back to Upload Dashboard
                    </button>
                    <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between">
                        <h2 className="text-2xl font-bold text-slate-900 tracking-tight">
                            Credit Decision Dashboard
                        </h2>
                        {data && (
                            <div className="mt-2 sm:mt-0 flex flex-wrap items-center gap-3">
                                <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-slate-200 text-slate-700">
                                    Entity Map: {data.entity_id.substring(0, 8)}...
                                </span>
                                <button
                                    onClick={handleDownloadReport}
                                    className="inline-flex items-center px-4 py-2 rounded-lg text-sm font-semibold bg-accent-500 text-white hover:bg-accent-600 transition-colors shadow-sm"
                                >
                                    <Download className="w-4 h-4 mr-2" />
                                    Download Report
                                </button>
                            </div>
                        )}
                    </div>
                    <p className="text-slate-500 text-sm mt-1">Holistic risk evaluation generated by AI using extracted financials and current news signals.</p>
                </div>

                {isLoading && (
                    <div className="w-full h-64 flex flex-col items-center justify-center bg-white rounded-2xl border border-slate-200 shadow-sm">
                        <Loader2 className="w-10 h-10 text-accent-500 animate-spin mb-4" />
                        <p className="text-slate-600 font-medium text-lg">Generating Credit Analysis...</p>
                        <p className="text-slate-400 text-sm mt-1">Aggregating extracted records, querying FinBERT, and running risk models.</p>
                    </div>
                )}

                {errorMsg && !isLoading && (
                    <div className="w-full p-6 bg-red-50 text-red-700 rounded-2xl border border-red-200 flex flex-col items-center text-center">
                        <AlertCircle className="w-10 h-10 mb-3 text-red-500" />
                        <h3 className="font-bold text-lg mb-1">Analysis Failed</h3>
                        <p className="text-sm max-w-lg">{errorMsg}</p>
                        <button
                            onClick={fetchAnalysis}
                            className="mt-4 px-4 py-2 bg-red-100 hover:bg-red-200 text-red-800 rounded-lg text-sm font-semibold transition-colors"
                        >
                            Try Again
                        </button>
                    </div>
                )}

                {data && !isLoading && (
                    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
                        {/* Financial Summary Strip */}
                        <FinancialSummaryCards summary={data.financial_summary} />

                        {/* Middle Cards: Risk Score & Recommendation */}
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                            <RiskScoreCard riskScore={data.risk_score} riskLevel={data.risk_level} />
                            <RecommendationCard
                                loanRecommendation={data.loan_recommendation}
                                recommendedAmount={data.recommended_amount}
                            />
                        </div>

                        {/* Bottom Panel: SWOT */}
                        <SWOTPanel swot={data.swot_analysis} />
                    </div>
                )}
            </div>
        </div>
    );
}
