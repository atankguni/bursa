import { useQuery } from '@tanstack/react-query'
import { fetchCatalog } from '../api'
import { queryKeys } from './keys'

/** The full IDX catalog (search by ticker/name). */
export function useCatalog(q: string) {
  return useQuery({
    queryKey: queryKeys.catalog(q),
    queryFn: () => fetchCatalog(q, 100),
    placeholderData: (prev) => prev,
  })
}
