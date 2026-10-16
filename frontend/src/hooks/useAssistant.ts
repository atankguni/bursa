import { useQuery } from '@tanstack/react-query'
import { fetchAssistantStatus } from '../api'
import { queryKeys } from './keys'

/** Whether the assistant is set up, and how many questions are left today. */
export function useAssistantStatus(enabled = true) {
  return useQuery({
    queryKey: queryKeys.assistantStatus,
    queryFn: fetchAssistantStatus,
    enabled,
  })
}
