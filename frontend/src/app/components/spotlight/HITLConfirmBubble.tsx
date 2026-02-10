// HITL 확인 요청 버블 컴포넌트
import { useState, useMemo, useRef, useEffect, useCallback, Fragment } from 'react';
import { motion } from 'framer-motion';
import { Check, X, AlertCircle, Loader2 } from 'lucide-react';
import type { ChatMessage, HITLRequiredField } from '@/app/types/command';
import { cn } from '@/lib/utils';

interface HITLConfirmBubbleProps {
  message: ChatMessage;
  onConfirm: (messageId: string, params?: Record<string, unknown>) => void;
  onCancel: (messageId: string) => void;
}

export function HITLConfirmBubble({ message, onConfirm, onCancel }: HITLConfirmBubbleProps) {
  const { hitlData, hitlStatus, hitlCancelReason } = message;
  const isPending = hitlStatus === 'pending';
  const isConfirmed = hitlStatus === 'confirmed';
  const isCancelled = hitlStatus === 'cancelled';

  // 버튼 클릭 후 로딩 상태 (중복 클릭 방지)
  const [isSubmitting, setIsSubmitting] = useState(false);

  // 사용자 입력 값 상태 - required_fields의 default_value로 초기화
  const [inputValues, setInputValues] = useState<Record<string, string>>(() => {
    const initialValues: Record<string, string> = {};
    if (hitlData?.required_fields) {
      for (const field of hitlData.required_fields) {
        if (field.default_value !== undefined && field.default_value !== null) {
          initialValues[field.name] = String(field.default_value);
        }
      }
    }
    return initialValues;
  });

  // Tab 키 이동을 위한 input ref 배열
  const inputRefs = useRef<(HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement | null)[]>([]);

  // display_template이 있는지 확인
  const hasTemplate = Boolean(hitlData?.display_template);

  // 필수 필드 (required=true인 필드)
  const requiredFields = useMemo(() => {
    if (!hitlData?.required_fields) return [];
    return hitlData.required_fields.filter((field) => field.required !== false);
  }, [hitlData]);

  // 선택적 필드 (required=false인 필드)
  const optionalFields = useMemo(() => {
    if (!hitlData?.required_fields) return [];
    return hitlData.required_fields.filter((field) => field.required === false);
  }, [hitlData]);

  const handleInputChange = (fieldName: string, value: string) => {
    setInputValues((prev) => ({ ...prev, [fieldName]: value }));
  };

  // 템플릿 파싱: {{param_name}} 패턴 추출
  const templateSegments = useMemo(() => {
    if (!hitlData?.display_template) return null;

    const regex = /\{\{(\w+)\}\}/g;
    const segments: { type: 'text' | 'input'; value: string; paramName?: string }[] = [];
    let lastIndex = 0;
    let match;

    while ((match = regex.exec(hitlData.display_template)) !== null) {
      // 매칭 전 텍스트
      if (match.index > lastIndex) {
        segments.push({
          type: 'text',
          value: hitlData.display_template.slice(lastIndex, match.index),
        });
      }
      // 매칭된 파라미터
      segments.push({
        type: 'input',
        value: match[1], // param_name
        paramName: match[1],
      });
      lastIndex = regex.lastIndex;
    }
    // 마지막 텍스트
    if (lastIndex < hitlData.display_template.length) {
      segments.push({
        type: 'text',
        value: hitlData.display_template.slice(lastIndex),
      });
    }

    return segments;
  }, [hitlData?.display_template]);

  // 템플릿에서 사용되는 파라미터 이름 목록
  const templateParamNames = useMemo(() => {
    if (!templateSegments) return [];
    return templateSegments
      .filter((s) => s.type === 'input')
      .map((s) => s.paramName!);
  }, [templateSegments]);

  // 파라미터에 해당하는 필드 정보 찾기
  const getFieldByName = useCallback(
    (paramName: string): HITLRequiredField | undefined => {
      return hitlData?.required_fields?.find((f) => f.name === paramName);
    },
    [hitlData?.required_fields]
  );

  // 모든 필수 필드가 채워졌는지 확인
  const isValid = useMemo(() => {
    // 템플릿 모드: 템플릿의 모든 파라미터 중 필수 필드가 채워져야 함
    if (hasTemplate && templateParamNames.length > 0) {
      return templateParamNames.every((paramName) => {
        const field = getFieldByName(paramName);
        // 선택적 필드는 비어있어도 OK
        if (field?.required === false) return true;
        // 사용자가 입력한 값이 있으면 OK
        const value = inputValues[paramName];
        return value && value.trim() !== '';
      });
    }
    // 기존 모드: requiredFields 기준
    return requiredFields.every((field) => {
      const value = inputValues[field.name];
      return value && value.trim() !== '';
    });
  }, [hasTemplate, templateParamNames, getFieldByName, requiredFields, inputValues]);

  // Tab 키 핸들링: 다음 input으로 이동
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent, currentIndex: number) => {
      if (e.key === 'Tab' && !e.shiftKey) {
        const nextInput = inputRefs.current[currentIndex + 1];
        if (nextInput) {
          e.preventDefault();
          nextInput.focus();
        }
      } else if (e.key === 'Tab' && e.shiftKey) {
        const prevInput = inputRefs.current[currentIndex - 1];
        if (prevInput) {
          e.preventDefault();
          prevInput.focus();
        }
      }
    },
    []
  );

  // 첫 번째 input에 자동 포커스 (모든 필드가 입력 가능하므로 첫 번째에 포커스)
  useEffect(() => {
    if (isPending && hasTemplate && inputRefs.current.length > 0) {
      setTimeout(() => {
        inputRefs.current[0]?.focus();
      }, 100);
    }
  }, [isPending, hasTemplate]);

  const handleConfirm = () => {
    if (isSubmitting || !isValid) return;
    setIsSubmitting(true);

    // 사용자가 입력한 값들을 params로 전달
    const userParams: Record<string, unknown> = {};
    Object.entries(inputValues).forEach(([key, value]) => {
      if (value && value.trim() !== '') {
        userParams[key] = value.trim();
      }
    });

    onConfirm(message.id, userParams);
  };

  const handleCancel = () => {
    if (isSubmitting) return;
    setIsSubmitting(true);
    onCancel(message.id);
  };

  // 도구 이름을 한글로 매핑
  const toolNameMap: Record<string, string> = {
    create_meeting: '회의 생성',
    update_meeting: '회의 수정',
    delete_meeting: '회의 삭제',
  };

  const toolDisplayName = hitlData?.tool_name
    ? toolNameMap[hitlData.tool_name] || hitlData.tool_name
    : '작업';

  // 필드의 input_type 결정 (확장된 input_type 우선, 없으면 type 기반)
  const getInputType = (field: HITLRequiredField): string => {
    if (field.input_type) return field.input_type;
    // fallback: type 기반
    switch (field.type) {
      case 'datetime':
        return 'datetime';
      case 'number':
        return 'number';
      default:
        return 'text';
    }
  };

  // 필드 타입에 따른 placeholder
  const getPlaceholder = (field: HITLRequiredField): string => {
    if (field.placeholder) return field.placeholder;
    switch (field.type) {
      case 'datetime':
        return 'YYYY-MM-DDTHH:mm';
      case 'uuid':
        return 'UUID 형식';
      default:
        return field.description;
    }
  };

  // 인라인 input 렌더링 (템플릿 모드용) - 모든 필드가 입력 가능
  const renderInlineInput = (paramName: string, inputIndex: number) => {
    const field = getFieldByName(paramName);
    const inputType = field?.input_type || 'text';
    const currentValue = inputValues[paramName] || '';

    // select 타입이고 옵션이 있으면, 현재 값에 해당하는 라벨 표시 (힌트용)
    const getDisplayHint = () => {
      if (inputType === 'select' && field?.options && currentValue) {
        const option = field.options.find(opt => opt.value === currentValue);
        return option?.label;
      }
      return null;
    };

    const baseClass = cn(
      'inline-block px-1.5 py-0.5 mx-1 rounded-md border-b border-white/20',
      'bg-white/0 text-white/90',
      'focus:outline-none focus:border-mit-primary/70 focus:bg-white/10',
      'min-w-[72px] text-center transition-colors'
    );

    if (inputType === 'select' && field?.options) {
      const displayHint = getDisplayHint();
      return (
        <select
          key={paramName}
          ref={(el) => { inputRefs.current[inputIndex] = el; }}
          value={currentValue}
          onChange={(e) => handleInputChange(paramName, e.target.value)}
          onKeyDown={(e) => handleKeyDown(e, inputIndex)}
          disabled={isSubmitting}
          className={cn(baseClass, 'cursor-pointer appearance-none pr-5', currentValue && 'text-mit-primary font-medium')}
          title={displayHint || undefined}
        >
          <option value="" className="bg-gray-800">{field.placeholder || '선택'}</option>
          {field.options.map((opt) => (
            <option key={opt.value} value={opt.value} className="bg-gray-800">
              {opt.label}
            </option>
          ))}
        </select>
      );
    }

    if (inputType === 'datetime') {
      return (
        <input
          key={paramName}
          ref={(el) => { inputRefs.current[inputIndex] = el; }}
          type="datetime-local"
          value={currentValue}
          onChange={(e) => handleInputChange(paramName, e.target.value)}
          onKeyDown={(e) => handleKeyDown(e, inputIndex)}
          disabled={isSubmitting}
        className={cn(baseClass, 'min-w-[170px]', currentValue && 'text-mit-primary font-medium')}
        />
      );
    }

    // 기본: text input
    return (
      <input
        key={paramName}
        ref={(el) => { inputRefs.current[inputIndex] = el; }}
        type="text"
        value={currentValue}
        onChange={(e) => handleInputChange(paramName, e.target.value)}
        onKeyDown={(e) => handleKeyDown(e, inputIndex)}
        placeholder={field?.placeholder || paramName}
        disabled={isSubmitting}
        className={cn(baseClass, currentValue && 'text-mit-primary font-medium')}
        style={{ width: `${Math.max(72, (currentValue.length || 6) * 11)}px` }}
      />
    );
  };

  // 템플릿 렌더링
  const renderTemplate = () => {
    if (!templateSegments) return null;

    let inputIndex = 0;
    return (
      <p className="text-white/90 text-base leading-relaxed">
        {templateSegments.map((segment, idx) => {
          if (segment.type === 'text') {
            return <Fragment key={idx}>{segment.value}</Fragment>;
          }
          const currentIndex = inputIndex++;
          return renderInlineInput(segment.paramName!, currentIndex);
        })}
      </p>
    );
  };

  // 입력 필드 렌더링 (타입별) - 기존 테이블 모드용
  const renderInputField = (field: HITLRequiredField) => {
    const inputType = getInputType(field);
    const commonClass = cn(
      'w-full px-3 py-2 rounded-lg text-sm',
      'bg-white/5 border border-white/10',
      'text-white placeholder:text-white/40',
      'focus:outline-none focus:border-mit-primary/60 focus:bg-white/10',
      'disabled:opacity-50 disabled:cursor-not-allowed'
    );

    switch (inputType) {
      case 'select':
        return (
          <select
            value={inputValues[field.name] || ''}
            onChange={(e) => handleInputChange(field.name, e.target.value)}
            disabled={isSubmitting}
            className={cn(commonClass, 'appearance-none cursor-pointer')}
          >
            <option value="" className="bg-gray-800 text-white/60">
              {getPlaceholder(field)}
            </option>
            {field.options?.map((opt) => (
              <option key={opt.value} value={opt.value} className="bg-gray-800 text-white">
                {opt.label}
              </option>
            ))}
          </select>
        );

      case 'multiselect':
        return (
          <div className="space-y-2">
            {field.options?.map((opt) => (
              <label key={opt.value} className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={(inputValues[field.name] || '').split(',').includes(opt.value)}
                  onChange={(e) => {
                    const current = (inputValues[field.name] || '').split(',').filter(Boolean);
                    const newValue = e.target.checked
                      ? [...current, opt.value].join(',')
                      : current.filter((v) => v !== opt.value).join(',');
                    handleInputChange(field.name, newValue);
                  }}
                  disabled={isSubmitting}
                  className="w-4 h-4 rounded border-white/20 bg-white/10 text-mit-primary focus:ring-mit-primary/50"
                />
                <span className="text-sm text-white/80">{opt.label}</span>
              </label>
            ))}
          </div>
        );

      case 'checkbox':
        return (
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={inputValues[field.name] === 'true'}
              onChange={(e) => handleInputChange(field.name, e.target.checked ? 'true' : 'false')}
              disabled={isSubmitting}
              className="w-4 h-4 rounded border-white/20 bg-white/10 text-mit-primary focus:ring-mit-primary/50"
            />
            <span className="text-sm text-white/80">{field.description}</span>
          </label>
        );

      case 'textarea':
        return (
          <textarea
            value={inputValues[field.name] || ''}
            onChange={(e) => handleInputChange(field.name, e.target.value)}
            placeholder={getPlaceholder(field)}
            disabled={isSubmitting}
            rows={3}
            className={cn(commonClass, 'resize-none')}
          />
        );

      case 'datetime':
        return (
          <input
            type="datetime-local"
            value={inputValues[field.name] || ''}
            onChange={(e) => handleInputChange(field.name, e.target.value)}
            disabled={isSubmitting}
            className={commonClass}
          />
        );

      case 'number':
        return (
          <input
            type="number"
            value={inputValues[field.name] || ''}
            onChange={(e) => handleInputChange(field.name, e.target.value)}
            placeholder={getPlaceholder(field)}
            disabled={isSubmitting}
            className={commonClass}
          />
        );

      default: // text
        return (
          <input
            type="text"
            value={inputValues[field.name] || ''}
            onChange={(e) => handleInputChange(field.name, e.target.value)}
            placeholder={getPlaceholder(field)}
            disabled={isSubmitting}
            className={commonClass}
          />
        );
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      className="flex w-full justify-start"
    >
      <div
        className={cn(
          'max-w-[85%] rounded-2xl px-5 py-4 text-sm leading-relaxed rounded-bl-md',
          'border-2',
          isPending && 'glass-card border-mit-primary/50',
          isConfirmed && 'glass-card border-green-500/50 bg-green-500/10',
          isCancelled && 'glass-card border-red-500/30 bg-red-500/5 opacity-60'
        )}
      >
        {/* 헤더 */}
        <div className="flex items-center gap-2 mb-3">
          <AlertCircle className="w-4 h-4 text-mit-primary" />
          <span className="font-medium text-white/90">다음 내용을 확인해주세요</span>
        </div>

        {/* 작업 내용 */}
        <div className="mb-4">
          {hasTemplate && isPending ? (
            // 템플릿 모드: 자연어 + 인라인 input
            <div className="py-2">
              {renderTemplate()}
              <p className="text-white/40 text-xs mt-3">Tab 키로 다음 항목으로 이동할 수 있어요</p>
            </div>
          ) : (
            // 기존 모드: 테이블 형태
            <>
              <p className="text-white/80 font-medium mb-2">{toolDisplayName}</p>

              {/* 필수 입력 필드 */}
              {isPending && requiredFields.length > 0 && (
                <div className="space-y-3 mb-3">
                  <p className="text-white/60 text-xs">필수 항목</p>
                  {requiredFields.map((field) => (
                    <div key={field.name} className="space-y-1">
                      <label className="text-xs text-white/70">
                        {formatParamKey(field.name)} <span className="text-red-400">*</span>
                      </label>
                      {renderInputField(field)}
                    </div>
                  ))}
                </div>
              )}

              {/* 선택적 입력 필드 */}
              {isPending && optionalFields.length > 0 && (
                <div className="space-y-3 mb-3">
                  <p className="text-white/60 text-xs">선택 항목</p>
                  {optionalFields.map((field) => (
                    <div key={field.name} className="space-y-1">
                      <label className="text-xs text-white/70">{formatParamKey(field.name)}</label>
                      {renderInputField(field)}
                    </div>
                  ))}
                </div>
              )}
            </>
          )}
        </div>

        {/* 상태 표시 또는 버튼 */}
        {isPending ? (
          <div className="flex gap-2">
            <button
              onClick={handleConfirm}
              disabled={isSubmitting || !isValid}
              className={cn(
                'flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg',
                'bg-mit-primary hover:bg-mit-primary/80 text-white font-medium',
                'transition-colors duration-200',
                'disabled:opacity-50 disabled:cursor-not-allowed'
              )}
            >
              {isSubmitting ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Check className="w-4 h-4" />
              )}
              {isSubmitting ? '처리 중...' : '확인하기'}
            </button>
            <button
              onClick={handleCancel}
              disabled={isSubmitting}
              className={cn(
                'flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg',
                'bg-white/10 hover:bg-white/20 text-white/80 font-medium',
                'transition-colors duration-200',
                'disabled:opacity-50 disabled:cursor-not-allowed'
              )}
            >
              <X className="w-4 h-4" />
              취소
            </button>
          </div>
        ) : (
          <div
            className={cn(
              'flex items-center justify-center gap-2 px-4 py-2 rounded-lg text-sm',
              isConfirmed && 'bg-green-500/20 text-green-400',
              isCancelled && 'bg-red-500/10 text-red-400/70'
            )}
          >
            {isConfirmed ? (
              <>
                <Check className="w-4 h-4" />
                확인 완료
              </>
            ) : (
              <>
                <X className="w-4 h-4" />
                {hitlCancelReason === 'auto' ? '자동으로 취소되었어요' : '취소되었어요'}
              </>
            )}
          </div>
        )}
      </div>
    </motion.div>
  );
}

// 파라미터 키를 한글로 변환
function formatParamKey(key: string): string {
  const keyMap: Record<string, string> = {
    team_id: '팀',
    title: '제목',
    scheduled_at: '예정 일시',
    description: '설명',
    meeting_id: '회의',
    status: '상태',
    user_id: '사용자',
    assignee_id: '담당자',
    due_date: '마감일',
    priority: '우선순위',
  };
  return keyMap[key] || key;
}
