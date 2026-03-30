/**
 * react-markdown 모의 구현
 * 테스트 환경에서 실제 Markdown 파싱 없이 간단한 변환만 수행
 */

export default function ReactMarkdown({ children: content }: { children: string }) {
  if (!content) return <div />;

  const text = String(content);

  // # Heading
  if (text.startsWith('# ')) {
    return <h1>{text.slice(2)}</h1>;
  }
  // ## Heading
  if (text.startsWith('## ')) {
    return <h2>{text.slice(3)}</h2>;
  }
  // **bold**
  if (text.match(/^\*\*(.+)\*\*$/)) {
    return <strong>{text.slice(2, -2)}</strong>;
  }
  // *italic*
  if (text.match(/^\*(.+)\*$/)) {
    return <em>{text.slice(1, -1)}</em>;
  }
  // `code`
  if (text.match(/^`(.+)`$/)) {
    return <code>{text.slice(1, -1)}</code>;
  }
  // [link](url)
  const linkMatch = text.match(/^\[([^\]]+)\]\(([^)]+)\)$/);
  if (linkMatch) {
    return <a href={linkMatch[2]}>{linkMatch[1]}</a>;
  }
  // ~~strikethrough~~
  if (text.match(/^~~(.+)~~$/)) {
    return <del>{text.slice(2, -2)}</del>;
  }
  // Multi-line content (lists, tables)
  if (text.includes('\n')) {
    const lines = text.split('\n');
    // List detection
    const hasListItem = lines.some(line => line.match(/^[-*]\s/) || line.match(/^\d+\.\s/));
    if (hasListItem) {
      return (
        <div>
          {lines.map((line, i) => {
            if (line.match(/^[-*]\s(.+)/)) {
              return <li key={i}>{line.replace(/^[-*]\s/, '')}</li>;
            }
            if (line.match(/^\d+\.\s(.+)/)) {
              return <li key={i}>{line.replace(/^\d+\.\s/, '')}</li>;
            }
            return null;
          })}
        </div>
      );
    }
    // Table detection
    if (text.includes('|')) {
      const cells = lines.flatMap(line =>
        line.split('|').filter(c => c.trim() && !c.match(/^-+$/)).map(c => c.trim())
      );
      return (
        <div>
          {cells.map((cell, i) => <span key={i}>{cell}</span>)}
        </div>
      );
    }
  }

  return <div>{text}</div>;
}
