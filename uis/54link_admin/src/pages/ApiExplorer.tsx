import { createTRPCClient, httpBatchLink } from "@trpc/client";
import {
  ChevronDown,
  ChevronRight,
  Loader2,
  Play,
  Search,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import superjson from "superjson";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "../components/ui/card";
import { Input } from "../components/ui/input";

/**
 * ApiExplorer — read-only catalog of every backend tRPC router/procedure.
 *
 * The catalog is generated from the backend source audit and served as a
 * static asset (/api-catalog.json), so this page adds no bundle bloat.
 *
 * Invocation policy:
 *  - "query" procedures expose a manual "Run" button that calls the procedure
 *    with NO input through a vanilla tRPC client configured exactly like the
 *    app's client in main.tsx (httpBatchLink -> /api/trpc, superjson,
 *    credentials: "include"). Nothing is auto-executed.
 *  - "mutation" procedures are NEVER invoked from this page — catalog view only.
 */

interface CatalogProcedure {
  name: string;
  kind: "query" | "mutation" | string;
}

interface ApiCatalog {
  generated_from_commit?: string;
  router_count?: number;
  procedure_count?: number;
  routers: Record<string, CatalogProcedure[]>;
}

type RunState =
  | { status: "idle" }
  | { status: "running" }
  | { status: "ok"; data: unknown }
  | { status: "error"; message: string };

// Vanilla (untyped) tRPC client — same link configuration as src/main.tsx so
// auth cookies and the superjson transformer behave identically. Typed hooks
// (trpc.useQuery) cannot be used here because procedure paths are dynamic.
const explorerClient = createTRPCClient<any>({
  links: [
    httpBatchLink({
      url: "/api/trpc",
      transformer: superjson,
      fetch(input, init) {
        return globalThis.fetch(input, {
          ...(init ?? {}),
          credentials: "include",
        });
      },
    }),
  ],
});

export default function ApiExplorer() {
  const [catalog, setCatalog] = useState<ApiCatalog | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [runs, setRuns] = useState<Record<string, RunState>>({});

  useEffect(() => {
    fetch("/api-catalog.json")
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((data: ApiCatalog) => setCatalog(data))
      .catch((err: unknown) =>
        setLoadError(err instanceof Error ? err.message : "Failed to load catalog")
      );
  }, []);

  const routerEntries = useMemo(() => {
    if (!catalog) return [];
    const q = search.trim().toLowerCase();
    return Object.entries(catalog.routers)
      .map(([router, procs]) => {
        if (!q) return [router, procs] as const;
        const matchingProcs = procs.filter((p) =>
          p.name.toLowerCase().includes(q)
        );
        if (router.toLowerCase().includes(q)) return [router, procs] as const;
        if (matchingProcs.length > 0) return [router, matchingProcs] as const;
        return null;
      })
      .filter((e): e is readonly [string, CatalogProcedure[]] => e !== null)
      .sort(([a], [b]) => a.localeCompare(b));
  }, [catalog, search]);

  const runQuery = (router: string, proc: string) => {
    const key = `${router}.${proc}`;
    setRuns((prev) => ({ ...prev, [key]: { status: "running" } }));
    explorerClient
      .query(key)
      .then((data: unknown) =>
        setRuns((prev) => ({ ...prev, [key]: { status: "ok", data } }))
      )
      .catch((err: unknown) =>
        setRuns((prev) => ({
          ...prev,
          [key]: {
            status: "error",
            message: err instanceof Error ? err.message : String(err),
          },
        }))
      );
  };

  if (loadError) {
    return (
      <div className="p-6">
        <Card>
          <CardHeader>
            <CardTitle>API Explorer</CardTitle>
            <CardDescription>
              Failed to load /api-catalog.json: {loadError}
            </CardDescription>
          </CardHeader>
        </Card>
      </div>
    );
  }

  if (!catalog) {
    return (
      <div className="flex items-center justify-center p-8 text-sm text-muted-foreground">
        <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Loading API catalog…
      </div>
    );
  }

  return (
    <div className="p-6 space-y-4">
      <div>
        <h1 className="text-2xl font-semibold">API Explorer</h1>
        <p className="text-sm text-muted-foreground">
          {catalog.router_count ?? routerEntries.length} routers ·{" "}
          {catalog.procedure_count ?? "?"} procedures
          {catalog.generated_from_commit
            ? ` · backend commit ${catalog.generated_from_commit.slice(0, 8)}`
            : ""}
          . Queries can be run manually with empty input; mutations are
          catalog-only and are never invoked from this page.
        </p>
      </div>

      <div className="relative max-w-md">
        <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
        <Input
          className="pl-8"
          placeholder="Search routers or procedures…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      <div className="space-y-2">
        {routerEntries.length === 0 && (
          <p className="text-sm text-muted-foreground">
            No routers match “{search}”.
          </p>
        )}
        {routerEntries.map(([router, procs]) => {
          const isOpen = !!expanded[router];
          const queryCount = procs.filter((p) => p.kind === "query").length;
          const mutationCount = procs.length - queryCount;
          return (
            <Card key={router}>
              <CardHeader
                className="cursor-pointer py-3"
                onClick={() =>
                  setExpanded((prev) => ({ ...prev, [router]: !prev[router] }))
                }
              >
                <div className="flex items-center gap-2">
                  {isOpen ? (
                    <ChevronDown className="h-4 w-4" />
                  ) : (
                    <ChevronRight className="h-4 w-4" />
                  )}
                  <CardTitle className="text-base font-mono">{router}</CardTitle>
                  <Badge variant="secondary">{procs.length} procedures</Badge>
                  <Badge variant="outline">{queryCount} query</Badge>
                  <Badge variant="outline">{mutationCount} mutation</Badge>
                </div>
              </CardHeader>
              {isOpen && (
                <CardContent className="pt-0">
                  <ul className="divide-y">
                    {procs.map((proc) => {
                      const key = `${router}.${proc.name}`;
                      const run = runs[key] ?? { status: "idle" };
                      return (
                        <li key={proc.name} className="py-2">
                          <div className="flex items-center gap-2">
                            <code className="text-sm">{proc.name}</code>
                            <Badge
                              variant={
                                proc.kind === "mutation"
                                  ? "destructive"
                                  : "default"
                              }
                            >
                              {proc.kind}
                            </Badge>
                            {proc.kind === "query" && (
                              <Button
                                size="sm"
                                variant="outline"
                                disabled={run.status === "running"}
                                onClick={() => runQuery(router, proc.name)}
                              >
                                {run.status === "running" ? (
                                  <Loader2 className="mr-1 h-3 w-3 animate-spin" />
                                ) : (
                                  <Play className="mr-1 h-3 w-3" />
                                )}
                                Run
                              </Button>
                            )}
                          </div>
                          {run.status === "ok" && (
                            <pre className="mt-2 max-h-64 overflow-auto rounded bg-muted p-2 text-xs">
                              {JSON.stringify(run.data, null, 2)}
                            </pre>
                          )}
                          {run.status === "error" && (
                            <p className="mt-2 text-xs text-destructive">
                              {run.message}
                            </p>
                          )}
                        </li>
                      );
                    })}
                  </ul>
                </CardContent>
              )}
            </Card>
          );
        })}
      </div>
    </div>
  );
}
