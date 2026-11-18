/** Parse SSE over arbitrary byte boundaries, including named events and CRLF. */
export async function consumeChatSse(reader, onEvent) {
  const decoder = new TextDecoder()
  let buffer = ''
  function emit(block) {
    let eventName = ''
    const dataLines = []
    for (const line of block.split(/\r?\n/)) {
      if (line.startsWith('event:')) eventName = line.slice(6).trim()
      else if (line.startsWith('data:')) dataLines.push(line.slice(5).replace(/^ /, ''))
    }
    const data = dataLines.join('\n')
    if (!data || data === '[DONE]') return
    const parsed = JSON.parse(data)
    if (!parsed.type && eventName) parsed.type = eventName
    if (parsed.type === 'done' && parsed.answer && !parsed.response) parsed.response = parsed.answer
    onEvent(parsed)
  }
  try {
    while (true) {
      const { done, value } = await reader.read()
      buffer += done ? decoder.decode() : decoder.decode(value, { stream: true })
      let match
      while ((match = /\r?\n\r?\n/.exec(buffer))) {
        emit(buffer.slice(0, match.index))
        buffer = buffer.slice(match.index + match[0].length)
      }
      if (done) {
        if (buffer.trim()) emit(buffer)
        break
      }
    }
  } finally {
    await reader.cancel().catch(() => {})
    reader.releaseLock()
  }
}
