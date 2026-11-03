export interface SSEFrame {
  event: string
  data: unknown
}

function parseFrame(raw: string): SSEFrame | null {
  let event = 'message'
  const data: string[] = []
  for (const line of raw.split('\n')) {
    if (!line || line.startsWith(':')) continue
    const i = line.indexOf(':')
    const field = i < 0 ? line : line.slice(0, i)
    const value = i < 0 ? '' : line.slice(i + 1).replace(/^ /, '')
    if (field === 'event') event = value
    else if (field === 'data') data.push(value)
  }
  return data.length ? { event, data: JSON.parse(data.join('\n')) } : null
}

/** Server-sent event frames from text chunks that may split a frame anywhere. */
export async function* parseSSE(chunks: AsyncIterable<string>): AsyncIterable<SSEFrame> {
  let buffer = ''
  for await (const chunk of chunks) {
    buffer = (buffer + chunk).replace(/\r\n?/g, '\n')
    let end: number
    while ((end = buffer.indexOf('\n\n')) >= 0) {
      const frame = parseFrame(buffer.slice(0, end))
      buffer = buffer.slice(end + 2)
      if (frame) yield frame
    }
  }
  const last = parseFrame(buffer) // a final frame without the trailing blank line
  if (last) yield last
}
