import { useState, useCallback, useEffect, useRef } from 'react'
import { postQuery } from '../api/client'
import type { QueryResponse } from '../types/api'

interface UseQueryReturn {
  task: string
  setTask: (task: string) => void
  topK: number
  setTopK: (topK: number) => void
  loading: boolean
  error: string | null
  result: QueryResponse | null
  runQuery: () => Promise<void>
}

export function useQuery(onResult?: (r: QueryResponse) => void): UseQueryReturn {
  const initialTask = new URLSearchParams(window.location.search).get('task') ?? ''
  const [task, setTask] = useState(initialTask)
  const [topK, setTopK] = useState(10)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<QueryResponse | null>(null)
  const autoRan = useRef(false)

  const runQuery = useCallback(async () => {
    if (!task.trim()) return
    setLoading(true)
    setError(null)
    try {
      const data = await postQuery({ task: task.trim(), top_k: topK })
      setResult(data)
      onResult?.(data)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Query failed')
    } finally {
      setLoading(false)
    }
  }, [task, topK, onResult])

  useEffect(() => {
    if (initialTask && !autoRan.current) {
      autoRan.current = true
      runQuery()
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  return { task, setTask, topK, setTopK, loading, error, result, runQuery }
}
