export function markSaved(cache, runId, savedId) {
  for (const entry of cache.values()) {
    if (entry.data?.turns) entry.data = { ...entry.data, turns: entry.data.turns.map((turn) => turn.run_id === runId ? { ...turn, saved_report_id: savedId } : turn) }
  }
}
