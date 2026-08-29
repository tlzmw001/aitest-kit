import { consumeSseStream } from './sse'
import { expect, test } from 'vitest'

function chunked(...chunks: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder()
  return new ReadableStream({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk))
      controller.close()
    },
  })
}

test('SSE parser survives chunk boundaries and ignores heartbeats', async () => {
  const seen: string[] = []
  let activity = 0
  await consumeSseStream(
    chunked(
      ': heartbeat\n\nid: 1\nevent: text_delta\nda',
      'ta: {"event_id":"e1","seq":1,"session_id":"s1","type":"text_delta",',
      '"timestamp":"now","correlation_id":"p1","payload":{"delta":"你好"}}\n\n',
    ),
    (event) => seen.push(String(event.payload.delta)),
    () => activity += 1,
  )

  expect(seen).toEqual(['你好'])
  expect(activity).toBe(2)
})
