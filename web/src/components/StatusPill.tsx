import type { TestStatus } from '../api'

const LABELS: Record<TestStatus, string> = {
  passed: 'Passed',
  failed: 'Failed',
  error: 'Error',
  skipped: 'Skipped',
}

export function StatusPill({ status }: { status: TestStatus }) {
  return <span className={`pill pill-${status}`}>{LABELS[status]}</span>
}
