"""
User Migration Script for Keycloak
Remittance Platform V11.0

Migrates existing users from the database to Keycloak.

Usage:
    python migrate_users_to_keycloak.py --dry-run
    python migrate_users_to_keycloak.py --batch-size 100
    python migrate_users_to_keycloak.py --role agent

Author: Manus AI
Date: November 11, 2025
"""

import os
import sys
import argparse
import logging
from typing import List, Dict, Optional
import asyncio
import asyncpg
import httpx
from datetime import datetime


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class KeycloakUserMigration:
    """Keycloak user migration handler."""
    
    def __init__(
        self,
        keycloak_url: str,
        realm: str,
        admin_username: str,
        admin_password: str,
        db_host: str,
        db_port: int,
        db_name: str,
        db_user: str,
        db_password: str
    ):
        """Initialize migration handler."""
        self.keycloak_url = keycloak_url
        self.realm = realm
        self.admin_username = admin_username
        self.admin_password = admin_password
        
        self.db_host = db_host
        self.db_port = db_port
        self.db_name = db_name
        self.db_user = db_user
        self.db_password = db_password
        
        self.admin_token = None
        self.db_pool = None
        
        # URLs
        self.token_url = f"{keycloak_url}/realms/master/protocol/openid-connect/token"
        self.users_url = f"{keycloak_url}/admin/realms/{realm}/users"
    
    async def connect_db(self):
        """Connect to PostgreSQL database."""
        logger.info(f"Connecting to database: {self.db_host}:{self.db_port}/{self.db_name}")
        
        self.db_pool = await asyncpg.create_pool(
            host=self.db_host,
            port=self.db_port,
            database=self.db_name,
            user=self.db_user,
            password=self.db_password,
            min_size=1,
            max_size=10
        )
        
        logger.info("Database connection established")
    
    async def close_db(self):
        """Close database connection."""
        if self.db_pool:
            await self.db_pool.close()
            logger.info("Database connection closed")
    
    async def get_admin_token(self):
        """Get admin access token from Keycloak."""
        logger.info("Obtaining admin access token...")
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.token_url,
                data={
                    "client_id": "admin-cli",
                    "username": self.admin_username,
                    "password": self.admin_password,
                    "grant_type": "password"
                }
            )
            
            if response.status_code != 200:
                raise Exception(f"Failed to get admin token: {response.text}")
            
            data = response.json()
            self.admin_token = data["access_token"]
            logger.info("Admin token obtained successfully")
    
    async def fetch_users_from_db(
        self,
        role_filter: Optional[str] = None,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[Dict]:
        """
        Fetch users from database.
        
        Args:
            role_filter: Filter by role (agent, super_agent, admin, customer)
            limit: Maximum number of users to fetch
            offset: Offset for pagination
            
        Returns:
            List of user dictionaries
        """
        logger.info(f"Fetching users from database (role={role_filter}, limit={limit}, offset={offset})")
        
        query = """
            SELECT 
                id,
                username,
                email,
                first_name,
                last_name,
                phone_number,
                role,
                is_active,
                email_verified,
                created_at
            FROM users
            WHERE 1=1
        """
        
        params = []
        param_count = 1
        
        if role_filter:
            query += f" AND role = ${param_count}"
            params.append(role_filter)
            param_count += 1
        
        query += " ORDER BY created_at ASC"
        
        if limit:
            query += f" LIMIT ${param_count}"
            params.append(limit)
            param_count += 1
        
        if offset:
            query += f" OFFSET ${param_count}"
            params.append(offset)
        
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
        
        users = [dict(row) for row in rows]
        logger.info(f"Fetched {len(users)} users from database")
        
        return users
    
    async def create_user_in_keycloak(self, user: Dict, dry_run: bool = False) -> bool:
        """
        Create user in Keycloak.
        
        Args:
            user: User dictionary from database
            dry_run: If True, don't actually create user
            
        Returns:
            True if successful, False otherwise
        """
        keycloak_user = {
            "username": user["username"],
            "email": user["email"],
            "firstName": user.get("first_name"),
            "lastName": user.get("last_name"),
            "enabled": user.get("is_active", True),
            "emailVerified": user.get("email_verified", False),
            "attributes": {
                "phone_number": [user.get("phone_number", "")],
                "migrated_from_db": ["true"],
                "original_user_id": [str(user["id"])],
                "migration_date": [datetime.utcnow().isoformat()]
            },
            "realmRoles": [user.get("role", "customer")],
            "credentials": [
                {
                    "type": "password",
                    "value": "ChangeMe123!",  # Temporary password
                    "temporary": True  # Force password reset on first login
                }
            ]
        }
        
        if dry_run:
            logger.info(f"[DRY RUN] Would create user: {user['username']} ({user['email']})")
            return True
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.users_url,
                    json=keycloak_user,
                    headers={"Authorization": f"Bearer {self.admin_token}"}
                )
                
                if response.status_code == 201:
                    logger.info(f"✅ Created user: {user['username']} ({user['email']})")
                    return True
                elif response.status_code == 409:
                    logger.warning(f"⚠️  User already exists: {user['username']}")
                    return False
                else:
                    logger.error(f"❌ Failed to create user {user['username']}: {response.status_code} - {response.text}")
                    return False
        
        except Exception as e:
            logger.error(f"❌ Error creating user {user['username']}: {e}")
            return False
    
    async def migrate_users(
        self,
        role_filter: Optional[str] = None,
        batch_size: int = 100,
        dry_run: bool = False
    ):
        """
        Migrate users from database to Keycloak.
        
        Args:
            role_filter: Filter by role
            batch_size: Number of users to process per batch
            dry_run: If True, don't actually create users
        """
        logger.info("=" * 80)
        logger.info("User Migration to Keycloak")
        logger.info("=" * 80)
        logger.info(f"Keycloak URL: {self.keycloak_url}")
        logger.info(f"Realm: {self.realm}")
        logger.info(f"Role Filter: {role_filter or 'All'}")
        logger.info(f"Batch Size: {batch_size}")
        logger.info(f"Dry Run: {dry_run}")
        logger.info("=" * 80)
        
        # Connect to database
        await self.connect_db()
        
        # Get admin token
        await self.get_admin_token()
        
        # Fetch total count
        async with self.db_pool.acquire() as conn:
            if role_filter:
                total_count = await conn.fetchval(
                    "SELECT COUNT(*) FROM users WHERE role = $1",
                    role_filter
                )
            else:
                total_count = await conn.fetchval("SELECT COUNT(*) FROM users")
        
        logger.info(f"Total users to migrate: {total_count}")
        
        # Process in batches
        offset = 0
        success_count = 0
        failure_count = 0
        skipped_count = 0
        
        while offset < total_count:
            logger.info(f"\nProcessing batch: {offset + 1} to {min(offset + batch_size, total_count)}")
            
            # Fetch batch
            users = await self.fetch_users_from_db(
                role_filter=role_filter,
                limit=batch_size,
                offset=offset
            )
            
            # Process each user
            for user in users:
                result = await self.create_user_in_keycloak(user, dry_run=dry_run)
                
                if result:
                    success_count += 1
                else:
                    failure_count += 1
                
                # Small delay to avoid rate limiting
                await asyncio.sleep(0.1)
            
            offset += batch_size
        
        # Summary
        logger.info("\n" + "=" * 80)
        logger.info("Migration Summary")
        logger.info("=" * 80)
        logger.info(f"Total Users: {total_count}")
        logger.info(f"Successfully Created: {success_count}")
        logger.info(f"Failed: {failure_count}")
        logger.info("=" * 80)
        
        # Close database connection
        await self.close_db()


async def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Migrate users from database to Keycloak")
    
    parser.add_argument(
        "--keycloak-url",
        default=os.getenv("KEYCLOAK_URL", "http://localhost:8080"),
        help="Keycloak server URL"
    )
    parser.add_argument(
        "--realm",
        default=os.getenv("KEYCLOAK_REALM", "remittance"),
        help="Keycloak realm name"
    )
    parser.add_argument(
        "--admin-username",
        default=os.getenv("KEYCLOAK_ADMIN_USERNAME", "admin"),
        help="Keycloak admin username"
    )
    parser.add_argument(
        "--admin-password",
        default=os.getenv("KEYCLOAK_ADMIN_PASSWORD"),
        help="Keycloak admin password"
    )
    parser.add_argument(
        "--db-host",
        default=os.getenv("DB_HOST", "localhost"),
        help="Database host"
    )
    parser.add_argument(
        "--db-port",
        type=int,
        default=int(os.getenv("DB_PORT", "5432")),
        help="Database port"
    )
    parser.add_argument(
        "--db-name",
        default=os.getenv("DB_NAME", "remittance"),
        help="Database name"
    )
    parser.add_argument(
        "--db-user",
        default=os.getenv("DB_USER", "postgres"),
        help="Database user"
    )
    parser.add_argument(
        "--db-password",
        default=os.getenv("DB_PASSWORD"),
        help="Database password"
    )
    parser.add_argument(
        "--role",
        choices=["agent", "super_agent", "admin", "customer"],
        help="Filter by role"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Number of users to process per batch"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Perform a dry run without actually creating users"
    )
    
    args = parser.parse_args()
    
    # Validate required arguments
    if not args.admin_password:
        logger.error("Admin password is required (--admin-password or KEYCLOAK_ADMIN_PASSWORD)")
        sys.exit(1)
    
    if not args.db_password:
        logger.error("Database password is required (--db-password or DB_PASSWORD)")
        sys.exit(1)
    
    # Create migration handler
    migration = KeycloakUserMigration(
        keycloak_url=args.keycloak_url,
        realm=args.realm,
        admin_username=args.admin_username,
        admin_password=args.admin_password,
        db_host=args.db_host,
        db_port=args.db_port,
        db_name=args.db_name,
        db_user=args.db_user,
        db_password=args.db_password
    )
    
    # Run migration
    await migration.migrate_users(
        role_filter=args.role,
        batch_size=args.batch_size,
        dry_run=args.dry_run
    )


if __name__ == "__main__":
    asyncio.run(main())

