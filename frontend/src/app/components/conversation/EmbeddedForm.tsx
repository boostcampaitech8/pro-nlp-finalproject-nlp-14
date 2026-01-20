// 채팅 내 임베디드 폼 컴포넌트
import { motion } from 'framer-motion';
import { X, Send } from 'lucide-react';
import { formVariants } from '@/app/constants/animations';
import { Button } from '@/app/components/ui';
import type { ActiveCommand, CommandField } from '@/app/types/command';
import { cn } from '@/lib/utils';

interface FieldInputProps {
  field: CommandField;
  onChange: (value: string) => void;
}

function FieldInput({ field, onChange }: FieldInputProps) {
  const baseClasses =
    'w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-white placeholder:text-white/30 outline-none focus:border-mit-primary/50 focus:ring-1 focus:ring-mit-primary/20 transition-all';

  switch (field.type) {
    case 'select':
      return (
        <select
          value={field.value || ''}
          onChange={(e) => onChange(e.target.value)}
          className={cn(baseClasses, 'cursor-pointer')}
        >
          <option value="" className="bg-slate-800">
            선택하세요
          </option>
          {field.options?.map((option) => (
            <option key={option} value={option} className="bg-slate-800">
              {option}
            </option>
          ))}
        </select>
      );

    case 'textarea':
      return (
        <textarea
          value={field.value || ''}
          onChange={(e) => onChange(e.target.value)}
          placeholder={field.placeholder}
          rows={2}
          className={cn(baseClasses, 'resize-none')}
        />
      );

    case 'date':
      return (
        <input
          type="date"
          value={field.value || ''}
          onChange={(e) => onChange(e.target.value)}
          className={baseClasses}
        />
      );

    case 'number':
      return (
        <input
          type="number"
          value={field.value || ''}
          onChange={(e) => onChange(e.target.value)}
          placeholder={field.placeholder}
          className={baseClasses}
        />
      );

    default:
      return (
        <input
          type="text"
          value={field.value || ''}
          onChange={(e) => onChange(e.target.value)}
          placeholder={field.placeholder}
          className={baseClasses}
        />
      );
  }
}

interface EmbeddedFormProps {
  command: ActiveCommand;
  onSubmit: () => void;
  onCancel: () => void;
  onFieldChange: (fieldId: string, value: string) => void;
  isProcessing?: boolean;
}

export function EmbeddedForm({
  command,
  onSubmit,
  onCancel,
  onFieldChange,
  isProcessing = false,
}: EmbeddedFormProps) {
  const isValid = command.fields
    .filter((f) => f.required)
    .every((f) => f.value && f.value.trim());

  return (
    <motion.div
      variants={formVariants}
      initial="initial"
      animate="animate"
      exit="exit"
      className="overflow-hidden"
    >
      <div className="glass-card p-4 mt-2">
        {/* 헤더 */}
        <div className="flex items-start justify-between mb-4">
          <div className="flex items-center gap-2">
            {command.icon && (
              <span className="text-lg">{command.icon}</span>
            )}
            <div>
              <h4 className="text-sm font-semibold text-white">{command.title}</h4>
              {command.description && (
                <p className="text-xs text-white/50 mt-0.5">{command.description}</p>
              )}
            </div>
          </div>
          <button
            onClick={onCancel}
            className="p-1.5 rounded-lg hover:bg-white/10 transition-colors"
            title="취소"
          >
            <X className="w-4 h-4 text-white/60" />
          </button>
        </div>

        {/* 필드 */}
        <div className="space-y-3">
          {command.fields.map((field) => (
            <div key={field.id}>
              <label className="block text-xs font-medium text-white/60 mb-1">
                {field.label}
                {field.required && <span className="text-mit-warning ml-0.5">*</span>}
              </label>
              <FieldInput
                field={field}
                onChange={(value) => onFieldChange(field.id, value)}
              />
            </div>
          ))}
        </div>

        {/* 액션 버튼 */}
        <div className="mt-4 flex justify-end gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={onCancel}
            disabled={isProcessing}
          >
            취소
          </Button>
          <Button
            variant="glass-primary"
            size="sm"
            onClick={onSubmit}
            disabled={!isValid || isProcessing}
            className="gap-1.5"
          >
            {isProcessing ? '처리 중...' : (
              <>
                <Send className="w-3.5 h-3.5" />
                실행
              </>
            )}
          </Button>
        </div>
      </div>
    </motion.div>
  );
}
