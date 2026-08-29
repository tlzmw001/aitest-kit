import type { AgentEvent } from '../types'

export async function consumeSseStream(
  stream: ReadableStream<Uint8Array>,
  onEvent: (event: AgentEvent) => void,
  onActivity?: () => void,
): Promise<void> {
  const reader = stream.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  try {
    while (true) {
      const { done, value } = await reader.read()
      buffer += decoder.decode(value, { stream: !done })
      buffer = drainFrames(buffer, onEvent, onActivity, done)
      if (done) return
    }
  } finally {
    reader.releaseLock()
  }
}

function drainFrames(
  source: string,
  onEvent: (event: AgentEvent) => void,
  onActivity: (() => void) | undefined,
  flush: boolean,
): string {
  const normalized = source.replaceAll('\r\n', '\n')
  const frames = normalized.split('\n\n')
  const remainder = flush ? '' : (frames.pop() ?? '')
  for (const frame of frames) parseFrame(frame, onEvent, onActivity)
  if (flush && frames.length === 0 && normalized.trim()) parseFrame(normalized, onEvent, onActivity)
  return remainder
}

function parseFrame(frame: string, onEvent: (event: AgentEvent) => void, onActivity?: () => void): void {
  if (!frame.trim()) return
  onActivity?.()
  if (frame.trimStart().startsWith(':')) return
  const data = frame
    .split('\n')
    .filter((line) => line.startsWith('data:'))
    .map((line) => line.slice(5).trimStart())
    .join('\n')
  if (!data) return
  onEvent(JSON.parse(data) as AgentEvent)
}
