import { api } from './client'
import type {
  AssistantReply,
  AssistantStatus,
  ChatDetail,
  ChatSummary,
  ChatTurn,
} from './types'

export async function fetchAssistantStatus(): Promise<AssistantStatus> {
  const { data } = await api.get<AssistantStatus>('/api/assistant/status')
  return data
}

/** `chatId`: the saved chat this continues (null starts a new one). */
export async function askAssistant(
  messages: ChatTurn[],
  context?: string,
  chatId?: number | null,
): Promise<AssistantReply> {
  // Tool calls + the model can take a while on the free tier.
  const { data } = await api.post<AssistantReply>(
    '/api/assistant/chat',
    { messages, context, chat_id: chatId ?? null },
    { timeout: 120_000 },
  )
  return data
}

export async function fetchChats(): Promise<ChatSummary[]> {
  const { data } = await api.get<ChatSummary[]>('/api/assistant/chats')
  return data
}

export async function fetchChat(id: number): Promise<ChatDetail> {
  const { data } = await api.get<ChatDetail>(`/api/assistant/chats/${id}`)
  return data
}

export async function deleteChat(id: number): Promise<void> {
  await api.delete(`/api/assistant/chats/${id}`)
}

export async function deleteAllChats(): Promise<void> {
  await api.delete('/api/assistant/chats')
}
