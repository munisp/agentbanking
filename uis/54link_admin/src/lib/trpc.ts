import { createTRPCReact } from "@trpc/react-query";

// Mock AppRouter type - replace with actual server routers when backend is available
// Using 'any' to bypass type checking until backend is available
export const trpc = createTRPCReact() as any;
