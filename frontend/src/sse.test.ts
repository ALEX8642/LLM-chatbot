import { describe, expect, it } from 'vitest'
import { parseSSE } from './sse'

async function* chunks(...parts: string[]) {
  for (const p of parts) yield p
}

async function collect<T>(it: AsyncIterable<T>): Promise<T[]> {
  const out: T[] = []
  for await (const x of it) out.push(x)
  return out
}

describe('parseSSE', () => {
  it('parseSSE splits frames across chunks', async () => {
    const frames = await collect(
      parseSSE(
        chunks(
          'event: retrieved\nda',
          'ta: {"pages": [3]}\n',
          '\nevent: claim_shown\r\ndata: {"claim": "a"}\r\n\r\n',
          'event: done\ndata: {"text": "x"}', // last frame, no blank line
        ),
      ),
    )
    expect(frames).toEqual([
      { event: 'retrieved', data: { pages: [3] } },
      { event: 'claim_shown', data: { claim: 'a' } },
      { event: 'done', data: { text: 'x' } },
    ])
  })

  it('joins multi-line data and skips comments and empty frames', async () => {
    const frames = await collect(
      parseSSE(chunks(': keepalive\n\n', 'event: done\ndata: {"a":\ndata: 1}\n\n')),
    )
    expect(frames).toEqual([{ event: 'done', data: { a: 1 } }])
  })
})
