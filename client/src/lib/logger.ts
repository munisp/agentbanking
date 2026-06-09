/**
 * Client-side logger — structured logging for the 54Link PWA.
 *
 * In production builds, debug/log are silenced; warn/error always print.
 * All output goes through this module so grepping for `console.log` in
 * client code can be treated as a lint error.
 */

const IS_PROD =
  typeof window !== "undefined" && window.location.hostname !== "localhost";

function noop() {}

export const logger = {
  debug: IS_PROD ? noop : console.debug.bind(console),
  log: IS_PROD ? noop : console.log.bind(console),
  info: IS_PROD ? noop : console.info.bind(console),
  warn: console.warn.bind(console),
  error: console.error.bind(console),
};
