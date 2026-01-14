// Interactive Form 컴포넌트 (빈칸 채우기)
import { motion } from 'framer-motion';
import { X } from 'lucide-react';
import { useCommand } from '@/app/hooks/useCommand';
import { useCommandStore } from '@/app/stores/commandStore';
import { Button } from '@/app/components/ui';
import type { ActiveCommand, CommandField } from '@/app/types/command';
import { cn } from '@/lib/utils';

interface FieldInputProps {
  field: CommandField;
  onChange: (value: string) => void;
}

function FieldInput({ field, onChange }: FieldInputProps) {
  const baseClasses =
    'w-full bg-white/5 border border-white/10 rounded-lg px-4 py-2.5 text-white placeholder:text-white/30 outline-none focus:border-mit-primary/50 focus:ring-2 focus:ring-mit-primary/20 transition-all';

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
          rows={3}
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

interface InteractiveFormProps {
  command: ActiveCommand;
}

export function InteractiveForm({ command }: InteractiveFormProps) {
  const { submitForm, cancelCommand, updateField } = useCommand();
  const { isProcessing } = useCommandStore();

  const handleFieldChange = (fieldId: string, value: string) => {
    updateField(fieldId, value);
  };

  const isValid = command.fields
    .filter((f) => f.required)
    .every((f) => f.value && f.value.trim());

  return (
    <motion.div
      initial={{ opacity: 0, y: -20, height: 0 }}
      animate={{ opacity: 1, y: 0, height: 'auto' }}
      exit={{ opacity: 0, y: -20, height: 0 }}
      transition={{ duration: 0.2, ease: 'easeOut' }}
      className="mt-4 overflow-hidden"
    >
      <div className="glass-card p-6">
        {/* 헤더 */}
        <div className="flex items-start justify-between mb-6">
          <div className="flex items-center gap-3">
            {command.icon && (
              <div className="icon-container-sm">
                <span className="text-xl">{command.icon}</span>
              </div>
            )}
            <div>
              <h3 className="text-lg font-semibold text-white">{command.title}</h3>
              {command.description && (
                <p className="text-sm text-white/50 mt-0.5">{command.description}</p>
              )}
            </div>
          </div>
          <button
            onClick={cancelCommand}
            className="action-btn"
            title="취소"
          >
            <X className="w-4 h-4 text-white/60" />
          </button>
        </div>

        {/* 필드 */}
        <div className="space-y-4">
          {command.fields.map((field) => (
            <div key={field.id}>
              <label className="block text-sm font-medium text-white/70 mb-1.5">
                {field.label}
                {field.required && <span className="text-mit-warning ml-1">*</span>}
              </label>
              <FieldInput
                field={field}
                onChange={(value) => handleFieldChange(field.id, value)}
              />
            </div>
          ))}
        </div>

        {/* 액션 버튼 */}
        <div className="mt-6 flex justify-end gap-3">
          <Button
            variant="ghost"
            onClick={cancelCommand}
            disabled={isProcessing}
          >
            취소
          </Button>
          <Button
            variant="glass-primary"
            onClick={submitForm}
            disabled={!isValid || isProcessing}
          >
            {isProcessing ? '처리 중...' : '실행'}
          </Button>
        </div>
      </div>
    </motion.div>
  );
}
