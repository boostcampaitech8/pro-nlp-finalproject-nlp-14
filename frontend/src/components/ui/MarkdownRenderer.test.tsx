/**
 * MarkdownRenderer 컴포넌트 테스트
 */

import { describe, it, expect } from 'vitest';
import { render, screen } from '@/test/test-utils';
import { MarkdownRenderer } from './MarkdownRenderer';

describe('MarkdownRenderer', () => {
  it('일반 텍스트를 렌더링한다', () => {
    render(<MarkdownRenderer content="Hello World" />);
    expect(screen.getByText('Hello World')).toBeInTheDocument();
  });

  it('헤더를 렌더링한다', () => {
    render(<MarkdownRenderer content="# 제목" />);
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('제목');
  });

  it('h2 헤더를 렌더링한다', () => {
    render(<MarkdownRenderer content="## 소제목" />);
    expect(screen.getByRole('heading', { level: 2 })).toHaveTextContent(
      '소제목'
    );
  });

  it('굵은 텍스트를 렌더링한다', () => {
    render(<MarkdownRenderer content="**굵은 글씨**" />);
    expect(screen.getByText('굵은 글씨').tagName).toBe('STRONG');
  });

  it('기울임 텍스트를 렌더링한다', () => {
    render(<MarkdownRenderer content="*기울임*" />);
    expect(screen.getByText('기울임').tagName).toBe('EM');
  });

  it('목록을 렌더링한다', () => {
    render(<MarkdownRenderer content={`- 항목1
- 항목2`} />);
    expect(screen.getByText('항목1')).toBeInTheDocument();
    expect(screen.getByText('항목2')).toBeInTheDocument();
  });

  it('번호 목록을 렌더링한다', () => {
    render(<MarkdownRenderer content={`1. 첫번째
2. 두번째`} />);
    expect(screen.getByText('첫번째')).toBeInTheDocument();
    expect(screen.getByText('두번째')).toBeInTheDocument();
  });

  it('링크를 렌더링한다', () => {
    render(<MarkdownRenderer content="[링크](https://example.com)" />);
    const link = screen.getByRole('link', { name: '링크' });
    expect(link).toHaveAttribute('href', 'https://example.com');
  });

  it('인라인 코드를 렌더링한다', () => {
    render(<MarkdownRenderer content="`코드`" />);
    expect(screen.getByText('코드').tagName).toBe('CODE');
  });

  it('className을 전달한다', () => {
    const { container } = render(
      <MarkdownRenderer content="test" className="custom-class" />
    );
    expect(container.firstChild).toHaveClass('custom-class');
  });

  it('빈 문자열을 처리한다', () => {
    const { container } = render(<MarkdownRenderer content="" />);
    expect(container.firstChild).toBeInTheDocument();
  });

  it('GFM 테이블을 렌더링한다', () => {
    const tableContent = `| 헤더1 | 헤더2 |
| --- | --- |
| 셀1 | 셀2 |`;
    render(<MarkdownRenderer content={tableContent} />);
    expect(screen.getByText('헤더1')).toBeInTheDocument();
    expect(screen.getByText('셀1')).toBeInTheDocument();
  });

  it('취소선을 렌더링한다', () => {
    render(<MarkdownRenderer content="~~취소선~~" />);
    expect(screen.getByText('취소선').tagName).toBe('DEL');
  });
});
