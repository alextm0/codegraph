import { Component } from 'react'
import type { ReactNode, ErrorInfo } from 'react'

interface Props {
  children: ReactNode
  fallback?: ReactNode
}

interface State {
  hasError: boolean
  message: string
}

export default class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, message: '' }

  static getDerivedStateFromError(error: unknown): State {
    const message = error instanceof Error ? error.message : String(error)
    return { hasError: true, message }
  }

  componentDidCatch(error: unknown, info: ErrorInfo) {
    console.error('ErrorBoundary caught:', error, info.componentStack)
  }

  render() {
    if (this.state.hasError) {
      return this.props.fallback ?? (
        <div style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 8,
          padding: 24,
          color: 'var(--red)',
          fontSize: 12,
          fontFamily: 'var(--mono)',
        }}>
          <div style={{ fontWeight: 600 }}>Something went wrong</div>
          <div style={{ color: 'var(--text-dim)', wordBreak: 'break-all', textAlign: 'center' }}>
            {this.state.message}
          </div>
          <button
            onClick={() => this.setState({ hasError: false, message: '' })}
            style={{
              marginTop: 8,
              padding: '4px 12px',
              background: 'var(--surface2)',
              border: '1px solid var(--border)',
              borderRadius: 'var(--radius-sm)',
              color: 'var(--text)',
              cursor: 'pointer',
              fontFamily: 'var(--font-mono)',
              fontSize: 12,
            }}
          >
            Dismiss
          </button>
        </div>
      )
    }
    return this.props.children
  }
}
