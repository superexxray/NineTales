import React from 'react';

type StatusType = 'awaiting_review' | 'approved' | 'corrected_by_user' | 'extraction_complete';

interface StatusBadgeProps {
    status: StatusType;
}

export function StatusBadge({ status }: StatusBadgeProps) {
    const config: Record<StatusType, { label: string; classes: string }> = {
        awaiting_review: {
            label: 'Awaiting',
            classes: 'bg-amber-100 text-amber-800 border-amber-200',
        },
        approved: {
            label: 'Approved',
            classes: 'bg-emerald-100 text-emerald-800 border-emerald-200',
        },
        corrected_by_user: {
            label: 'Corrected',
            classes: 'bg-primary-100 text-primary-800 border-primary-200',
        },
        extraction_complete: {
            label: 'Done',
            classes: 'bg-slate-100 text-slate-800 border-slate-200',
        }
    };

    const { label, classes } = config[status] || config['awaiting_review'];

    return (
        <span className={`px-2.5 py-0.5 rounded-full text-xs font-semibold border ${classes}`}>
            {label}
        </span>
    );
}
