ALTER TYPE "public"."billing_audit_action" ADD VALUE 'invoice_generated';--> statement-breakpoint
ALTER TYPE "public"."billing_audit_action" ADD VALUE 'payment_recorded';--> statement-breakpoint
ALTER TYPE "public"."billing_audit_action" ADD VALUE 'subscription_created';--> statement-breakpoint
ALTER TYPE "public"."billing_audit_action" ADD VALUE 'subscription_updated';--> statement-breakpoint
ALTER TYPE "public"."billing_audit_action" ADD VALUE 'subscription_cancelled';--> statement-breakpoint
ALTER TYPE "public"."billing_audit_action" ADD VALUE 'credit_applied';--> statement-breakpoint
ALTER TYPE "public"."billing_audit_action" ADD VALUE 'refund_processed';--> statement-breakpoint
ALTER TYPE "public"."billing_audit_action" ADD VALUE 'late_fee_applied';--> statement-breakpoint
ALTER TYPE "public"."billing_audit_action" ADD VALUE 'usage_recorded';--> statement-breakpoint
ALTER TYPE "public"."billing_audit_action" ADD VALUE 'proration_applied';