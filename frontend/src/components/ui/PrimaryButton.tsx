import React from 'react';
import { Loader2 } from 'lucide-react';

interface PrimaryButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
    isLoading?: boolean;
    leftIcon?: React.ReactNode;
    rightIcon?: React.ReactNode;
    variant?: 'primary' | 'accent' | 'outline' | 'ghost';
    size?: 'sm' | 'md' | 'lg';
}

export function PrimaryButton({
    children,
    isLoading,
    leftIcon,
    rightIcon,
    variant = 'accent',
    size = 'md',
    className = '',
    disabled,
    ...props
}: PrimaryButtonProps) {

    const baseClasses = "inline-flex items-center justify-center font-semibold rounded-lg transition-all focus:outline-none focus:ring-2 focus:ring-offset-2";

    const variants = {
        primary: "bg-primary-500 hover:bg-primary-600 text-white shadow-sm shadow-primary-500/20 focus:ring-primary-500",
        accent: "bg-accent-500 hover:bg-accent-600 text-white shadow-sm shadow-accent-500/20 focus:ring-accent-500",
        outline: "border-2 border-slate-200 hover:border-slate-300 bg-white text-slate-700 focus:ring-slate-500",
        ghost: "bg-transparent hover:bg-slate-100 text-slate-700 focus:ring-slate-500",
    };

    const sizes = {
        sm: "px-3 py-1.5 text-sm",
        md: "px-4 py-2 text-sm",
        lg: "px-6 py-3 text-base",
    };

    const isDisabled = disabled || isLoading;

    return (
        <button
            className={`
        ${baseClasses}
        ${variants[variant]}
        ${sizes[size]}
        ${isDisabled ? 'opacity-60 cursor-not-allowed hidden-pointer-events' : ''}
        ${className}
      `}
            disabled={isDisabled}
            {...props}
        >
            {isLoading && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
            {!isLoading && leftIcon && <span className="mr-2">{leftIcon}</span>}
            {children}
            {!isLoading && rightIcon && <span className="ml-2">{rightIcon}</span>}
        </button>
    );
}
