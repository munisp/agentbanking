"""
Referral Program Workflow Implementation
Remittance Platform V11.0

This module implements the Referral Program Workflow for viral growth.

Author: Manus AI
Date: November 11, 2025
"""

from dataclasses import dataclass
from datetime import timedelta
from typing import Optional
from temporalio import workflow
from temporalio.common import RetryPolicy

# Import activities (will be implemented in activities_referral.py)
with workflow.unsafe.imports_passed_through():
    from activities_referral import (
        generate_referral_code,
        track_referral_attribution,
        validate_referral_eligibility,
        check_user_activation,
        calculate_referral_reward,
        credit_referral_reward,
        send_referral_notification,
        update_referral_analytics,
        detect_referral_fraud,
        generate_referral_qr_code,
        create_referral_deep_link,
    )


@dataclass
class ReferralCodeGenerationInput:
    """Input for referral code generation."""
    user_id: str
    user_type: str  # customer, agent


@dataclass
class ReferralSignupInput:
    """Input for referral signup event."""
    referral_code: str
    new_user_id: str
    new_user_type: str  # customer, agent
    signup_metadata: dict  # device_id, ip_address, etc.


@dataclass
class ReferralActivationInput:
    """Input for referral activation event."""
    referral_code: str
    new_user_id: str
    activation_transaction_id: str
    transaction_amount: float


@dataclass
class ReferralCodeGenerationOutput:
    """Output for referral code generation."""
    success: bool
    referral_code: str
    referral_qr_code_url: str
    referral_deep_link: str
    share_message: str


@dataclass
class ReferralRewardOutput:
    """Output for referral reward."""
    success: bool
    referral_id: str
    referrer_id: str
    new_user_id: str
    referrer_reward: float
    new_user_reward: float
    total_referrals: int
    next_bonus_at: int


# ============================================================================
# Workflow 1: Referral Code Generation Workflow
# ============================================================================

@workflow.defn(name="ReferralCodeGenerationWorkflow")
class ReferralCodeGenerationWorkflow:
    """
    Workflow for generating referral codes for users.
    
    Steps:
    1. Generate unique referral code
    2. Generate QR code image
    3. Create deep link for mobile app
    4. Store referral code in database
    5. Return referral assets to user
    
    Duration: < 5 seconds
    Success Rate: > 99%
    """
    
    @workflow.run
    async def run(self, input: ReferralCodeGenerationInput) -> ReferralCodeGenerationOutput:
        """Execute referral code generation workflow."""
        
        # Step 1: Generate unique referral code (8-character alphanumeric)
        referral_code = await workflow.execute_activity(
            generate_referral_code,
            args=[input.user_id, input.user_type],
            start_to_close_timeout=timedelta(seconds=5),
            retry_policy=RetryPolicy(
                maximum_attempts=3,
                initial_interval=timedelta(seconds=1),
                maximum_interval=timedelta(seconds=5),
            ),
        )
        
        # Step 2: Generate QR code image
        qr_code_url = await workflow.execute_activity(
            generate_referral_qr_code,
            args=[referral_code, input.user_id],
            start_to_close_timeout=timedelta(seconds=5),
            retry_policy=RetryPolicy(maximum_attempts=2),
        )
        
        # Step 3: Create deep link for mobile app install attribution
        deep_link = await workflow.execute_activity(
            create_referral_deep_link,
            args=[referral_code, input.user_type],
            start_to_close_timeout=timedelta(seconds=3),
            retry_policy=RetryPolicy(maximum_attempts=2),
        )
        
        # Step 4: Create share message
        if input.user_type == "agent":
            share_message = (
                f"Join me on Remittance Platform and earn ₦1,000! "
                f"Use my code {referral_code} when you sign up. "
                f"Download: {deep_link}"
            )
        else:
            share_message = (
                f"Get ₦500 free when you join Remittance Platform! "
                f"Use code {referral_code} at signup. "
                f"Download: {deep_link}"
            )
        
        return ReferralCodeGenerationOutput(
            success=True,
            referral_code=referral_code,
            referral_qr_code_url=qr_code_url,
            referral_deep_link=deep_link,
            share_message=share_message,
        )


# ============================================================================
# Workflow 2: Referral Signup Workflow
# ============================================================================

@workflow.defn(name="ReferralSignupWorkflow")
class ReferralSignupWorkflow:
    """
    Workflow for processing referral signup events.
    
    Steps:
    1. Validate referral code
    2. Detect fraud (self-referral, fake accounts)
    3. Track referral attribution
    4. Send signup notification to referrer
    5. Update referral analytics
    
    Duration: < 10 seconds
    Success Rate: > 95% (some fraud rejections expected)
    """
    
    @workflow.run
    async def run(self, input: ReferralSignupInput) -> dict:
        """Execute referral signup workflow."""
        
        # Step 1: Validate referral code exists and is active
        is_valid = await workflow.execute_activity(
            validate_referral_eligibility,
            args=[input.referral_code, input.new_user_id],
            start_to_close_timeout=timedelta(seconds=5),
            retry_policy=RetryPolicy(maximum_attempts=2),
        )
        
        if not is_valid:
            return {
                "success": False,
                "error": "Invalid or expired referral code",
            }
        
        # Step 2: Detect fraud (self-referral, fake accounts)
        fraud_result = await workflow.execute_activity(
            detect_referral_fraud,
            args=[input.referral_code, input.new_user_id, input.signup_metadata],
            start_to_close_timeout=timedelta(seconds=10),
            retry_policy=RetryPolicy(maximum_attempts=2),
        )
        
        if fraud_result["is_fraud"]:
            return {
                "success": False,
                "error": f"Fraud detected: {fraud_result['reason']}",
                "fraud_score": fraud_result["fraud_score"],
            }
        
        # Step 3: Track referral attribution
        referral_id = await workflow.execute_activity(
            track_referral_attribution,
            args=[input.referral_code, input.new_user_id, input.new_user_type],
            start_to_close_timeout=timedelta(seconds=5),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )
        
        # Step 4: Send signup notification to referrer
        await workflow.execute_activity(
            send_referral_notification,
            args=[
                referral_id,
                "signup",
                {"new_user_type": input.new_user_type},
            ],
            start_to_close_timeout=timedelta(seconds=5),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )
        
        # Step 5: Update referral analytics (best effort)
        await workflow.execute_activity(
            update_referral_analytics,
            args=[referral_id, "signup"],
            start_to_close_timeout=timedelta(seconds=5),
            retry_policy=RetryPolicy(maximum_attempts=2),
        )
        
        return {
            "success": True,
            "referral_id": referral_id,
            "message": "Referral signup tracked. Reward will be credited after first transaction.",
        }


# ============================================================================
# Workflow 3: Referral Activation & Reward Workflow
# ============================================================================

@workflow.defn(name="ReferralActivationWorkflow")
class ReferralActivationWorkflow:
    """
    Workflow for processing referral activation and crediting rewards.
    
    Steps:
    1. Validate activation transaction (minimum ₦1,000)
    2. Check activation window (30 days from signup)
    3. Calculate referral rewards (tiered)
    4. Credit reward to referrer
    5. Credit reward to new user
    6. Send reward notifications
    7. Update referral analytics
    8. Check for bonus eligibility (every 10 referrals)
    
    Duration: < 15 seconds
    Success Rate: > 99%
    """
    
    @workflow.run
    async def run(self, input: ReferralActivationInput) -> ReferralRewardOutput:
        """Execute referral activation workflow."""
        
        # Step 1: Check if user is activated (first transaction completed)
        activation_result = await workflow.execute_activity(
            check_user_activation,
            args=[
                input.new_user_id,
                input.activation_transaction_id,
                input.transaction_amount,
            ],
            start_to_close_timeout=timedelta(seconds=5),
            retry_policy=RetryPolicy(maximum_attempts=2),
        )
        
        if not activation_result["is_activated"]:
            return ReferralRewardOutput(
                success=False,
                referral_id="",
                referrer_id="",
                new_user_id=input.new_user_id,
                referrer_reward=0.0,
                new_user_reward=0.0,
                total_referrals=0,
                next_bonus_at=0,
            )
        
        referral_id = activation_result["referral_id"]
        referrer_id = activation_result["referrer_id"]
        new_user_type = activation_result["new_user_type"]
        
        # Step 2: Calculate referral rewards (tiered based on user type)
        reward_result = await workflow.execute_activity(
            calculate_referral_reward,
            args=[referrer_id, new_user_type],
            start_to_close_timeout=timedelta(seconds=5),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )
        
        referrer_reward = reward_result["referrer_reward"]
        new_user_reward = reward_result["new_user_reward"]
        bonus_reward = reward_result.get("bonus_reward", 0.0)
        
        # Step 3: Credit reward to referrer
        await workflow.execute_activity(
            credit_referral_reward,
            args=[
                referrer_id,
                referrer_reward + bonus_reward,
                referral_id,
                "referrer",
            ],
            start_to_close_timeout=timedelta(seconds=10),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )
        
        # Step 4: Credit reward to new user
        await workflow.execute_activity(
            credit_referral_reward,
            args=[input.new_user_id, new_user_reward, referral_id, "new_user"],
            start_to_close_timeout=timedelta(seconds=10),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )
        
        # Step 5: Send reward notifications
        await workflow.execute_activity(
            send_referral_notification,
            args=[
                referral_id,
                "activation",
                {
                    "referrer_reward": referrer_reward + bonus_reward,
                    "new_user_reward": new_user_reward,
                    "bonus_reward": bonus_reward,
                },
            ],
            start_to_close_timeout=timedelta(seconds=5),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )
        
        # Step 6: Update referral analytics
        analytics_result = await workflow.execute_activity(
            update_referral_analytics,
            args=[referral_id, "activation"],
            start_to_close_timeout=timedelta(seconds=5),
            retry_policy=RetryPolicy(maximum_attempts=2),
        )
        
        return ReferralRewardOutput(
            success=True,
            referral_id=referral_id,
            referrer_id=referrer_id,
            new_user_id=input.new_user_id,
            referrer_reward=referrer_reward + bonus_reward,
            new_user_reward=new_user_reward,
            total_referrals=analytics_result["total_referrals"],
            next_bonus_at=analytics_result["next_bonus_at"],
        )


# ============================================================================
# Workflow 4: Referral Leaderboard Update Workflow (Scheduled)
# ============================================================================

@workflow.defn(name="ReferralLeaderboardUpdateWorkflow")
class ReferralLeaderboardUpdateWorkflow:
    """
    Scheduled workflow for updating referral leaderboard.
    
    Runs every 5 minutes to update:
    - Top 10 referrers (all-time)
    - Top 10 referrers (monthly)
    - Referral badges (Champion, Elite, Rising Star)
    
    Duration: < 30 seconds
    Success Rate: > 99%
    """
    
    @workflow.run
    async def run(self) -> dict:
        """Execute referral leaderboard update workflow."""
        
        # This is a simple workflow that calls a single activity
        # The activity handles all the leaderboard computation
        from activities_referral import update_referral_leaderboard
        
        result = await workflow.execute_activity(
            update_referral_leaderboard,
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=2),
        )
        
        return {
            "success": True,
            "leaderboard_updated_at": result["updated_at"],
            "top_referrer": result["top_referrer"],
            "total_active_referrers": result["total_active_referrers"],
        }

