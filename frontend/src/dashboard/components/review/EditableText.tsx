/**
 * 인라인 편집 가능한 텍스트 컴포넌트
 *
 * 클릭하면 편집 모드로 전환
 * Enter로 저장, Escape로 취소
 */

import { useState, useRef, useEffect, useCallback } from 'react';
import { Pencil, Check, Loader2 } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

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
      <div className="space-y-2">
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
          className={`w-full px-4 py-3 border-2 border-blue-500/50 rounded-xl bg-white/10 focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-400 text-white placeholder-white/50 ${
            multiline ? 'resize-y min-h-[200px]' : ''
          } ${inputClassName}`}
          rows={multiline ? 8 : undefined}
        />
        <div className="flex items-center justify-end gap-2">
          <button
            type="button"
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              handleCancel();
            }}
            disabled={isSaving}
            className="px-3 py-1.5 text-sm text-white/70 hover:bg-white/10 rounded-lg transition-colors"
          >
            취소
          </button>
          <button
            type="button"
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              handleSave();
            }}
            disabled={isSaving}
            className="px-3 py-1.5 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg transition-colors flex items-center gap-1"
          >
            {isSaving ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Check className="w-4 h-4" />
            )}
            저장
          </button>
        </div>
      </div>
    );
  }

  return (
    <div
      className={`group flex items-start gap-2 ${disabled ? 'opacity-60' : ''} ${className}`}
      onDoubleClick={() => !disabled && setIsEditing(true)}
    >
      <div className="flex-1">
        {value ? (
          <div className="prose prose-sm prose-invert max-w-none prose-p:my-1 prose-ul:my-1 prose-ol:my-1 prose-li:my-0.5">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{value}</ReactMarkdown>
          </div>
        ) : (
          <span className="text-white/50 italic">{placeholder}</span>
        )}
      </div>
      {showEditIcon && !disabled && (
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            setIsEditing(true);
          }}
          className="p-1.5 text-white/40 hover:text-blue-400 hover:bg-blue-500/20 rounded-lg opacity-0 group-hover:opacity-100 transition-all shrink-0"
          title="편집 (더블클릭으로도 가능)"
        >
          <Pencil className="w-4 h-4" />
        </button>
      )}
    </div>
  );
}
