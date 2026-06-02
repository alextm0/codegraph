import { useState, useEffect, useRef } from 'react'
import { formatTimeHms } from '../utils/formatTime'

export interface WSStatus {
  type: 'file_changed' | 'rebuild_started' | 'rebuild_progress' | 'rebuild_complete' | 'rebuild_error'
  path?: string
  detail?: string
  stage?: 'parsing' | 'building'
  files_parsed?: number
  files_total?: number
  current_file?: string
  node_count?: number
  edge_count?: number
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
          timestamp: data.timestamp ? formatTimeHms(data.timestamp) : formatTimeHms(new Date()),
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
