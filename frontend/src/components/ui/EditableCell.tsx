import React, { useState, useEffect, useRef } from 'react';
import { Edit2, Check, X } from 'lucide-react';

interface EditableCellProps {
    value: string | number;
    onSave: (newValue: string) => void;
    type?: 'text' | 'number';
}

export function EditableCell({ value, onSave, type = 'text' }: EditableCellProps) {
    const [isEditing, setIsEditing] = useState(false);
    const [currentValue, setCurrentValue] = useState(String(value ?? ''));
    const inputRef = useRef<HTMLInputElement>(null);

    useEffect(() => {
        setCurrentValue(String(value ?? ''));
    }, [value]);

    useEffect(() => {
        if (isEditing && inputRef.current) {
            inputRef.current.focus();
        }
    }, [isEditing]);

    const handleSave = () => {
        onSave(currentValue);
        setIsEditing(false);
    };

    const handleCancel = () => {
        setCurrentValue(String(value ?? ''));
        setIsEditing(false);
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter') handleSave();
        if (e.key === 'Escape') handleCancel();
    };

    if (isEditing) {
        return (
            <div className="flex items-center space-x-2">
                <input
                    ref={inputRef}
                    type={type}
                    value={currentValue}
                    onChange={(e) => setCurrentValue(e.target.value)}
                    onKeyDown={handleKeyDown}
                    className="w-full px-2 py-1 text-sm border-2 border-primary-500 rounded focus:outline-none bg-white min-w-[120px]"
                />
                <button
                    onClick={handleSave}
                    className="p-1 text-green-600 hover:bg-green-50 rounded"
                    title="Save"
                >
                    <Check className="w-4 h-4" />
                </button>
                <button
                    onClick={handleCancel}
                    className="p-1 text-slate-400 hover:text-red-500 hover:bg-red-50 rounded"
                    title="Cancel"
                >
                    <X className="w-4 h-4" />
                </button>
            </div>
        );
    }

    return (
        <div
            className="group flex items-center justify-between p-1 -m-1 rounded hover:bg-slate-50 cursor-pointer transition-colors"
            onClick={() => setIsEditing(true)}
            title="Click to edit"
        >
            <span className="text-sm font-medium text-slate-900 truncate">
                {value !== null && value !== undefined && value !== '' ? String(value) : <span className="text-slate-400 italic">Empty</span>}
            </span>
            <Edit2 className="w-3.5 h-3.5 text-slate-300 opacity-0 group-hover:opacity-100 transition-opacity ml-2 shrink-0" />
        </div>
    );
}
