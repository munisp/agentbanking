/**
 * tRPC stub — these pages are being migrated to direct REST API calls.
 * This stub prevents TypeScript errors for pages not yet migrated.
 * Do not use this in new pages; import directly from ../../utils/api instead.
 */

function makeStubQuery() {
  return {
    data: undefined,
    isLoading: false,
    error: null,
    refetch: () => {},
  };
}

function makeStubMutation() {
  return [(data?: any) => Promise.resolve(null), { isLoading: false }] as const;
}

function makeNamespaceProxy(): any {
  return new Proxy(
    {},
    {
      get: () => makeNamespaceProxy(),
      apply: () => makeStubQuery(),
    }
  );
}

export const trpc: any = new Proxy(
  {},
  {
    get: (_target, _prop) => makeNamespaceProxy(),
  }
);
