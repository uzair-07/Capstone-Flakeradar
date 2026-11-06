import type { RunSummary } from '../api'

// A thin stacked bar: the share of passed, failed, error and skipped tests in one run.
export function ResultBar({ run }: { run: RunSummary }) {
  const parts = [
    { key: 'passed', value: run.passed },
    { key: 'failed', value: run.failed },
    { key: 'error', value: run.errored },
    { key: 'skipped', value: run.skipped },
  ].filter((part) => part.value > 0)
  const label = `${run.passed} passed, ${run.failed} failed, ${run.errored} errors, ${run.skipped} skipped`
  return (
    <div className="result-bar" role="img" aria-label={label} title={label}>
      {parts.map((part) => (
        <span
          key={part.key}
          className={`seg seg-${part.key}`}
          style={{ flexGrow: part.value }}
        />
      ))}
    </div>
  )
}
