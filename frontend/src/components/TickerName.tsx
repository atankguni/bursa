/**
 * Phones: the company name under the ticker, standing in for the Name column
 * (hidden below `md` to leave room for prices).
 */
export default function TickerName({ name }: { name: string | null | undefined }) {
  if (!name) return null
  return (
    <span className="block max-w-28 truncate text-[10px] font-normal text-subtle md:hidden">
      {name}
    </span>
  )
}
