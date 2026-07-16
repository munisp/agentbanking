const DEFAULT_PAGE_NUMBER = 1;
const DEFAULT_PAGE_LIMIT = 0;

export function getPagination(query: any) {
  const page = Math.abs(Number(query.page)) || DEFAULT_PAGE_NUMBER;
  const limit = Math.abs(Number(query.limit)) || DEFAULT_PAGE_LIMIT;
  const extraSkip = Number(query.extraSkip ?? 0);

  const skip = (page - 1) * limit + extraSkip;

  return {
    skip,
    limit,
  };
}
