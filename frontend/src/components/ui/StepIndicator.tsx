import React from 'react';
import { Check } from 'lucide-react';

interface StepIndicatorProps {
    steps: string[];
    currentStep: number;
}

export function StepIndicator({ steps, currentStep }: StepIndicatorProps) {
    return (
        <div className="w-full py-6">
            <div className="flex items-center justify-between relative">
                {/* Connecting line */}
                <div className="absolute left-0 top-1/2 -translate-y-1/2 w-full h-1 bg-slate-200 rounded-full z-0" />
                <div
                    className="absolute left-0 top-1/2 -translate-y-1/2 h-1 bg-primary-500 rounded-full z-0 transition-all duration-500 ease-in-out"
                    style={{ width: `${(Math.max(0, currentStep - 1) / (steps.length - 1)) * 100}%` }}
                />

                {steps.map((step, index) => {
                    const stepNumber = index + 1;
                    const isCompleted = stepNumber < currentStep;
                    const isCurrent = stepNumber === currentStep;

                    return (
                        <div key={step} className="relative z-10 flex flex-col items-center">
                            <div
                                className={`
                  w-10 h-10 rounded-full flex items-center justify-center font-semibold text-sm transition-all duration-300 shadow-sm
                  ${isCompleted ? 'bg-primary-500 text-white shadow-primary-500/30' :
                                        isCurrent ? 'bg-white border-2 border-primary-500 text-primary-600 shadow-primary-500/20' :
                                            'bg-white border-2 border-slate-200 text-slate-400'}
                `}
                            >
                                {isCompleted ? <Check className="w-5 h-5" /> : stepNumber}
                            </div>
                            <span
                                className={`
                  absolute top-12 whitespace-nowrap text-xs font-medium transition-colors duration-300 hidden sm:block
                  ${isCurrent ? 'text-primary-700' : isCompleted ? 'text-slate-700' : 'text-slate-400'}
                `}
                            >
                                {step}
                            </span>
                        </div>
                    );
                })}
            </div>
        </div>
    );
}
