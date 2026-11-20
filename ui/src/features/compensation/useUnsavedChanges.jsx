import { useBeforeUnload, useBlocker } from 'react-router-dom'
import { useAuth } from '../auth/useAuth'
import { DiscardDialog } from './DiscardDialog'

export function useUnsavedChanges(dirty) {
  const { session } = useAuth()
  const blocker = useBlocker(!!session && dirty)
  useBeforeUnload((event) => {
    if (dirty && session) {
      event.preventDefault()
      event.returnValue = ''
    }
  })
  return (
    <DiscardDialog
      open={blocker.state === 'blocked'}
      onCancel={() => blocker.reset?.()}
      onDiscard={() => blocker.proceed?.()}
    />
  )
}
