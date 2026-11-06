import type { ReactNode } from 'react'

interface NoticeProps {
  title: string
  tone?: 'neutral' | 'critical'
  children?: ReactNode
}

export function Notice({ title, tone = 'neutral', children }: NoticeProps) {
  return (
    <section className={`notice notice-${tone}`} role={tone === 'critical' ? 'alert' : undefined}>
      <h2>{title}</h2>
      {children && <div className="notice-body">{children}</div>}
    </section>
  )
}
