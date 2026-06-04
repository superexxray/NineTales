import React from 'react';
import { TrendingUp, TrendingDown, Target, AlertTriangle } from 'lucide-react';

interface SWOTData {
    strengths: string[];
    weaknesses: string[];
    opportunities: string[];
    threats: string[];
}

interface SWOTPanelProps {
    swot: SWOTData;
}

export function SWOTPanel({ swot }: SWOTPanelProps) {
    const panels = [
        {
            title: 'Strengths',
            data: swot.strengths,
            icon: <TrendingUp className="w-5 h-5 text-emerald-600" />,
            bgColor: 'bg-emerald-50',
            borderColor: 'border-emerald-200',
            textColor: 'text-emerald-800',
            iconBg: 'bg-emerald-100'
        },
        {
            title: 'Weaknesses',
            data: swot.weaknesses,
            icon: <TrendingDown className="w-5 h-5 text-red-600" />,
            bgColor: 'bg-red-50',
            borderColor: 'border-red-200',
            textColor: 'text-red-800',
            iconBg: 'bg-red-100'
        },
        {
            title: 'Opportunities',
            data: swot.opportunities,
            icon: <Target className="w-5 h-5 text-indigo-600" />,
            bgColor: 'bg-indigo-50',
            borderColor: 'border-indigo-200',
            textColor: 'text-indigo-800',
            iconBg: 'bg-indigo-100'
        },
        {
            title: 'Threats',
            data: swot.threats,
            icon: <AlertTriangle className="w-5 h-5 text-amber-600" />,
            bgColor: 'bg-amber-50',
            borderColor: 'border-amber-200',
            textColor: 'text-amber-800',
            iconBg: 'bg-amber-100'
        }
    ];

    return (
        <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
            <div className="px-6 py-4 border-b border-slate-100 bg-slate-50">
                <h3 className="text-lg font-bold text-slate-800">SWOT Analysis</h3>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-px bg-slate-100">
                {panels.map((panel, idx) => (
                    <div key={idx} className={`p-6 bg-white relative`}>
                        <div className="flex items-center mb-4">
                            <div className={`p-2 rounded-lg ${panel.iconBg} mr-3`}>
                                {panel.icon}
                            </div>
                            <h4 className={`text-base font-bold ${panel.textColor}`}>
                                {panel.title}
                            </h4>
                        </div>

                        {(!panel.data || panel.data.length === 0) ? (
                            <p className="text-sm text-slate-400 italic pl-2">No {panel.title.toLowerCase()} identified.</p>
                        ) : (
                            <ul className="space-y-3">
                                {panel.data.map((item, itemIdx) => (
                                    <li key={itemIdx} className="flex items-start text-sm text-slate-600">
                                        <span className={`min-w-1.5 h-1.5 rounded-full ${panel.bgColor.replace('50', '400')} mt-2 mr-2.5`}></span>
                                        <span className="leading-snug">{item}</span>
                                    </li>
                                ))}
                            </ul>
                        )}
                    </div>
                ))}
            </div>
        </div>
    );
}
