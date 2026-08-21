/**
 * useComposition — tracks IME composition state (CJK input methods) and
 * forwards composition/keyboard events to the caller's handlers.
 *
 * While an IME composition session is active, Enter key presses confirm the
 * composed text rather than submitting a form, so they are swallowed here.
 */

import * as React from "react";

export interface UseCompositionHandlers<T extends HTMLElement> {
  onKeyDown?: (e: React.KeyboardEvent<T>) => void;
  onCompositionStart?: (e: React.CompositionEvent<T>) => void;
  onCompositionEnd?: (e: React.CompositionEvent<T>) => void;
}

export function useComposition<T extends HTMLElement>(
  handlers: UseCompositionHandlers<T>
) {
  const isComposingRef = React.useRef(false);

  const onCompositionStart = (e: React.CompositionEvent<T>) => {
    isComposingRef.current = true;
    handlers.onCompositionStart?.(e);
  };

  const onCompositionEnd = (e: React.CompositionEvent<T>) => {
    isComposingRef.current = false;
    handlers.onCompositionEnd?.(e);
  };

  const onKeyDown = (e: React.KeyboardEvent<T>) => {
    const composing =
      isComposingRef.current || (e.nativeEvent as { isComposing?: boolean }).isComposing;
    if (composing && e.key === "Enter") {
      // Enter confirms the IME candidate; do not trigger submit handlers.
      return;
    }
    handlers.onKeyDown?.(e);
  };

  return { onCompositionStart, onCompositionEnd, onKeyDown };
}
