import { useQuery } from '@tanstack/react-query'
import { fetchCatalog } from '../api'
import { queryKeys } from './keys'

/** One page of the full IDX catalog (search by ticker/name). `page` is 0-based. */
export function useCatalog(q: string, page: number, pageSize: number) {
  return useQuery({
    queryKey: queryKeys.catalog(q, page, pageSize),
    queryFn: () => fetchCatalog(q, pageSize, page * pageSize),
    placeholderData: (prev) => prev, // keep the old page visible while the next loads
  })
}
