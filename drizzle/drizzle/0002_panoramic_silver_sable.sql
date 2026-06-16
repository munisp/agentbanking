CREATE TABLE "otp_tokens" (
	"id" serial PRIMARY KEY NOT NULL,
	"agentId" integer NOT NULL,
	"hashedOtp" varchar(128) NOT NULL,
	"expiresAt" timestamp NOT NULL,
	"used" boolean DEFAULT false NOT NULL,
	"createdAt" timestamp DEFAULT now() NOT NULL
);
