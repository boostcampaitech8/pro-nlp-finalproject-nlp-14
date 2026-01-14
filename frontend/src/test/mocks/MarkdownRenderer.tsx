/**
 * 테스트용 MarkdownRenderer 모의 구현
 */

interface MarkdownRendererProps {
  content: string;
  className?: string;
}

export function MarkdownRenderer({ content, className }: MarkdownRendererProps) {
  return <div className={className}>{content}</div>;
}
