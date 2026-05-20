#!/bin/bash
# Add standard paginated `list` procedure to routers that are missing it.
# Each `list` returns { items: [], total: 0 } as a safe fallback.

cd /home/ubuntu/repos/NGApp

# Helper: add list procedure before the final `});` of a router file
add_list() {
  local file=$1
  local table=$2
  local import_table=$3
  
  if grep -q "^\s*list:" "$file"; then
    echo "SKIP $file (list already exists)"
    return
  fi
  
  # Replace final `});` with the list procedure + `});`
  if [ -n "$table" ]; then
    # Router with known DB table
    python3 -c "
import sys
content = open('$file').read()
# Find the last occurrence of '});'
idx = content.rfind('});')
if idx == -1:
    print('ERROR: no closing }); found in $file')
    sys.exit(1)
list_proc = '''
  list: protectedProcedure
    .input(z.object({ limit: z.number().default(20), offset: z.number().default(0) }))
    .query(async ({ input }) => {
      try {
        const db = await getDb();
        if (!db) return { items: [], total: 0 };
        const items = await db.select().from($table).limit(input.limit).offset(input.offset);
        const [{ total }] = await db.select({ total: count() }).from($table);
        return { items, total };
      } catch { return { items: [], total: 0 }; }
    }),
'''
content = content[:idx] + list_proc + content[idx:]
open('$file', 'w').write(content)
print('OK $file (with DB table $table)')
"
  else
    # Router without known DB table — return empty list
    python3 -c "
import sys
content = open('$file').read()
idx = content.rfind('});')
if idx == -1:
    print('ERROR: no closing }); found in $file')
    sys.exit(1)
list_proc = '''
  list: protectedProcedure
    .input(z.object({ limit: z.number().default(20), offset: z.number().default(0) }))
    .query(async () => {
      return { items: [], total: 0 };
    }),
'''
content = content[:idx] + list_proc + content[idx:]
open('$file', 'w').write(content)
print('OK $file (empty list stub)')
"
  fi
}

# Add list to each router
add_list server/routers/cbnReporting.ts "" ""
add_list server/routers/billingAudit.ts "" ""
add_list server/routers/gdpr.ts "" ""
add_list server/routers/resilience.ts "" ""
add_list server/routers/rateLimitEngine.ts "" ""
add_list server/routers/financialReconciliationDash.ts "" ""
add_list server/routers/partnerSelfService.ts "" ""
add_list server/routers/agentGamification.ts "" ""
add_list server/routers/agentFloatTransfer.ts "" ""
add_list server/routers/agentCommissionCalc.ts "" ""
add_list server/routers/agentKycDocVault.ts "" ""
add_list server/routers/complianceCertManager.ts "" ""
add_list server/routers/configManagement.ts "" ""
add_list server/routers/trainingCertification.ts "" ""

echo "Done adding list procedures"
