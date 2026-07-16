// Sonner stub
export const toast = {
  success: (msg: string) => console.log("[toast success]", msg),
  error: (msg: string) => console.error("[toast error]", msg),
  info: (msg: string) => console.log("[toast info]", msg),
  warning: (msg: string) => console.warn("[toast warn]", msg),
};
export const Toaster = () => null;
