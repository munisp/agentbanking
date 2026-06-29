/**
 * tRPC stub — pages are being migrated to direct REST API calls.
 * This stub prevents TypeScript/runtime errors for pages not yet migrated.
 */

function makeStubQuery() {
  return {
    data: undefined,
    isLoading: false,
    isFetching: false,
    error: null,
    refetch: () => Promise.resolve({ data: undefined }),
    isError: false,
    isSuccess: true,
  };
}

function makeStubMutation() {
  return {
    mutate: (_data?: any) => {},
    mutateAsync: (_data?: any) => Promise.resolve(null),
    isPending: false,
    isLoading: false,
    isError: false,
    data: undefined,
    error: null,
  };
}

function makeNamespaceProxy(): any {
  const handler: ProxyHandler<object> = {
    get: (_t, _p) => makeNamespaceProxy(),
    apply: () => makeStubQuery(),
  };
  const fn = function () { return makeStubQuery(); } as any;
  return new Proxy(fn, handler);
}

export const trpc: any = new Proxy(
  {},
  {
    get: (_target, prop) => {
      if (prop === "useUtils") return () => makeNamespaceProxy();
      return makeNamespaceProxy();
    },
  }
);
