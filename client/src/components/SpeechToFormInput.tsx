/**
 * Speech-to-Form Auto-fill
 * Agent speaks "cash in five thousand for 08012345678"
 * and form fields populate automatically.
 * Uses Web Speech API with Nigerian English/Pidgin recognition.
 */
import { useState, useCallback, useRef } from "react";
import { Mic, MicOff, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";

interface ParsedCommand {
  type?: "cash_in" | "cash_out" | "transfer" | "airtime" | "bills";
  amount?: number;
  phone?: string;
  recipient?: string;
}

interface SpeechToFormProps {
  onParsed: (command: ParsedCommand) => void;
  className?: string;
}

export function SpeechToFormInput({ onParsed, className }: SpeechToFormProps) {
  const [listening, setListening] = useState(false);
  const [transcript, setTranscript] = useState("");
  const [processing, setProcessing] = useState(false);
  const recognitionRef = useRef<any>(null);

  const startListening = useCallback(() => {
    if (
      !("webkitSpeechRecognition" in window) &&
      !("SpeechRecognition" in window)
    ) {
      return;
    }

    const SpeechRecognition =
      (window as any).SpeechRecognition ||
      (window as any).webkitSpeechRecognition;
    const recognition = new SpeechRecognition();
    recognitionRef.current = recognition;

    recognition.lang = "en-NG"; // Nigerian English
    recognition.continuous = false;
    recognition.interimResults = true;

    recognition.onstart = () => setListening(true);
    recognition.onend = () => setListening(false);

    recognition.onresult = (event: any) => {
      const result = event.results[event.results.length - 1];
      const text = result[0].transcript;
      setTranscript(text);

      if (result.isFinal) {
        setProcessing(true);
        const parsed = parseVoiceCommand(text);
        onParsed(parsed);
        setProcessing(false);
      }
    };

    recognition.onerror = () => {
      setListening(false);
    };

    recognition.start();
  }, [onParsed]);

  const stopListening = useCallback(() => {
    if (recognitionRef.current) {
      recognitionRef.current.stop();
    }
    setListening(false);
  }, []);

  return (
    <div className={`flex items-center gap-2 ${className || ""}`}>
      <Button
        type="button"
        variant={listening ? "destructive" : "outline"}
        size="icon"
        onClick={listening ? stopListening : startListening}
        className="shrink-0"
      >
        {processing ? (
          <Loader2 className="w-4 h-4 animate-spin" />
        ) : listening ? (
          <MicOff className="w-4 h-4" />
        ) : (
          <Mic className="w-4 h-4" />
        )}
      </Button>
      {transcript && (
        <span className="text-sm text-muted-foreground truncate italic">
          &ldquo;{transcript}&rdquo;
        </span>
      )}
    </div>
  );
}

// ── Voice Command Parser ────────────────────────────────────────────────────

function parseVoiceCommand(text: string): ParsedCommand {
  const lower = text.toLowerCase();
  const result: ParsedCommand = {};

  // Detect transaction type
  if (
    lower.includes("cash in") ||
    lower.includes("deposit") ||
    lower.includes("put money")
  ) {
    result.type = "cash_in";
  } else if (
    lower.includes("cash out") ||
    lower.includes("withdraw") ||
    lower.includes("collect money")
  ) {
    result.type = "cash_out";
  } else if (lower.includes("transfer") || lower.includes("send")) {
    result.type = "transfer";
  } else if (lower.includes("airtime") || lower.includes("recharge")) {
    result.type = "airtime";
  } else if (lower.includes("bill") || lower.includes("pay")) {
    result.type = "bills";
  }

  // Extract amount (handles "five thousand", "5000", "5k", etc.)
  const amountPatterns = [
    /(\d[\d,]*)\s*(naira|ngn)?/i,
    /(\d+)k\b/i,
    /(\d+)\s*thousand/i,
    /(\d+)\s*million/i,
  ];

  for (const pattern of amountPatterns) {
    const match = lower.match(pattern);
    if (match) {
      let amount = parseInt(match[1].replace(/,/g, ""), 10);
      if (lower.includes("k") || lower.includes("thousand")) amount *= 1000;
      if (lower.includes("million")) amount *= 1000000;
      result.amount = amount;
      break;
    }
  }

  // Word-to-number mapping for spoken amounts
  if (!result.amount) {
    const wordAmounts: Record<string, number> = {
      "one thousand": 1000,
      "two thousand": 2000,
      "three thousand": 3000,
      "four thousand": 4000,
      "five thousand": 5000,
      "six thousand": 6000,
      "seven thousand": 7000,
      "eight thousand": 8000,
      "nine thousand": 9000,
      "ten thousand": 10000,
      "twenty thousand": 20000,
      "fifty thousand": 50000,
      "hundred thousand": 100000,
      "one million": 1000000,
      "five hundred": 500,
      "one hundred": 100,
      "two hundred": 200,
    };
    for (const [word, value] of Object.entries(wordAmounts)) {
      if (lower.includes(word)) {
        result.amount = value;
        break;
      }
    }
  }

  // Extract phone number (Nigerian format)
  const phoneMatch = text.match(/0[789]\d{9}/);
  if (phoneMatch) {
    result.phone = phoneMatch[0];
  }

  // Alternative phone formats: "zero eight zero one two three..."
  if (!result.phone) {
    const spokenPhone = lower.match(
      /(?:zero|oh)\s*(?:eight|seven|nine)\s*(?:zero|one|two|three|four|five|six|seven|eight|nine|\s)*/
    );
    if (spokenPhone) {
      const digitWords: Record<string, string> = {
        zero: "0",
        oh: "0",
        one: "1",
        two: "2",
        three: "3",
        four: "4",
        five: "5",
        six: "6",
        seven: "7",
        eight: "8",
        nine: "9",
      };
      const digits = spokenPhone[0]
        .split(/\s+/)
        .map(w => digitWords[w] || "")
        .join("");
      if (digits.length >= 10) {
        result.phone = digits.slice(0, 11);
      }
    }
  }

  return result;
}
