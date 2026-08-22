/**
 * Shared builders for the funds-flow router unit tests.
 *
 * The routers under test talk to PostgreSQL through drizzle and to the
 * middleware mesh (Kafka / Redis / TigerBeetle / Fluvio / Permify). These
 * tests replace that infrastructure at the module boundary (vi.mock) — the
 * same approach as vitest.setup.ts — while executing the REAL router and
 * REAL transactionHelper code, so the guarded-debit / idempotency /
 * authorization behavior being asserted is the production code path.
 *
 * This file contains builders only; each test file performs its own vi.mock
 * calls (vi.mock is file-scoped and hoisted).
 */

/** Minimal tRPC caller context (shape mirrors server/lib/__tests__/testHelpers.ts). */
export function makeCtx(role: "admin" | "user" = "admin") {
  return {
    user: {
      id: 1,
      keycloakSub: "kc-test-1",
      name: "Test User",
      email: "test@54agent.io",
      role,
      loginMethod: "keycloak",
      lastSignedIn: new Date(),
      createdAt: new Date(),
      updatedAt: new Date(),
    },
    req: { headers: {} },
    res: { cookie: () => {}, clearCookie: () => {} },
  } as any;
}

export function makeAgentCtx() {
  return makeCtx("user");
}

/**
 * Stub for the "drizzle-orm" module. The mocked DB driver never inspects
 * query operators, so each operator is reduced to a tagged marker object.
 * `sql` keeps its template-tag call signature because transactionHelper and
 * the routers interpolate values into it.
 */
export function drizzleOrmStub() {
  const sqlTag = ((strings: TemplateStringsArray, ...values: unknown[]) => ({
    __sql: true,
    strings: Array.from(strings),
    values,
  })) as any;
  const marker = (op: string) => (...a: unknown[]) => ({ __op: op, args: a });
  return {
    sql: sqlTag,
    eq: marker("eq"),
    ne: marker("ne"),
    and: marker("and"),
    or: marker("or"),
    desc: marker("desc"),
    asc: marker("asc"),
    count: marker("count"),
    gte: marker("gte"),
    lte: marker("lte"),
    gt: marker("gt"),
    lt: marker("lt"),
    like: marker("like"),
    inArray: marker("inArray"),
    notInArray: marker("notInArray"),
    isNull: marker("isNull"),
    isNotNull: marker("isNotNull"),
  };
}

/**
 * Stub for the drizzle schema module (../../drizzle/schema from a router).
 * Tables are proxies: any column access yields a "table.column" string,
 * which is all the mocked operators/chains need.
 */
export function drizzleSchemaStub() {
  const table = (name: string) =>
    new Proxy(
      { __table: name },
      {
        get: (t, p) =>
          p in t ? (t as any)[p as string] : `${name}.${String(p)}`,
      }
    );
  return {
    transactions: table("transactions"),
    agents: table("agents"),
    merchants: table("merchants"),
    merchantSettlements: table("merchantSettlements"),
    floatReconciliations: table("floatReconciliations"),
  };
}

/** drizzle-style select chain resolving to `rows`. */
export function selectChain(rows: unknown[]) {
  const chain: any = {
    from: () => chain,
    where: () => chain,
    orderBy: () => chain,
    offset: () => chain,
    limit: async () => rows,
    then: (resolve: (v: unknown[]) => unknown) => resolve(rows),
  };
  return chain;
}

/** drizzle-style update chain; `returning()` resolves to `rows`. */
export function updateChain(rows: unknown[], capture?: { setValues: any[] }) {
  return {
    set: (v: any) => {
      capture?.setValues.push(v);
      return {
        where: () => ({ returning: async () => rows }),
      };
    },
  };
}

/** drizzle-style insert chain; `returning()` resolves to `rows`. */
export function insertChain(rows: unknown[], capture?: { values: any[] }) {
  return {
    values: (v: any) => {
      capture?.values.push(v);
      return { returning: async () => rows };
    },
  };
}

/** Pass-through tRPC middleware factory used to stub the sidecar/cache/hardening middleware. */
export function passThroughMiddleware(t: any) {
  return t.middleware(async ({ next, ctx }: any) => next({ ctx }));
}
