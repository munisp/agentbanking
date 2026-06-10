"""
Referral Program Activity Implementations
Remittance Platform V11.0

This module implements all activities for the Referral Program Workflow.

Author: Manus AI
Date: November 11, 2025
"""

import hashlib
import random
import string
from datetime import datetime, timedelta
from typing import Dict, Optional
from temporalio import activity
import asyncpg
import redis
import qrcode
import io
import base64

# Database and cache connections (injected via dependency injection)
db_pool: Optional[asyncpg.Pool] = None
redis_client: Optional[redis.Redis] = None


# ============================================================================
# Activity 1: Generate Referral Code
# ============================================================================

@activity.defn(name="generate_referral_code")
async def generate_referral_code(user_id: str, user_type: str) -> str:
    """
    Generate a unique 8-character alphanumeric referral code.
    
    Args:
        user_id: ID of the user requesting referral code
        user_type: Type of user (customer, agent)
    
    Returns:
        Unique referral code (e.g., "ABC12XYZ")
    """
    # Generate random 8-character code
    while True:
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        
        # Check if code already exists
        async with db_pool.acquire() as conn:
            existing = await conn.fetchval(
                "SELECT id FROM referral_codes WHERE referral_code = $1",
                code
            )
            
            if not existing:
                # Insert new referral code
                await conn.execute(
                    """
                    INSERT INTO referral_codes 
                    (id, user_id, user_type, referral_code, created_at, expires_at)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    """,
                    f"ref-{user_id}-{datetime.utcnow().timestamp()}",
                    user_id,
                    user_type,
                    code,
                    datetime.utcnow(),
                    datetime.utcnow() + timedelta(days=365),  # 1 year expiry
                )
                
                activity.logger.info(f"Generated referral code {code} for user {user_id}")
                return code


# ============================================================================
# Activity 2: Generate Referral QR Code
# ============================================================================

@activity.defn(name="generate_referral_qr_code")
async def generate_referral_qr_code(referral_code: str, user_id: str) -> str:
    """
    Generate QR code image for referral code.
    
    Args:
        referral_code: The referral code to encode
        user_id: ID of the user (for file naming)
    
    Returns:
        URL to QR code image
    """
    # Create QR code
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr_data = f"https://remittance.app/signup?ref={referral_code}"
    qr.add_data(qr_data)
    qr.make(fit=True)
    
    # Generate image
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Convert to base64 (in production, upload to S3)
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    img_base64 = base64.b64encode(buffer.getvalue()).decode()
    
    # In production: upload to S3 and return URL
    # For now, return data URL
    qr_code_url = f"data:image/png;base64,{img_base64}"
    
    activity.logger.info(f"Generated QR code for referral {referral_code}")
    return qr_code_url


# ============================================================================
# Activity 3: Create Referral Deep Link
# ============================================================================

@activity.defn(name="create_referral_deep_link")
async def create_referral_deep_link(referral_code: str, user_type: str) -> str:
    """
    Create deep link for mobile app install attribution.
    
    Args:
        referral_code: The referral code
        user_type: Type of user (customer, agent)
    
    Returns:
        Deep link URL
    """
    # In production: use Branch.io or Firebase Dynamic Links
    # For now, return simple deep link
    base_url = "https://remittance.app"
    deep_link = f"{base_url}/signup?ref={referral_code}&type={user_type}"
    
    activity.logger.info(f"Created deep link for referral {referral_code}")
    return deep_link


# ============================================================================
# Activity 4: Validate Referral Eligibility
# ============================================================================

@activity.defn(name="validate_referral_eligibility")
async def validate_referral_eligibility(referral_code: str, new_user_id: str) -> bool:
    """
    Validate that referral code is valid and eligible for use.
    
    Args:
        referral_code: The referral code to validate
        new_user_id: ID of the new user signing up
    
    Returns:
        True if valid, False otherwise
    """
    async with db_pool.acquire() as conn:
        # Check if referral code exists and is not expired
        referral = await conn.fetchrow(
            """
            SELECT id, user_id, expires_at 
            FROM referral_codes 
            WHERE referral_code = $1
            """,
            referral_code
        )
        
        if not referral:
            activity.logger.warning(f"Referral code {referral_code} not found")
            return False
        
        if referral['expires_at'] < datetime.utcnow():
            activity.logger.warning(f"Referral code {referral_code} expired")
            return False
        
        # Check if user is not referring themselves
        if referral['user_id'] == new_user_id:
            activity.logger.warning(f"Self-referral detected for user {new_user_id}")
            return False
        
        activity.logger.info(f"Referral code {referral_code} is valid")
        return True


# ============================================================================
# Activity 5: Detect Referral Fraud
# ============================================================================

@activity.defn(name="detect_referral_fraud")
async def detect_referral_fraud(
    referral_code: str,
    new_user_id: str,
    signup_metadata: dict
) -> Dict:
    """
    Detect fraudulent referral signups using ML-based scoring.
    
    Args:
        referral_code: The referral code used
        new_user_id: ID of the new user
        signup_metadata: Metadata about signup (device_id, ip_address, etc.)
    
    Returns:
        Fraud detection result with score and reason
    """
    fraud_score = 0.0
    fraud_reasons = []
    
    async with db_pool.acquire() as conn:
        # Get referrer info
        referrer = await conn.fetchrow(
            """
            SELECT user_id FROM referral_codes WHERE referral_code = $1
            """,
            referral_code
        )
        
        if not referrer:
            return {"is_fraud": True, "fraud_score": 1.0, "reason": "Invalid referral code"}
        
        referrer_id = referrer['user_id']
        
        # Check 1: Same device ID
        if signup_metadata.get('device_id'):
            same_device = await conn.fetchval(
                """
                SELECT COUNT(*) FROM user_devices 
                WHERE user_id = $1 AND device_id = $2
                """,
                referrer_id,
                signup_metadata['device_id']
            )
            if same_device > 0:
                fraud_score += 0.5
                fraud_reasons.append("Same device as referrer")
        
        # Check 2: Same IP address
        if signup_metadata.get('ip_address'):
            same_ip = await conn.fetchval(
                """
                SELECT COUNT(*) FROM user_sessions 
                WHERE user_id = $1 AND ip_address = $2 
                AND created_at > NOW() - INTERVAL '7 days'
                """,
                referrer_id,
                signup_metadata['ip_address']
            )
            if same_ip > 0:
                fraud_score += 0.3
                fraud_reasons.append("Same IP as referrer (last 7 days)")
        
        # Check 3: Referral velocity (too many referrals too quickly)
        referral_count_today = await conn.fetchval(
            """
            SELECT COUNT(*) FROM referral_events 
            WHERE referrer_id = $1 
            AND event_type = 'signed_up'
            AND event_timestamp > NOW() - INTERVAL '1 day'
            """,
            referrer_id
        )
        
        if referral_count_today > 10:
            fraud_score += 0.2
            fraud_reasons.append(f"High referral velocity ({referral_count_today} today)")
        
        # Check 4: Duplicate phone number
        if signup_metadata.get('phone_number'):
            duplicate_phone = await conn.fetchval(
                """
                SELECT COUNT(*) FROM users 
                WHERE phone_number = $1 AND id != $2
                """,
                signup_metadata['phone_number'],
                new_user_id
            )
            if duplicate_phone > 0:
                fraud_score += 0.4
                fraud_reasons.append("Duplicate phone number")
    
    is_fraud = fraud_score >= 0.7  # Threshold for fraud
    
    if is_fraud:
        activity.logger.warning(
            f"Fraud detected for referral {referral_code}: {', '.join(fraud_reasons)}"
        )
    
    return {
        "is_fraud": is_fraud,
        "fraud_score": fraud_score,
        "reason": ", ".join(fraud_reasons) if fraud_reasons else "No fraud detected"
    }


# ============================================================================
# Activity 6: Track Referral Attribution
# ============================================================================

@activity.defn(name="track_referral_attribution")
async def track_referral_attribution(
    referral_code: str,
    new_user_id: str,
    new_user_type: str
) -> str:
    """
    Track referral attribution in database.
    
    Args:
        referral_code: The referral code used
        new_user_id: ID of the new user
        new_user_type: Type of new user (customer, agent)
    
    Returns:
        Referral event ID
    """
    async with db_pool.acquire() as conn:
        # Get referrer ID
        referrer = await conn.fetchrow(
            "SELECT user_id FROM referral_codes WHERE referral_code = $1",
            referral_code
        )
        
        referrer_id = referrer['user_id']
        
        # Insert referral event
        referral_id = f"ref-event-{new_user_id}-{datetime.utcnow().timestamp()}"
        
        await conn.execute(
            """
            INSERT INTO referral_events 
            (id, referrer_id, referral_code, new_user_id, new_user_type, 
             event_type, event_timestamp, reward_amount, reward_credited)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            """,
            referral_id,
            referrer_id,
            referral_code,
            new_user_id,
            new_user_type,
            "signed_up",
            datetime.utcnow(),
            0.0,  # Reward calculated later
            False
        )
        
        activity.logger.info(f"Tracked referral attribution: {referral_id}")
        return referral_id


# ============================================================================
# Activity 7: Check User Activation
# ============================================================================

@activity.defn(name="check_user_activation")
async def check_user_activation(
    new_user_id: str,
    activation_transaction_id: str,
    transaction_amount: float
) -> Dict:
    """
    Check if user has completed activation (first transaction).
    
    Args:
        new_user_id: ID of the new user
        activation_transaction_id: ID of the activation transaction
        transaction_amount: Amount of the transaction
    
    Returns:
        Activation result with referral info
    """
    # Minimum transaction amount for activation
    MIN_ACTIVATION_AMOUNT = 1000.0
    
    if transaction_amount < MIN_ACTIVATION_AMOUNT:
        activity.logger.info(
            f"Transaction amount {transaction_amount} below minimum {MIN_ACTIVATION_AMOUNT}"
        )
        return {"is_activated": False}
    
    async with db_pool.acquire() as conn:
        # Get referral event for this user
        referral = await conn.fetchrow(
            """
            SELECT id, referrer_id, new_user_type, event_timestamp
            FROM referral_events 
            WHERE new_user_id = $1 AND event_type = 'signed_up'
            ORDER BY event_timestamp DESC
            LIMIT 1
            """,
            new_user_id
        )
        
        if not referral:
            activity.logger.warning(f"No referral found for user {new_user_id}")
            return {"is_activated": False}
        
        # Check activation window (30 days)
        signup_time = referral['event_timestamp']
        if datetime.utcnow() - signup_time > timedelta(days=30):
            activity.logger.warning(f"Activation window expired for user {new_user_id}")
            return {"is_activated": False}
        
        # Check if already activated
        already_activated = await conn.fetchval(
            """
            SELECT COUNT(*) FROM referral_events 
            WHERE new_user_id = $1 AND event_type = 'activated'
            """,
            new_user_id
        )
        
        if already_activated > 0:
            activity.logger.info(f"User {new_user_id} already activated")
            return {"is_activated": False}
        
        # Mark as activated
        await conn.execute(
            """
            INSERT INTO referral_events 
            (id, referrer_id, referral_code, new_user_id, new_user_type,
             event_type, event_timestamp, reward_amount, reward_credited)
            SELECT 
                $1, referrer_id, referral_code, new_user_id, new_user_type,
                'activated', NOW(), 0.0, FALSE
            FROM referral_events
            WHERE id = $2
            """,
            f"ref-activation-{new_user_id}-{datetime.utcnow().timestamp()}",
            referral['id']
        )
        
        activity.logger.info(f"User {new_user_id} activated successfully")
        return {
            "is_activated": True,
            "referral_id": referral['id'],
            "referrer_id": referral['referrer_id'],
            "new_user_type": referral['new_user_type']
        }


# ============================================================================
# Activity 8: Calculate Referral Reward
# ============================================================================

@activity.defn(name="calculate_referral_reward")
async def calculate_referral_reward(referrer_id: str, new_user_type: str) -> Dict:
    """
    Calculate referral rewards based on user type and bonus tiers.
    
    Args:
        referrer_id: ID of the referrer
        new_user_type: Type of new user (customer, agent)
    
    Returns:
        Reward amounts for referrer and new user
    """
    # Base rewards
    if new_user_type == "agent":
        referrer_reward = 2000.0  # ₦2,000 for agent referral
        new_user_reward = 1000.0  # ₦1,000 for new agent
    else:
        referrer_reward = 500.0   # ₦500 for customer referral
        new_user_reward = 500.0   # ₦500 for new customer
    
    # Check for bonus (every 10 successful referrals)
    async with db_pool.acquire() as conn:
        activated_count = await conn.fetchval(
            """
            SELECT COUNT(*) FROM referral_events 
            WHERE referrer_id = $1 AND event_type = 'activated'
            """,
            referrer_id
        )
        
        bonus_reward = 0.0
        if (activated_count + 1) % 10 == 0:
            bonus_reward = 1000.0  # ₦1,000 bonus for every 10 referrals
            activity.logger.info(f"Bonus reward triggered for referrer {referrer_id}")
    
    return {
        "referrer_reward": referrer_reward,
        "new_user_reward": new_user_reward,
        "bonus_reward": bonus_reward,
        "total_referrer_reward": referrer_reward + bonus_reward
    }


# ============================================================================
# Activity 9: Credit Referral Reward
# ============================================================================

@activity.defn(name="credit_referral_reward")
async def credit_referral_reward(
    user_id: str,
    reward_amount: float,
    referral_id: str,
    reward_type: str
) -> bool:
    """
    Credit referral reward to user's account.
    
    Args:
        user_id: ID of the user to credit
        reward_amount: Amount to credit
        referral_id: ID of the referral event
        reward_type: Type of reward (referrer, new_user)
    
    Returns:
        True if successful
    """
    async with db_pool.acquire() as conn:
        # Credit to user's wallet (in production: integrate with TigerBeetle ledger)
        await conn.execute(
            """
            UPDATE user_wallets 
            SET balance = balance + $1,
                updated_at = NOW()
            WHERE user_id = $2
            """,
            reward_amount,
            user_id
        )
        
        # Record transaction
        await conn.execute(
            """
            INSERT INTO transactions 
            (id, user_id, type, amount, description, created_at)
            VALUES ($1, $2, $3, $4, $5, $6)
            """,
            f"txn-referral-{user_id}-{datetime.utcnow().timestamp()}",
            user_id,
            "referral_reward",
            reward_amount,
            f"Referral reward ({reward_type})",
            datetime.utcnow()
        )
        
        # Update referral event
        await conn.execute(
            """
            UPDATE referral_events 
            SET reward_amount = $1, reward_credited = TRUE
            WHERE id = $2
            """,
            reward_amount,
            referral_id
        )
        
        activity.logger.info(f"Credited ₦{reward_amount} to user {user_id}")
        return True


# ============================================================================
# Activity 10: Send Referral Notification
# ============================================================================

@activity.defn(name="send_referral_notification")
async def send_referral_notification(
    referral_id: str,
    event_type: str,
    metadata: dict
) -> bool:
    """
    Send notification about referral event.
    
    Args:
        referral_id: ID of the referral event
        event_type: Type of event (signup, activation)
        metadata: Additional metadata
    
    Returns:
        True if successful
    """
    async with db_pool.acquire() as conn:
        # Get referral info
        referral = await conn.fetchrow(
            """
            SELECT referrer_id, new_user_id, new_user_type
            FROM referral_events 
            WHERE id = $1
            """,
            referral_id
        )
        
        if not referral:
            return False
        
        # Send notification to referrer
        if event_type == "signup":
            message = f"Good news! Someone signed up using your referral code. They'll need to complete their first transaction for you to earn your reward."
        elif event_type == "activation":
            referrer_reward = metadata.get('referrer_reward', 0)
            message = f"Congratulations! You've earned ₦{referrer_reward} from a successful referral. The reward has been credited to your account."
        
        # In production: integrate with notification service
        activity.logger.info(f"Notification sent for referral {referral_id}: {message}")
        
        return True


# ============================================================================
# Activity 11: Update Referral Analytics
# ============================================================================

@activity.defn(name="update_referral_analytics")
async def update_referral_analytics(referral_id: str, event_type: str) -> Dict:
    """
    Update referral analytics for leaderboard and reporting.
    
    Args:
        referral_id: ID of the referral event
        event_type: Type of event (signup, activation)
    
    Returns:
        Updated analytics
    """
    async with db_pool.acquire() as conn:
        # Get referrer ID
        referrer_id = await conn.fetchval(
            "SELECT referrer_id FROM referral_events WHERE id = $1",
            referral_id
        )
        
        # Update analytics
        if event_type == "signup":
            await conn.execute(
                """
                INSERT INTO referral_analytics 
                (user_id, total_referrals, activated_referrals, total_rewards_earned, last_referral_at)
                VALUES ($1, 1, 0, 0, NOW())
                ON CONFLICT (user_id) DO UPDATE SET
                    total_referrals = referral_analytics.total_referrals + 1,
                    last_referral_at = NOW()
                """,
                referrer_id
            )
        elif event_type == "activation":
            reward_amount = await conn.fetchval(
                "SELECT reward_amount FROM referral_events WHERE id = $1",
                referral_id
            )
            
            await conn.execute(
                """
                UPDATE referral_analytics SET
                    activated_referrals = activated_referrals + 1,
                    total_rewards_earned = total_rewards_earned + $1
                WHERE user_id = $2
                """,
                reward_amount,
                referrer_id
            )
        
        # Get updated analytics
        analytics = await conn.fetchrow(
            """
            SELECT total_referrals, activated_referrals, total_rewards_earned
            FROM referral_analytics WHERE user_id = $1
            """,
            referrer_id
        )
        
        next_bonus_at = ((analytics['activated_referrals'] // 10) + 1) * 10
        
        return {
            "total_referrals": analytics['total_referrals'],
            "activated_referrals": analytics['activated_referrals'],
            "next_bonus_at": next_bonus_at
        }


# ============================================================================
# Activity 12: Update Referral Leaderboard
# ============================================================================

@activity.defn(name="update_referral_leaderboard")
async def update_referral_leaderboard() -> Dict:
    """
    Update referral leaderboard (scheduled task).
    
    Returns:
        Leaderboard update result
    """
    async with db_pool.acquire() as conn:
        # Get top 10 referrers (all-time)
        top_referrers = await conn.fetch(
            """
            SELECT user_id, total_referrals, activated_referrals, total_rewards_earned
            FROM referral_analytics
            ORDER BY activated_referrals DESC, total_referrals DESC
            LIMIT 10
            """
        )
        
        # Assign badges
        badges = ["🥇 Champion", "🥈 Elite", "🥉 Rising Star"]
        for i, referrer in enumerate(top_referrers[:3]):
            await conn.execute(
                """
                UPDATE users SET referral_badge = $1 WHERE id = $2
                """,
                badges[i],
                referrer['user_id']
            )
        
        # Cache leaderboard in Redis
        if redis_client:
            leaderboard_data = [
                {
                    "user_id": r['user_id'],
                    "total_referrals": r['total_referrals'],
                    "activated_referrals": r['activated_referrals'],
                    "total_rewards": float(r['total_rewards_earned'])
                }
                for r in top_referrers
            ]
            redis_client.setex(
                "referral:leaderboard:all_time",
                300,  # 5 minutes TTL
                str(leaderboard_data)
            )
        
        activity.logger.info("Referral leaderboard updated")
        
        return {
            "updated_at": datetime.utcnow().isoformat(),
            "top_referrer": top_referrers[0]['user_id'] if top_referrers else None,
            "total_active_referrers": len(top_referrers)
        }
