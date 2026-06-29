import * as z from "zod";
import { PaginationSchema } from "..";

export const FetchTenantsSchema = z.object({}).and(PaginationSchema);
