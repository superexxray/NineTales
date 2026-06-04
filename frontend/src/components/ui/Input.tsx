import React from 'react';

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
    label: string;
    error?: string;
    helperText?: string;
}

export const Input = React.forwardRef<HTMLInputElement, InputProps>(
    ({ label, error, helperText, className = '', ...props }, ref) => {
        return (
            <div className="flex flex-col gap-1.5 w-full">
                <label
                    htmlFor={props.id || props.name}
                    className="text-sm font-semibold text-slate-700"
                >
                    {label}
                </label>
                <div className="relative">
                    <input
                        ref={ref}
                        className={`
              w-full px-4 py-2.5 rounded-lg border text-sm transition-all duration-200
              focus:outline-none focus:ring-2 focus:ring-opacity-50
              ${error
                                ? 'border-red-300 focus:border-red-500 focus:ring-red-500 bg-red-50'
                                : 'border-slate-300 focus:border-primary-500 focus:ring-primary-500 hover:border-slate-400 bg-white'
                            }
              ${props.disabled ? 'opacity-60 cursor-not-allowed bg-slate-50' : ''}
              ${className}
            `}
                        {...props}
                    />
                </div>
                {(error || helperText) && (
                    <p className={`text-xs ${error ? 'text-red-500' : 'text-slate-500'}`}>
                        {error || helperText}
                    </p>
                )}
            </div>
        );
    }
);

Input.displayName = 'Input';
