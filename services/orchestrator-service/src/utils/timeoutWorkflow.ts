export async function timeoutWorkflow<T>(
  promise: Promise<T>,
  ms: number,
  onTimeout: () => void | Promise<void>
): Promise<T> {
  let timeout: NodeJS.Timeout | undefined = undefined;

  const timeoutPromise = new Promise<never>((_, reject) => {
    timeout = setTimeout(async () => {
      try {
        await onTimeout();
        reject(new Error(`Operation timed out after ${ms}ms`));
      } catch (err) {
        reject(new Error(`Timeout cleanup failed: ${err instanceof Error ? err.message : String(err)}`));
      }
    }, ms);
  });

  try {
    return await Promise.race([promise, timeoutPromise]);
  } finally {
    if (timeout) clearTimeout(timeout);
  }
}
