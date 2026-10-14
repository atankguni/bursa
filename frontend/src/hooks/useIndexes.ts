import { useQuery } from '@tanstack/react-query'
import { fetchIndexes } from '../api'
import { queryKeys } from './keys'

/** Available index names for the selector (falls back handled by the caller). */
export function useIndexes() {
  return useQuery({
    queryKey: queryKeys.indexes,
    queryFn: fetchIndexes,
  })
}
