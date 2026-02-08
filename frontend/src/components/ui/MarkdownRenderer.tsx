/**
 * Markdown 렌더러 컴포넌트
 * react-markdown과 remark-gfm을 사용하여 Markdown을 렌더링
 */

import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface MarkdownRendererProps {
  /** 렌더링할 Markdown 콘텐츠 */
  content: string;
  /** 추가 CSS 클래스 */
  className?: string;
}

/**
 * Markdown 콘텐츠를 HTML로 렌더링하는 컴포넌트
 * GFM(GitHub Flavored Markdown) 지원: 테이블, 취소선, 체크박스 등
 */
export function MarkdownRenderer({
  content,
  className = '',
}: MarkdownRendererProps) {
  return (
    <div className={`prose prose-sm prose-invert max-w-none ${className}`.trim()}>
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
    </div>
  );
}
