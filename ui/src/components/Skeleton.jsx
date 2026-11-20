export default function Skeleton({
  width = '100%',
  height = '0.75rem',
  round = false,
}) {
  return (
    <span
      className="skeleton"
      aria-hidden="true"
      style={{ width, height, borderRadius: round ? '50%' : undefined }}
    />
  )
}
