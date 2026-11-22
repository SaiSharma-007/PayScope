import { Line, LineChart, XAxis, YAxis } from 'recharts'
import { ChartContainer } from '@/components/ui/chart'

const chartConfig = {
  level: { label: 'Pay range', color: 'var(--chart-1)' },
  median: { label: 'Median', color: 'var(--chart-2)' },
}

function PayMark({ cx, cy, payload }) {
  if (payload.label === 'Median') {
    return (
      <path
        className="landing-median-mark"
        d={`M ${cx} ${cy - 11} l 11 11 -11 11 -11 -11 Z`}
        fill="var(--color-median)"
      />
    )
  }
  return <circle cx={cx} cy={cy} r={5} fill="var(--color-level)" />
}

export default function PayRange({ figures }) {
  const data = figures.map(figure => ({ ...figure, level: 0 }))
  const domain = [figures[0].amount, figures.at(-1).amount]
  return (
    <ChartContainer className="h-full w-full aspect-auto" config={chartConfig} initialDimension={{ width: 320, height: 48 }}>
      <LineChart data={data} margin={{ left: 16, right: 16, top: 0, bottom: 0 }} accessibilityLayer={false}>
        <XAxis dataKey="amount" type="number" domain={domain} hide />
        <YAxis dataKey="level" type="number" domain={[-1, 1]} hide />
        <Line dataKey="level" stroke="var(--color-level)" strokeWidth={3}
          activeDot={false} isAnimationActive={false} dot={PayMark} />
      </LineChart>
    </ChartContainer>
  )
}
