export const toast = {
  success: (msg: string) => console.log("[toast]", msg),
  error: (msg: string) => console.error("[toast]", msg),
  info: (msg: string) => console.info("[toast]", msg),
  warning: (msg: string) => console.warn("[toast]", msg),
};

export const Toaster = () => null;
