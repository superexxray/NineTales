import React from 'react';
import { ShieldCheck, IndianRupee } from 'lucide-react';

interface RecommendationCardProps {
    loanRecommendation: string;
    recommendedAmount: number;
}

export function RecommendationCard({ loanRecommendation, recommendedAmount }: RecommendationCardProps) {
    const formattedAmount = new Intl.NumberFormat('en-IN', {
        style: 'currency',
        currency: 'INR',
        maximumFractionDigits: 0
    }).format(recommendedAmount);

    return (
        <div className="bg-gradient-to-br from-primary-900 to-primary-800 rounded-2xl shadow-md border border-primary-700 p-6 flex flex-col justify-between h-full text-white relative overflow-hidden">
            {/* Background design graphic */}
            <div className="absolute -right-6 -top-6 w-32 h-32 bg-white opacity-5 rounded-full blur-2xl"></div>
            <div className="absolute right-10 bottom-10 w-24 h-24 bg-accent-500 opacity-20 rounded-full blur-xl"></div>

            <div className="relative z-10">
                <div className="flex items-center justify-between mb-2">
                    <h3 className="text-sm font-semibold text-primary-200 uppercase tracking-wider">Final Recommendation</h3>
                    <ShieldCheck className="w-6 h-6 text-accent-400" />
                </div>

                <div className="mt-4 break-words">
                    <span className="text-2xl sm:text-3xl font-bold text-white leading-tight">
                        {loanRecommendation}
                    </span>
                </div>
            </div>

            <div className="mt-6 pt-5 border-t border-primary-700/50 relative z-10">
                <p className="text-xs font-medium text-primary-300 uppercase tracking-wide mb-1">Recommended Loan Amount</p>
                <div className="flex items-center">
                    <span className="text-2xl font-bold text-accent-400 flex items-center">
                        {formattedAmount}
                    </span>
                </div>
            </div>
        </div>
    );
}
