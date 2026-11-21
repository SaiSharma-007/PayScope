import { Link } from 'react-router-dom'
import { InsightCard } from '../workspace/InsightHelp'
import { useInsightDetails } from '../workspace/useInsightDetails'

export default function ChatTitle({ chat, selected }) {
  const details = useInsightDetails()
  return <>
    <Link
      to={`?chat=${chat.id}`}
      aria-current={selected ? 'page' : undefined}
      aria-label={chat.title}
      {...details.trigger(chat.id)}
    >
      <span className="agent-chat-title">{chat.title}</span>
    </Link>
    <InsightCard details={details} label="Conversation title">
      <span className="agent-chat-title-preview">{chat.title}</span>
    </InsightCard>
  </>
}
