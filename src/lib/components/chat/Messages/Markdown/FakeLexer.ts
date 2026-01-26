import type { Token } from 'marked';

export function fakeLexer(content: string): Token[] {
  if (!content) return [];

  return [
    {
      type: 'paragraph',
      raw: content,
      text: content,
      tokens: [
        {
          type: 'text',
          raw: content,
          text: content
        }
      ]
    }
  ];
}
