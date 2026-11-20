export default function Feedback({ message, onRetry }) {
  return (
    <main id="main" className="page feedback-page">
      <div className="panel feedback-panel">
        <p role={onRetry ? 'alert' : 'status'}>{message}</p>
        {onRetry && (
          <button className="button secondary" onClick={onRetry}>
            Try again
          </button>
        )}
      </div>
    </main>
  )
}
