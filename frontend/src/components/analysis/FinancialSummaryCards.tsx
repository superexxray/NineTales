import React from 'react';
import { DollarSign, Landmark, ArrowDownCircle, ArrowUpCircle } from 'lucide-react';

interface FinancialSummary {
    revenue: number;
    ebitda: number;
    net_profit: number;
    total_debt: number;
}

interface FinancialSummaryCardsProps {
    summary: FinancialSummary;
}

export function FinancialSummaryCards({ summary }: FinancialSummaryCardsProps) {
    const formatCurrency = (val: number) => {
        if (!val) return '₹0';
        // For large numbers, show Cr/Lakh formatting if you prefer, but standard INR is fine
        return new Intl.NumberFormat('en-IN', {
            style: 'currency',
            currency: 'INR',
            maximumFractionDigits: 0
        }).format(val);
    };

    const metrics = [
        {
            title: 'Total Revenue',
            value: formatCurrency(summary.revenue),
            icon: <ArrowUpCircle className="w-5 h-5 text-emerald-500" />,
            bgColor: 'bg-emerald-50'
        },
        {
            title: 'EBITDA',
            value: formatCurrency(summary.ebitda),
            icon: <DollarSign className="w-5 h-5 text-blue-500" />,
            bgColor: 'bg-blue-50'
        },
        {
            title: 'Net Profit',
            value: formatCurrency(summary.net_profit),
            icon: <Landmark className="w-5 h-5 text-indigo-500" />,
            bgColor: 'bg-indigo-50'
        },
        {
            title: 'Total Debt',
            value: formatCurrency(summary.total_debt),
            icon: <ArrowDownCircle className="w-5 h-5 text-red-500" />,
            bgColor: 'bg-red-50'
        }
    ];

    return (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {metrics.map((m, idx) => (
                <div key={idx} className="bg-white rounded-xl shadow-sm border border-slate-200 p-5 flex items-center">
                    <div className={`p-3 rounded-xl ${m.bgColor} mr-4`}>
                        {m.icon}
                    </div>
                    <div>
                        <p className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-1">{m.title}</p>
                        <p className="text-lg font-bold text-slate-800">{m.value}</p>
                    </div>
                </div>
            ))}
        </div>
    );
}
