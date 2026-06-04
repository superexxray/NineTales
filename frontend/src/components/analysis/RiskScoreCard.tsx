import React from 'react';
import { Activity } from 'lucide-react';

interface RiskScoreCardProps {
    riskScore: number;
    riskLevel: string;
}

export function RiskScoreCard({ riskScore, riskLevel }: RiskScoreCardProps) {
    // Determine color based on risk score (higher is safer)
    let scoreColor = 'text-red-500';
    let bgColor = 'bg-red-50';
    let borderColor = 'border-red-200';

    if (riskScore >= 75) {
        scoreColor = 'text-emerald-500';
        bgColor = 'bg-emerald-50';
        borderColor = 'border-emerald-200';
    } else if (riskScore >= 40) {
        scoreColor = 'text-amber-500';
        bgColor = 'bg-amber-50';
        borderColor = 'border-amber-200';
    }

    return (
        <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6 flex flex-col justify-between h-full">
            <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-semibold text-slate-500 uppercase tracking-wider">Overall Risk Score</h3>
                <Activity className="w-5 h-5 text-slate-400" />
            </div>

            <div className="flex items-end gap-3 mb-2">
                <span className={`text-5xl font-extrabold ${scoreColor}`}>
                    {riskScore.toFixed(0)}
                </span>
                <span className="text-lg font-semibold text-slate-400 mb-1">/ 100</span>
            </div>

            <div className={`mt-4 inline-flex items-center px-3 py-1 rounded-full text-sm font-semibold border ${bgColor} ${scoreColor} ${borderColor} w-fit`}>
                Risk Level: {riskLevel}
            </div>
        </div>
    );
}
