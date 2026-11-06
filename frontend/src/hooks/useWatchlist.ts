import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  addToWatchlist,
  errorMessage,
  errorStatus,
  fetchWatchlist,
  removeFromWatchlist,
  type WatchlistItem,
} from '../api'
import { useSettings } from '../lib/settings'
import { queryKeys } from './keys'

/** The saved watchlist. Poll only where prices are shown, and only if enabled. */
export function useWatchlist(options?: { poll?: boolean }) {
  const { settings } = useSettings()
  const interval =
    options?.poll && settings.autoRefresh ? settings.refreshSeconds * 1000 : false
  return useQuery({
    queryKey: queryKeys.watchlist,
    queryFn: fetchWatchlist,
    refetchInterval: interval,
  })
}

// A newly watched stock's fundamentals arrive in the background: re-read then.
const SYNC_REFETCH_MS = [4_000, 12_000]

/**
 * Add / remove watchlist stocks with instant feedback: `isWatched` flips at the
 * click, `isPending` drives a spinner, and a failure flips it back with `error`.
 */
export function useWatchToggle() {
  const qc = useQueryClient()
  const { data: list = [] } = useWatchlist()
  // Clicked and not answered yet: what the button should already show.
  const [pending, setPending] = useState<Record<string, 'add' | 'remove'>>({})
  const [error, setError] = useState<string | null>(null)

  const mark = (ticker: string, op: 'add' | 'remove' | null) =>
    setPending(({ [ticker]: _, ...rest }) => (op ? { ...rest, [ticker]: op } : rest))
  const setList = (update: (items: WatchlistItem[]) => WatchlistItem[]) =>
    qc.setQueryData<WatchlistItem[]>(queryKeys.watchlist, (items) => update(items ?? []))
  const refetchSoon = () =>
    SYNC_REFETCH_MS.forEach((ms) =>
      window.setTimeout(
        () => void qc.invalidateQueries({ queryKey: queryKeys.watchlist }),
        ms,
      ),
    )

  const add = useMutation({
    mutationFn: addToWatchlist,
    onMutate: (ticker) => {
      setError(null)
      mark(ticker, 'add')
    },
    onSuccess: (item) => {
      setList((items) =>
        items.some((w) => w.ticker === item.ticker) ? items : [...items, item],
      )
      if (item.syncing) refetchSoon()
    },
    onError: (err, ticker) => {
      // Already there (another tab or device): just show the current list.
      if (errorStatus(err) === 409)
        void qc.invalidateQueries({ queryKey: queryKeys.watchlist })
      else setError(errorMessage(err, `Couldn't add ${ticker} to the watchlist.`))
    },
    onSettled: (_data, _err, ticker) => mark(ticker, null),
  })

  const remove = useMutation({
    mutationFn: removeFromWatchlist,
    onMutate: (ticker) => {
      setError(null)
      mark(ticker, 'remove')
    },
    onSuccess: (_data, ticker) =>
      setList((items) => items.filter((w) => w.ticker !== ticker)),
    onError: (err, ticker) =>
      setError(errorMessage(err, `Couldn't remove ${ticker} from the watchlist.`)),
    onSettled: (_data, _err, ticker) => mark(ticker, null),
  })

  const inList = (ticker: string) => list.some((w) => w.ticker === ticker)
  return {
    isWatched: (ticker: string) =>
      pending[ticker] ? pending[ticker] === 'add' : inList(ticker),
    isPending: (ticker: string) => ticker in pending,
    toggle: (ticker: string) => {
      if (ticker in pending) return
      if (inList(ticker)) remove.mutate(ticker)
      else add.mutate(ticker)
    },
    add: (ticker: string) => {
      if (!(ticker in pending) && !inList(ticker)) add.mutate(ticker)
    },
    error,
  }
}
