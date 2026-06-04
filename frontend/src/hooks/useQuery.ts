import { useState, useCallback, useEffect, useRef } from 'react'
import { postQuery } from '../api/client'
import type { QueryResponse } from '../types/api'

export interface QueryOptions {
  tokenBudget: number
}

interface UseQueryReturn {
  task: string
  setTask: (task: string) => void
  topK: number
  setTopK: (topK: number) => void
  options: QueryOptions
  setOptions: (opts: QueryOptions) => void
  loading: boolean
  error: string | null
  result: QueryResponse | null
  runQuery: () => Promise<void>
  resetQuery: () => void
}

const DEFAULT_OPTIONS: QueryOptions = {
  tokenBudget: 6000,
}

export function useQuery(onResult?: (r: QueryResponse) => void): UseQueryReturn {
  const initialTask = new URLSearchParams(window.location.search).get('task') ?? ''
  const [task, setTask] = useState(initialTask)
  const [topK, setTopK] = useState(10)
  const [options, setOptions] = useState<QueryOptions>(DEFAULT_OPTIONS)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<QueryResponse | null>(null)
  const autoRan = useRef(false)

  const runQuery = useCallback(async () => {
    if (!task.trim()) return
    setLoading(true)
    setError(null)
    try {
      const data = await postQuery({
        task: task.trim(),
        top_k: topK,
        token_budget: options.tokenBudget,
      })
      setResult(data)
      onResult?.(data)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Query failed')
    } finally {
      setLoading(false)
    }
  }, [task, topK, options, onResult])

  const resetQuery = useCallback(() => {
    setResult(null)
    setError(null)
  }, [])

  useEffect(() => {
    if (initialTask && !autoRan.current) {
      autoRan.current = true
      runQuery()
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  return {
    task, setTask, topK, setTopK, options, setOptions,
    loading, error, result, runQuery, resetQuery,
  }
}
