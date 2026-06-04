import React from 'react';

interface SelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
    label: string;
    options: { label: string; value: string }[];
    error?: string;
    placeholder?: string;
}

export const Select = React.forwardRef<HTMLSelectElement, SelectProps>(
    ({ label, options, error, placeholder, className = '', ...props }, ref) => {
        return (
            <div className="flex flex-col gap-1.5 w-full">
                <label
                    htmlFor={props.id || props.name}
                    className="text-sm font-semibold text-slate-700"
                >
                    {label}
                </label>
                <div className="relative">
                    <select
                        ref={ref}
                        className={`
              w-full px-4 py-2.5 rounded-lg border text-sm appearance-none transition-all duration-200
              focus:outline-none focus:ring-2 focus:ring-opacity-50
              ${error
                                ? 'border-red-300 focus:border-red-500 focus:ring-red-500 bg-red-50 text-red-900'
                                : 'border-slate-300 focus:border-primary-500 focus:ring-primary-500 hover:border-slate-400 bg-white text-slate-900'
                            }
              ${props.disabled ? 'opacity-60 cursor-not-allowed bg-slate-50' : ''}
              ${className}
            `}
                        {...props}
                    >
                        {placeholder && (
                            <option value="" disabled hidden>
                                {placeholder}
                            </option>
                        )}
                        {options.map((opt) => (
                            <option key={opt.value} value={opt.value}>
                                {opt.label}
                            </option>
                        ))}
                    </select>
                    {/* Custom chevron indicator */}
                    <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center px-4 text-slate-500">
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7" />
                        </svg>
                    </div>
                </div>
                {error && (
                    <p className="text-xs text-red-500">
                        {error}
                    </p>
                )}
            </div>
        );
    }
);

Select.displayName = 'Select';
