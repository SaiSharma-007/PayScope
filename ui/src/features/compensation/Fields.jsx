export function ErrorSummary({ error, onReload }) {
  if (!error) return null
  return (
    <div className="comp-error" role="alert" tabIndex={-1}>
      <strong>{error.message}</strong>
      {error.fields?.length > 0 && (
        <ul>
          {error.fields.map((field, index) => (
            <li key={index}>
              {field.loc.includes('components') &&
              Number.isInteger(field.loc[2])
                ? `Component ${field.loc[2] + 1}: `
                : ''}
              {field.msg.replace(/^Value error, /, '')}
            </li>
          ))}
        </ul>
      )}
      {error.status === 409 && onReload && (
        <button type="button" className="text-link" onClick={onReload}>
          Reload saved version
        </button>
      )}
    </div>
  )
}

export function FormField({ id, label, error, hint, multiline, ...props }) {
  const Control = multiline ? 'textarea' : 'input'
  return (
    <div className="comp-field">
      <label htmlFor={id}>{label}</label>
      <Control
        id={id}
        aria-invalid={!!error}
        aria-describedby={error || hint ? `${id}-help` : undefined}
        {...props}
      />
      {(error || hint) && (
        <small id={`${id}-help`} className={error ? 'error-message' : ''}>
          {error || hint}
        </small>
      )}
    </div>
  )
}
