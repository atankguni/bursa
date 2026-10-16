import { api } from './client'
import type { AssistantReply, AssistantStatus, ChatTurn } from './types'

export async function fetchAssistantStatus(): Promise<AssistantStatus> {
  const { data } = await api.get<AssistantStatus>('/api/assistant/status')
  return data
}

export async function askAssistant(
  messages: ChatTurn[],
  context?: string,
): Promise<AssistantReply> {
  // Tool calls + the model can take a while on the free tier.
  const { data } = await api.post<AssistantReply>(
    '/api/assistant/chat',
    { messages, context },
    { timeout: 120_000 },
  )
  return data
}
