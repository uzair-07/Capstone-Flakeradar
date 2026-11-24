// Score from 0 to 1 as a short horizontal meter with its value.
export function ScoreBar({ score, flagged }: { score: number; flagged: boolean }) {
  const percent = Math.round(score * 100)
  return (
    <div className="score" title={`Flakiness score ${score.toFixed(2)} of 1`}>
      <div className="score-track" aria-hidden="true">
        <span
          className={`score-fill ${flagged ? 'score-flagged' : ''}`}
          style={{ width: `${Math.max(percent, score > 0 ? 3 : 0)}%` }}
        />
      </div>
      <span className="score-value">{score.toFixed(2)}</span>
    </div>
  )
}
