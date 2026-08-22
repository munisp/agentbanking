/**
 * AIChatBox — presentational chat panel: message list, suggested prompts,
 * and a composer. The parent owns the message state and supplies
 * `onSendMessage`; this component renders and forwards user input.
 */

import * as React from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";
import { Loader2, Send } from "lucide-react";

export interface Message {
  role: "system" | "user" | "assistant";
  content: string;
}

export interface AIChatBoxProps {
  messages: Message[];
  onSendMessage: (content: string) => void;
  isLoading?: boolean;
  placeholder?: string;
  height?: string;
  emptyStateMessage?: string;
  suggestedPrompts?: string[];
  className?: string;
}

export function AIChatBox({
  messages,
  onSendMessage,
  isLoading = false,
  placeholder = "Type a message...",
  height = "400px",
  emptyStateMessage = "Start a conversation",
  suggestedPrompts,
  className,
}: AIChatBoxProps) {
  const [draft, setDraft] = React.useState("");
  const bottomRef = React.useRef<HTMLDivElement | null>(null);

  const visible = messages.filter(m => m.role !== "system");

  React.useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length, isLoading]);

  const submit = (content: string) => {
    const trimmed = content.trim();
    if (!trimmed || isLoading) return;
    onSendMessage(trimmed);
    setDraft("");
  };

  return (
    <div
      className={cn(
        "flex flex-col rounded-lg border border-border bg-card",
        className
      )}
      style={{ height }}
    >
      <ScrollArea className="flex-1 p-4">
        {visible.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center gap-4 text-center text-muted-foreground">
            <p>{emptyStateMessage}</p>
            {suggestedPrompts && suggestedPrompts.length > 0 && (
              <div className="flex flex-wrap justify-center gap-2">
                {suggestedPrompts.map(prompt => (
                  <Button
                    key={prompt}
                    variant="outline"
                    size="sm"
                    onClick={() => submit(prompt)}
                  >
                    {prompt}
                  </Button>
                ))}
              </div>
            )}
          </div>
        ) : (
          <div className="space-y-4">
            {visible.map((message, i) => (
              <div
                key={i}
                className={cn(
                  "max-w-[85%] whitespace-pre-wrap rounded-lg px-3 py-2 text-sm",
                  message.role === "user"
                    ? "ml-auto bg-primary text-primary-foreground"
                    : "mr-auto bg-muted text-foreground"
                )}
              >
                {message.content}
              </div>
            ))}
            {isLoading && (
              <div className="mr-auto flex items-center gap-2 rounded-lg bg-muted px-3 py-2 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" />
                Thinking…
              </div>
            )}
            <div ref={bottomRef} />
          </div>
        )}
      </ScrollArea>
      <form
        className="flex items-center gap-2 border-t border-border p-3"
        onSubmit={e => {
          e.preventDefault();
          submit(draft);
        }}
      >
        <Input
          value={draft}
          onChange={e => setDraft(e.target.value)}
          placeholder={placeholder}
          disabled={isLoading}
        />
        <Button type="submit" size="icon" disabled={isLoading || !draft.trim()}>
          <Send className="h-4 w-4" />
          <span className="sr-only">Send</span>
        </Button>
      </form>
    </div>
  );
}

export default AIChatBox;
