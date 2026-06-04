'use client';

import React, { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import axios from 'axios';
import { useRouter } from 'next/navigation';
import { Check, ChevronRight, ChevronLeft, Loader2, AlertCircle } from 'lucide-react';

import { onboardingSchema, OnboardingFormData } from '@/lib/schema';
import { Input } from './ui/Input';
import { Select } from './ui/Select';
import { StepIndicator } from './ui/StepIndicator';

const STEPS = [
    'Entity Information',
    'Financial Overview',
    'Loan Request',
    'Review & Submit',
];

export function OnboardingForm() {
    const router = useRouter();
    const [currentStep, setCurrentStep] = useState(1);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [submitError, setSubmitError] = useState<string | null>(null);
    const [isSuccess, setIsSuccess] = useState(false);

    const {
        register,
        handleSubmit,
        trigger,
        getValues,
        formState: { errors },
    } = useForm<OnboardingFormData>({
        resolver: zodResolver(onboardingSchema),
        mode: 'onTouched',
    });

    const handleNext = async () => {
        let fieldsToValidate: (keyof OnboardingFormData)[] = [];

        if (currentStep === 1) {
            fieldsToValidate = ['companyName', 'cin', 'pan', 'sector', 'subsector'];
        } else if (currentStep === 2) {
            fieldsToValidate = ['annualTurnover', 'netProfit', 'totalDebt', 'ebitda'];
        } else if (currentStep === 3) {
            fieldsToValidate = ['loanType', 'loanAmount', 'loanTenure', 'expectedInterestRate'];
        }

        const isStepValid = await trigger(fieldsToValidate);
        if (isStepValid) {
            setCurrentStep((prev) => Math.min(prev + 1, 4));
            window.scrollTo({ top: 0, behavior: 'smooth' });
        }
    };

    const handleBack = () => {
        setCurrentStep((prev) => Math.max(prev - 1, 1));
        window.scrollTo({ top: 0, behavior: 'smooth' });
    };

    const onSubmit = async (data: OnboardingFormData) => {
        setIsSubmitting(true);
        setSubmitError(null);
        try {
            const response = await axios.post('http://127.0.0.1:8000/onboarding', data);
            // Persist the entity_id returned by the backend so that the
            // extraction approval step can navigate to the correct analysis URL.
            const entityId: string = response.data?.entity_id ?? '';
            if (entityId) {
                localStorage.setItem('ninetales_entity_id', entityId);
            }
            setIsSuccess(true);
            window.scrollTo({ top: 0, behavior: 'smooth' });
        } catch (error: any) {
            console.error('Submission error:', error);
            setSubmitError(
                error.response?.data?.detail ||
                'An error occurred while submitting the application. Please try again.'
            );
        } finally {
            setIsSubmitting(false);
        }
    };

    if (isSuccess) {
        return (
            <div className="bg-white rounded-2xl shadow-xl border border-slate-100 p-10 text-center max-w-2xl mx-auto mt-12">
                <div className="w-20 h-20 bg-teal-100 rounded-full flex items-center justify-center mx-auto mb-6">
                    <Check className="w-10 h-10 text-teal-600" />
                </div>
                <h2 className="text-3xl font-bold text-slate-900 mb-4">Application Submitted!</h2>
                <p className="text-slate-600 mb-8 max-w-md mx-auto">
                    The entity onboarding details have been securely saved. You can now proceed to the next stage of the credit evaluation process.
                </p>
                <button
                    onClick={() => router.push('/upload')}
                    className="bg-primary-500 text-white font-semibold py-3 px-8 rounded-xl hover:bg-primary-600 transition shadow-lg shadow-primary-500/20"
                >
                    Proceed to Document Upload
                </button>
            </div>
        );
    }

    return (
        <div className="max-w-3xl mx-auto mt-8 mb-20 relative">

            {/* Form Container */}
            <div className="bg-white rounded-2xl shadow-xl shadow-slate-200/50 border border-slate-100 p-8 sm:p-10 relative overflow-hidden">
                {/* Soft background accents */}
                <div className="absolute top-0 right-0 w-64 h-64 bg-teal-50 rounded-full blur-3xl -mr-32 -mt-32 pointer-events-none opacity-60"></div>
                <div className="absolute bottom-0 left-0 w-64 h-64 bg-teal-50 rounded-full blur-3xl -ml-32 -mb-32 pointer-events-none opacity-60"></div>

                <div className="relative z-10">
                    <h2 className="text-2xl font-bold text-slate-900 mb-2">Entity Onboarding</h2>
                    <p className="text-slate-500 text-sm mb-6">Create a new credit application profile.</p>

                    <StepIndicator steps={STEPS} currentStep={currentStep} />

                    <form onSubmit={handleSubmit(onSubmit)} className="mt-8">

                        {/* --- STEP 1: ENTITY INFO --- */}
                        {currentStep === 1 && (
                            <div className="space-y-6 animate-in slide-in-from-right-4 fade-in duration-300">
                                <Input
                                    label="Company Name"
                                    placeholder="e.g. Acme Corporation Limited"
                                    {...register('companyName')}
                                    error={errors.companyName?.message}
                                />
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                    <Input
                                        label="Corporate Identification Number (CIN)"
                                        placeholder="21-character alphanumeric"
                                        {...register('cin')}
                                        error={errors.cin?.message}
                                    />
                                    <Input
                                        label="Permanent Account Number (PAN)"
                                        placeholder="e.g. ABCDE1234F"
                                        {...register('pan')}
                                        error={errors.pan?.message}
                                    />
                                </div>
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                    <Input
                                        label="Sector"
                                        placeholder="e.g. Manufacturing, Technology"
                                        {...register('sector')}
                                        error={errors.sector?.message}
                                    />
                                    <Input
                                        label="Subsector"
                                        placeholder="e.g. Semiconductors, Software"
                                        {...register('subsector')}
                                        error={errors.subsector?.message}
                                    />
                                </div>
                            </div>
                        )}

                        {/* --- STEP 2: FINANCIAL OVERVIEW --- */}
                        {currentStep === 2 && (
                            <div className="space-y-6 animate-in slide-in-from-right-4 fade-in duration-300">
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                    <Input
                                        type="number"
                                        step="0.01"
                                        label="Annual Turnover (₹)"
                                        placeholder="0.00"
                                        {...register('annualTurnover', { valueAsNumber: true })}
                                        error={errors.annualTurnover?.message}
                                    />
                                    <Input
                                        type="number"
                                        step="0.01"
                                        label="Net Profit (₹)"
                                        placeholder="0.00"
                                        {...register('netProfit', { valueAsNumber: true })}
                                        error={errors.netProfit?.message}
                                    />
                                </div>
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                    <Input
                                        type="number"
                                        step="0.01"
                                        label="Total Debt (₹)"
                                        placeholder="0.00"
                                        {...register('totalDebt', { valueAsNumber: true })}
                                        error={errors.totalDebt?.message}
                                    />
                                    <Input
                                        type="number"
                                        step="0.01"
                                        label="EBITDA (₹)"
                                        placeholder="0.00"
                                        {...register('ebitda', { valueAsNumber: true })}
                                        error={errors.ebitda?.message}
                                    />
                                </div>
                            </div>
                        )}

                        {/* --- STEP 3: LOAN REQUEST --- */}
                        {currentStep === 3 && (
                            <div className="space-y-6 animate-in slide-in-from-right-4 fade-in duration-300">
                                <Select
                                    label="Loan Type"
                                    placeholder="Select a loan type"
                                    options={[
                                        { label: 'Term Loan', value: 'Term Loan' },
                                        { label: 'Working Capital', value: 'Working Capital' },
                                        { label: 'Revolving Credit', value: 'Revolving Credit' },
                                    ]}
                                    {...register('loanType')}
                                    error={errors.loanType?.message}
                                />
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                    <Input
                                        type="number"
                                        step="0.01"
                                        label="Loan Amount Requested (₹)"
                                        placeholder="0.00"
                                        {...register('loanAmount', { valueAsNumber: true })}
                                        error={errors.loanAmount?.message}
                                    />
                                    <Input
                                        type="number"
                                        label="Loan Tenure (Months)"
                                        placeholder="e.g. 60"
                                        {...register('loanTenure', { valueAsNumber: true })}
                                        error={errors.loanTenure?.message}
                                    />
                                </div>
                                <div className="w-full md:w-1/2 md:pr-3">
                                    <Input
                                        type="number"
                                        step="0.01"
                                        label="Expected Interest Rate (%)"
                                        placeholder="e.g. 8.5"
                                        {...register('expectedInterestRate', { valueAsNumber: true })}
                                        error={errors.expectedInterestRate?.message}
                                    />
                                </div>
                            </div>
                        )}

                        {/* --- STEP 4: REVIEW & SUBMIT --- */}
                        {currentStep === 4 && (
                            <div className="space-y-8 animate-in slide-in-from-right-4 fade-in duration-300">

                                {submitError && (
                                    <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-start gap-3">
                                        <AlertCircle className="w-5 h-5 text-red-500 mt-0.5 shrink-0" />
                                        <div>
                                            <h4 className="text-sm font-semibold text-red-800">Submission Failed</h4>
                                            <p className="text-sm text-red-600 mt-1">{submitError}</p>
                                        </div>
                                    </div>
                                )}

                                <div className="bg-slate-50 border border-slate-100 rounded-xl p-6">
                                    <h3 className="text-lg font-semibold text-slate-800 mb-4 pb-2 border-b border-slate-200">
                                        Entity Information
                                    </h3>
                                    <div className="grid grid-cols-2 gap-y-4 gap-x-6 text-sm">
                                        <div><span className="text-slate-500 block">Company Name</span><span className="font-medium text-slate-900">{getValues('companyName')}</span></div>
                                        <div><span className="text-slate-500 block">CIN</span><span className="font-medium text-slate-900">{getValues('cin')}</span></div>
                                        <div><span className="text-slate-500 block">PAN</span><span className="font-medium text-slate-900">{getValues('pan')}</span></div>
                                        <div><span className="text-slate-500 block">Sector / Subsector</span><span className="font-medium text-slate-900">{getValues('sector')} / {getValues('subsector')}</span></div>
                                    </div>
                                </div>

                                <div className="bg-slate-50 border border-slate-100 rounded-xl p-6">
                                    <h3 className="text-lg font-semibold text-slate-800 mb-4 pb-2 border-b border-slate-200">
                                        Financial Overview
                                    </h3>
                                    <div className="grid grid-cols-2 gap-y-4 gap-x-6 text-sm">
                                        <div><span className="text-slate-500 block">Annual Turnover</span><span className="font-medium text-slate-900">₹{getValues('annualTurnover')?.toLocaleString()}</span></div>
                                        <div><span className="text-slate-500 block">Net Profit</span><span className="font-medium text-slate-900">₹{getValues('netProfit')?.toLocaleString()}</span></div>
                                        <div><span className="text-slate-500 block">Total Debt</span><span className="font-medium text-slate-900">₹{getValues('totalDebt')?.toLocaleString()}</span></div>
                                        <div><span className="font-medium text-slate-900">₹{getValues('ebitda')?.toLocaleString()}</span></div>
                                    </div>
                                </div>

                                <div className="bg-primary-50 border border-primary-100 rounded-xl p-6">
                                    <h3 className="text-lg font-semibold text-primary-900 mb-4 pb-2 border-b border-primary-200/50">
                                        Loan Request
                                    </h3>
                                    <div className="grid grid-cols-2 gap-y-4 gap-x-6 text-sm">
                                        <div><span className="text-slate-600 block">Loan Type</span><span className="font-medium text-primary-900">{getValues('loanType')}</span></div>
                                        <div><span className="text-slate-600 block">Loan Amount</span><span className="font-medium text-primary-900 leading-tight">₹{getValues('loanAmount')?.toLocaleString()}</span></div>
                                        <div><span className="text-slate-600 block">Loan Tenure</span><span className="font-medium text-primary-900">{getValues('loanTenure')} Months</span></div>
                                        <div><span className="text-slate-600 block">Expected Rate</span><span className="font-medium text-primary-900">{getValues('expectedInterestRate')}%</span></div>
                                    </div>
                                </div>

                            </div>
                        )}

                        {/* Navigation Buttons */}
                        <div className="mt-10 pt-6 border-t border-slate-100 flex items-center justify-between">
                            <button
                                type="button"
                                onClick={handleBack}
                                className={`flex items-center text-sm font-semibold text-slate-600 hover:text-slate-900 transition-colors px-4 py-2 ${currentStep === 1 ? 'invisible' : ''}`}
                                disabled={isSubmitting}
                            >
                                <ChevronLeft className="w-4 h-4 mr-1" /> Back
                            </button>

                            {currentStep < 4 ? (
                                <button
                                    type="button"
                                    onClick={handleNext}
                                    className="bg-slate-900 text-white font-semibold py-2.5 px-6 rounded-lg hover:bg-slate-800 transition-colors flex items-center shadow-lg shadow-slate-200"
                                >
                                    Next Step <ChevronRight className="w-4 h-4 ml-1" />
                                </button>
                            ) : (
                                <button
                                    type="submit"
                                    disabled={isSubmitting}
                                    className="bg-accent-500 text-white font-semibold flex items-center py-2.5 px-8 rounded-lg hover:bg-accent-600 transition shadow-lg shadow-accent-500/20 disabled:opacity-70 disabled:cursor-not-allowed"
                                >
                                    {isSubmitting ? (
                                        <>
                                            <Loader2 className="w-4 h-4 mr-2 animate-spin" /> Submitting...
                                        </>
                                    ) : (
                                        <>
                                            Submit Application <Check className="w-4 h-4 ml-2" />
                                        </>
                                    )}
                                </button>
                            )}
                        </div>

                    </form>
                </div>
            </div>
        </div>
    );
}
