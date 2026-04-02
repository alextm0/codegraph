import { useState, useEffect, useRef } from 'react'

export interface WSStatus {
  type: 'file_changed' | 'rebuild_started' | 'rebuild_complete'
  path?: string
  timestamp: string
}

export function useWebSocket() {
  const [lastMessage, setLastMessage] = useState<WSStatus | null>(null)
  const [connected, setConnected] = useState(false)
  const ws = useRef<WebSocket | null>(null)

  useEffect(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host === 'localhost:5173' ? 'localhost:8474' : window.location.host
    const socket = new WebSocket(`${protocol}//${host}/ws/status`)

    socket.onopen = () => setConnected(true)
    socket.onclose = () => setConnected(false)
    socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        setLastMessage({
          ...data,
          timestamp: new Date().toLocaleTimeString()
        })
      } catch (err) {
        console.error('WS parse error', err)
      }
    }

    ws.current = socket
    return () => socket.close()
  }, [])

  return { lastMessage, connected }
}
