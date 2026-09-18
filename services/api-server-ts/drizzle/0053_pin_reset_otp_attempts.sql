-- Round-6 F9: OTP brute-force protection for PIN reset
-- Tracks failed verification attempts per OTP token so resetPin can lock a token
-- after a bounded number of guesses.
ALTER TABLE "otp_tokens" ADD COLUMN IF NOT EXISTS "attempts" integer DEFAULT 0 NOT NULL;
