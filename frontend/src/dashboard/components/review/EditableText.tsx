/**
 * 인라인 편집 가능한 텍스트 컴포넌트
 *
 * 클릭하면 편집 모드로 전환
 * Enter로 저장, Escape로 취소
 */

import { useState, useRef, useEffect, useCallback } from 'react';
import { Pencil, Check, X, Loader2 } from 'lucide-react';

interface EditableTextProps {
  value: string;
  onSave: (value: string) => Promise<boolean>;
  className?: string;
  inputClassName?: string;
  placeholder?: string;
  multiline?: boolean;
  disabled?: boolean;
  showEditIcon?: boolean;
}

export function EditableText({
  value,
  onSave,
  className = '',
  inputClassName = '',
  placeholder = '입력하세요...',
  multiline = false,
  disabled = false,
  showEditIcon = true,
}: EditableTextProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [editValue, setEditValue] = useState(value);
  const [isSaving, setIsSaving] = useState(false);
  const inputRef = useRef<HTMLInputElement | HTMLTextAreaElement>(null);

  useEffect(() => {
    setEditValue(value);
  }, [value]);

  useEffect(() => {
    if (isEditing && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [isEditing]);

  const handleSave = useCallback(async () => {
    if (editValue.trim() === value.trim()) {
      setIsEditing(false);
      return;
    }

    setIsSaving(true);
    try {
      const success = await onSave(editValue.trim());
      if (success) {
        setIsEditing(false);
      } else {
        setEditValue(value);
      }
    } finally {
      setIsSaving(false);
    }
  }, [editValue, value, onSave]);

  const handleCancel = useCallback(() => {
    setEditValue(value);
    setIsEditing(false);
  }, [value]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Escape') {
        handleCancel();
      } else if (e.key === 'Enter' && !multiline) {
        e.preventDefault();
        handleSave();
      } else if (e.key === 'Enter' && e.metaKey && multiline) {
        e.preventDefault();
        handleSave();
      }
    },
    [handleCancel, handleSave, multiline]
  );

  if (isEditing) {
    const InputComponent = multiline ? 'textarea' : 'input';

    return (
      <div className="flex items-start gap-2">
        <InputComponent
          ref={inputRef as any}
          value={editValue}
          onChange={(e) => setEditValue(e.target.value)}
          onKeyDown={handleKeyDown}
          onBlur={() => {
            // 약간의 지연을 두어 버튼 클릭이 가능하게 함
            setTimeout(() => {
              if (!isSaving) handleCancel();
            }, 150);
          }}
          placeholder={placeholder}
          disabled={isSaving}
          className={`flex-1 px-3 py-2 border-2 border-blue-400 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-blue-200 ${
            multiline ? 'resize-none min-h-[80px]' : ''
          } ${inputClassName}`}
          rows={multiline ? 3 : undefined}
        />
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              handleSave();
            }}
            disabled={isSaving}
            className="p-2 text-green-600 hover:bg-green-50 rounded-lg transition-colors"
          >
            {isSaving ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Check className="w-4 h-4" />
            )}
          </button>
          <button
            type="button"
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              handleCancel();
            }}
            disabled={isSaving}
            className="p-2 text-gray-400 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>
    );
  }

  return (
    <div
      className={`group flex items-center gap-2 cursor-pointer ${disabled ? 'cursor-not-allowed opacity-60' : ''} ${className}`}
      onClick={() => !disabled && setIsEditing(true)}
    >
      <span className={value ? '' : 'text-gray-400 italic'}>{value || placeholder}</span>
      {showEditIcon && !disabled && (
        <Pencil className="w-4 h-4 text-gray-300 opacity-0 group-hover:opacity-100 transition-opacity" />
      )}
    </div>
  );
}
