// SSE 流式问答客户端：fetch + ReadableStream 逐帧解析
// （EventSource 不支持 POST 与 Authorization 头，故自实现）
// 事件协议：meta → delta* → references → done / error，帧间空行分隔

export async function streamChat(body, handlers = {}) {
  const { onMeta, onDelta, onReferences, onDone, onError } = handlers
  const token = localStorage.getItem('token') || ''

  const res = await fetch('/api/chat', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(body),
  })

  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    if (res.status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      location.href = '/login'
    }
    throw new Error(data.detail || `请求失败 (${res.status})`)
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  const parseFrame = (frame) => {
    const event = /^event:\s*(\w+)/m.exec(frame)?.[1]
    const data = /^data:\s*(.+)$/m.exec(frame)?.[1]
    if (!event || data === undefined) return
    let payload
    try {
      payload = JSON.parse(data)
    } catch {
      return
    }
    switch (event) {
      case 'meta': onMeta?.(payload); break
      case 'delta': onDelta?.(payload); break
      case 'references': onReferences?.(payload); break
      case 'done': onDone?.(payload); break
      case 'error': onError?.(new Error(payload.detail || '服务异常')); break
    }
  }

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    let idx
    while ((idx = buffer.indexOf('\n\n')) >= 0) {
      const frame = buffer.slice(0, idx)
      buffer = buffer.slice(idx + 2)
      parseFrame(frame)
    }
  }
  // 处理残留帧
  if (buffer.trim()) parseFrame(buffer)
}
