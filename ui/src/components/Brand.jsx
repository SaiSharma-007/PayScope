import { Link } from 'react-router-dom'
import { ChartNoAxesColumnIncreasing } from 'lucide-react'

export default function Brand() {
  return (
    <Link className="brand" to="/" aria-label="PayScope home">
      <span className="brand-mark">
        <ChartNoAxesColumnIncreasing
          size={24}
          strokeWidth={2.4}
          aria-hidden="true"
        />
      </span>
      <span className="brand-wordmark">PayScope<span className="brand-period">.</span></span>
    </Link>
  )
}
