import { useQuery } from '@tanstack/react-query'
import { fetchAssistantStatus, fetchChats } from '../api'
import { queryKeys } from './keys'

/** Whether the assistant is set up, and how many questions are left today. */
export function useAssistantStatus(enabled = true) {
  return useQuery({
    queryKey: queryKeys.assistantStatus,
    queryFn: fetchAssistantStatus,
    enabled,
  })
}

/** The user's saved chats, most recently used first. */
export function useAssistantChats(enabled = true) {
  return useQuery({
    queryKey: queryKeys.assistantChats,
    queryFn: fetchChats,
    enabled,
  })
}
