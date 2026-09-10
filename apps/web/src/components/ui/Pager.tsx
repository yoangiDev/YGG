import { Button } from "./Button";

export function Pager({
  page,
  pageSize,
  total,
  onPageChange,
}: {
  page: number;
  pageSize: number;
  total: number;
  onPageChange: (page: number) => void;
}) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  const from = total === 0 ? 0 : page * pageSize + 1;
  const to = Math.min(total, (page + 1) * pageSize);

  return (
    <nav
      aria-label="Pagination"
      className="flex items-center justify-between gap-3 border-t border-border/60 px-4 py-3 text-xs text-muted"
    >
      <span>
        {from}–{to} of {total}
      </span>
      <div className="flex gap-1">
        <Button variant="ghost" size="sm" disabled={page === 0} onClick={() => onPageChange(page - 1)}>
          Previous
        </Button>
        <Button variant="ghost" size="sm" disabled={page + 1 >= pages} onClick={() => onPageChange(page + 1)}>
          Next
        </Button>
      </div>
    </nav>
  );
}
