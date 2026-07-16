"""
Seed data for Realtime Notification Service
Creates sample agents, businesses, geofences, and violations for testing
"""

import os
import uuid
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import random
from dotenv import load_dotenv

# Load .env file first
load_dotenv()

# Add main.py models to path
from main import (
    POSDeviceLocation,
    POSGeofence,
    GeofenceViolation,
    TransactionNotification,
)

# Database setup
DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://postgres:password@localhost:5432/link_core_banking"
)
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Sample tenant - use bpmgd as tenant
SAMPLE_TENANT = "bpmgd"

# Nigerian first names
FIRST_NAMES = [
    "Chioma",
    "Ibrahim",
    "Ngozi",
    "Emeka",
    "Fatima",
    "Adebayo",
    "Aisha",
    "Chukwuemeka",
    "Zainab",
    "Tunde",
    "Amara",
    "Oluwaseun",
    "Khadija",
    "Chinedu",
    "Blessing",
    "Yusuf",
    "Chiamaka",
    "Abdullahi",
    "Ifeanyi",
    "Hauwa",
    "Segun",
    "Adaeze",
    "Mohammed",
    "Nneka",
    "Babatunde",
    "Amarachi",
    "Ahmed",
    "Chidinma",
    "Hassan",
    "Obiageli",
    "Usman",
    "Chinwe",
    "Aliyu",
    "Ifeoma",
    "Musa",
    "Nkechi",
    "Suleiman",
    "Adanna",
    "Bello",
    "Chinyere",
    "Abubakar",
    "Ezinne",
    "Muhammed",
    "Ngozi",
    "Abdulrahman",
    "Amina",
    "Omotola",
    "Rashida",
]

LAST_NAMES = [
    "Okafor",
    "Musa",
    "Eze",
    "Okonkwo",
    "Hassan",
    "Williams",
    "Abubakar",
    "Nwankwo",
    "Ibrahim",
    "Ojo",
    "Adeyemi",
    "Bello",
    "Obi",
    "Mohammed",
    "Chukwu",
    "Yusuf",
    "Okeke",
    "Suleiman",
    "Onuoha",
    "Abdullahi",
    "Ike",
    "Ahmed",
    "Nwosu",
    "Ali",
    "Chukwuma",
    "Usman",
    "Ezeh",
    "Aliyu",
    "Ogbonna",
    "Garba",
    "Emeka",
    "Sani",
    "Uzor",
    "Lawal",
    "Okafor",
    "Sadiq",
    "Okoli",
    "Mustafa",
    "Eze",
    "Bashir",
]

BUSINESS_TYPES = [
    "Mini-Mart",
    "Electronics",
    "Fashion Store",
    "Pharmacy",
    "Provisions",
    "Supermarket",
    "General Store",
    "Mobile Shop",
    "Cosmetics",
    "Boutique",
    "Hardware",
    "Bookshop",
    "Grocery",
    "Stationery",
    "Auto Parts",
    "Food Mart",
    "Beverage Shop",
    "Shoes Store",
    "Restaurant",
    "Cafe",
    "Bakery",
    "Meat Shop",
    "Fish Market",
    "Vegetable Store",
]

# Nigerian cities and states with coordinates
NIGERIAN_LOCATIONS = [
    {
        "city": "Lagos",
        "state": "Lagos",
        "lga": "Lagos Island",
        "lat": 6.5244,
        "lng": 3.3792,
    },
    {"city": "Lagos", "state": "Lagos", "lga": "Ikeja", "lat": 6.4541, "lng": 3.3947},
    {
        "city": "Lagos",
        "state": "Lagos",
        "lga": "Surulere",
        "lat": 6.5833,
        "lng": 3.3167,
    },
    {"city": "Lagos", "state": "Lagos", "lga": "Eti-Osa", "lat": 6.4281, "lng": 3.4219},
    {"city": "Lagos", "state": "Lagos", "lga": "Yaba", "lat": 6.6018, "lng": 3.3515},
    {"city": "Lagos", "state": "Lagos", "lga": "Apapa", "lat": 6.4489, "lng": 3.3594},
    {"city": "Lagos", "state": "Lagos", "lga": "Ikorodu", "lat": 6.6194, "lng": 3.5108},
    {"city": "Lagos", "state": "Lagos", "lga": "Badagry", "lat": 6.4167, "lng": 2.8833},
    {
        "city": "Abuja",
        "state": "FCT",
        "lga": "Abuja Municipal",
        "lat": 9.0820,
        "lng": 8.6753,
    },
    {
        "city": "Abuja",
        "state": "FCT",
        "lga": "Gwagwalada",
        "lat": 8.9420,
        "lng": 7.0837,
    },
    {"city": "Abuja", "state": "FCT", "lga": "Kubwa", "lat": 9.1356, "lng": 7.3367},
    {
        "city": "Kano",
        "state": "Kano",
        "lga": "Kano Municipal",
        "lat": 12.0022,
        "lng": 8.5919,
    },
    {
        "city": "Kano",
        "state": "Kano",
        "lga": "Nassarawa",
        "lat": 12.0167,
        "lng": 8.5333,
    },
    {
        "city": "Port Harcourt",
        "state": "Rivers",
        "lga": "Port Harcourt",
        "lat": 4.8156,
        "lng": 7.0498,
    },
    {
        "city": "Ibadan",
        "state": "Oyo",
        "lga": "Ibadan North",
        "lat": 7.3775,
        "lng": 3.9470,
    },
    {
        "city": "Kaduna",
        "state": "Kaduna",
        "lga": "Kaduna North",
        "lat": 10.5105,
        "lng": 7.4165,
    },
    {
        "city": "Enugu",
        "state": "Enugu",
        "lga": "Enugu North",
        "lat": 6.4403,
        "lng": 7.4947,
    },
    {
        "city": "Benin City",
        "state": "Edo",
        "lga": "Benin",
        "lat": 6.3176,
        "lng": 5.6145,
    },
]


def generate_agents(count=120):
    """Generate random agents data"""
    agents = []

    for i in range(count):
        first_name = random.choice(FIRST_NAMES)
        last_name = random.choice(LAST_NAMES)
        name = f"{first_name} {last_name}"
        business_type = random.choice(BUSINESS_TYPES)
        location_data = random.choice(NIGERIAN_LOCATIONS)

        # Add slight variation to coordinates to spread agents around
        lat_offset = random.uniform(-0.02, 0.02)
        lng_offset = random.uniform(-0.02, 0.02)

        agent = {
            "agent_id": f"agent-{str(i+1).zfill(3)}",
            "name": name,
            "business_name": f"{first_name} {business_type}",
            "location": {
                "lat": location_data["lat"] + lat_offset,
                "lng": location_data["lng"] + lng_offset,
            },
            "city": location_data["city"],
            "state": location_data["state"],
            "lga": location_data["lga"],
            "phone": f"+234 {random.randint(800, 909)} {random.randint(100, 999)} {random.randint(1000, 9999)}",
            "uin": f"UIN{str(random.randint(100000000, 999999999))}",
        }
        agents.append(agent)

    return agents


# Generate 120 agents
# Generate 120 agents
SAMPLE_AGENTS = generate_agents(120)

# POS Device IDs (one per agent)
SAMPLE_DEVICES = [f"POS-DEVICE-{str(i+1).zfill(3)}" for i in range(len(SAMPLE_AGENTS))]


def clear_existing_data(db: SessionLocal):
    """Clear existing test data"""
    print("Clearing existing data...")
    db.query(GeofenceViolation).delete()
    db.query(TransactionNotification).delete()
    db.query(POSDeviceLocation).delete()
    db.query(POSGeofence).delete()
    db.commit()
    print("✓ Cleared all existing data")


def seed_geofences(db: SessionLocal):
    """Create geofences for agents"""
    print("\nSeeding geofences...")
    geofences = []

    for agent in SAMPLE_AGENTS:
        # Primary geofence at business location
        geofence = POSGeofence(
            id=uuid.uuid4(),
            agent_id=agent["agent_id"],
            tenant_id=SAMPLE_TENANT,
            center_latitude=agent["location"]["lat"],
            center_longitude=agent["location"]["lng"],
            radius_km=2.0,  # 2km radius
            name=f"{agent['business_name']} - Main Location",
            is_active=True,
            created_at=datetime.utcnow(),
        )
        db.add(geofence)
        geofences.append(geofence)

    db.commit()
    print(f"✓ Created {len(geofences)} geofences")
    return geofences


def seed_locations(db: SessionLocal, geofences):
    """Create location history for devices"""
    print("\nSeeding device locations...")
    locations = []

    for i, agent in enumerate(SAMPLE_AGENTS):
        device_id = SAMPLE_DEVICES[i]
        geofence = geofences[i]

        # Create 5-10 location points over the last 24 hours (fewer due to more agents)
        num_locations = random.randint(5, 10)
        for j in range(num_locations):
            hours_ago = random.uniform(1, 24)  # Random time in last 24 hours

            # 80% within geofence, 20% outside
            is_inside = random.random() < 0.8

            if is_inside:
                # Vary location slightly within geofence
                lat_offset = random.uniform(-0.01, 0.01)
                lng_offset = random.uniform(-0.01, 0.01)
            else:
                # Move outside geofence (>2km away)
                lat_offset = random.uniform(-0.03, 0.03)
                lng_offset = random.uniform(-0.03, 0.03)

            location = POSDeviceLocation(
                id=uuid.uuid4(),
                device_id=device_id,
                agent_id=agent["agent_id"],
                tenant_id=SAMPLE_TENANT,
                latitude=agent["location"]["lat"] + lat_offset,
                longitude=agent["location"]["lng"] + lng_offset,
                accuracy=random.uniform(5, 25),  # GPS accuracy in meters
                timestamp=datetime.utcnow() - timedelta(hours=hours_ago),
                is_within_geofence=is_inside,
                speed=random.uniform(0, 15) if j % 3 == 0 else 0,  # Sometimes moving
                battery_level=random.randint(20, 100),
            )
            db.add(location)
            locations.append(location)

    db.commit()
    print(f"✓ Created {len(locations)} location records")
    return locations


def seed_violations(db: SessionLocal, geofences):
    """Create geofence violations"""
    print("\nSeeding geofence violations...")
    violations = []

    for i, agent in enumerate(SAMPLE_AGENTS):
        device_id = SAMPLE_DEVICES[i]
        geofence = geofences[i]

        # Create 10-20 violations per agent
        num_violations = random.randint(10, 20)

        for j in range(num_violations):
            hours_ago = random.uniform(1, 168)  # Within last 7 days (168 hours)
            is_resolved = random.random() < 0.3  # 30% resolved

            # Location outside geofence (>2km away)
            lat_offset = random.uniform(-0.04, 0.04)
            lng_offset = random.uniform(-0.04, 0.04)
            current_lat = agent["location"]["lat"] + lat_offset
            current_lng = agent["location"]["lng"] + lng_offset

            # Calculate distance from center
            from geopy.distance import geodesic

            distance = geodesic(
                (agent["location"]["lat"], agent["location"]["lng"]),
                (current_lat, current_lng),
            ).kilometers

            violation_time = datetime.utcnow() - timedelta(hours=hours_ago)

            violation = GeofenceViolation(
                id=uuid.uuid4(),
                device_id=device_id,
                agent_id=agent["agent_id"],
                tenant_id=SAMPLE_TENANT,
                geofence_id=geofence.id,
                geofence_name=geofence.name,
                current_latitude=current_lat,
                current_longitude=current_lng,
                geofence_center_lat=geofence.center_latitude,
                geofence_center_lng=geofence.center_longitude,
                distance_from_center_km=distance,
                radius_km=geofence.radius_km,
                violation_time=violation_time,
                was_resolved=is_resolved,
                resolved_at=(
                    violation_time + timedelta(hours=random.uniform(1, 5))
                    if is_resolved
                    else None
                ),
                admin_notes=(
                    "Resolved after agent confirmation" if is_resolved else None
                ),
            )
            db.add(violation)
            violations.append(violation)

    db.commit()
    print(f"✓ Created {len(violations)} geofence violations")
    return violations


def seed_transaction_notifications(db: SessionLocal):
    """Create sample transaction notifications"""
    print("\nSeeding transaction notifications...")
    notifications = []

    transaction_types = ["credit", "debit"]
    senders = [
        "John Doe",
        "Jane Smith",
        "ABC Company Ltd",
        "XYZ Store",
        "Transfer Service",
    ]

    for i, agent in enumerate(SAMPLE_AGENTS):
        device_id = SAMPLE_DEVICES[i]

        # Create 5-10 notifications per agent
        num_notifications = random.randint(5, 10)

        for j in range(num_notifications):
            hours_ago = random.uniform(0.5, 72)  # Within last 3 days

            notification = TransactionNotification(
                id=uuid.uuid4(),
                transaction_id=f"TXN-{uuid.uuid4().hex[:12].upper()}",
                agent_id=agent["agent_id"],
                tenant_id=SAMPLE_TENANT,
                device_id=device_id,
                amount=round(random.uniform(500, 50000), 2),
                transaction_type=random.choice(transaction_types),
                sender_name=random.choice(senders),
                account_number=f"30{random.randint(10000000, 99999999)}",
                notification_sent_at=datetime.utcnow() - timedelta(hours=hours_ago),
                was_delivered=random.random() < 0.95,  # 95% delivery rate
                delivered_at=(
                    datetime.utcnow() - timedelta(hours=hours_ago - 0.1)
                    if random.random() < 0.95
                    else None
                ),
            )
            db.add(notification)
            notifications.append(notification)

    db.commit()
    print(f"✓ Created {len(notifications)} transaction notifications")
    return notifications


def seed_agent_businesses(db: SessionLocal):
    """Seed agent businesses in the agent-service database"""
    print(f"\nSeeding agent businesses... ({len(SAMPLE_AGENTS)} agents to process)")

    # Use raw SQL to insert into agent-service tables
    agent_queries = []
    business_queries = []

    # Generate keycloak IDs
    keycloak_ids = [str(uuid.uuid4()) for _ in SAMPLE_AGENTS]

    for i, agent in enumerate(SAMPLE_AGENTS):
        keycloak_id = keycloak_ids[i]
        agent_uuid = str(uuid.uuid4())
        business_id = f"BIZ-{uuid.uuid4().hex[:12].upper()}"

        # Escape single quotes in names
        agent_name = agent["name"].replace("'", "''")
        first_name = agent["name"].split()[0].replace("'", "''")
        last_name = agent["name"].split()[-1].replace("'", "''")
        business_name = agent["business_name"].replace("'", "''")
        email = agent["name"].lower().replace(" ", ".").replace("'", "''")
        state = agent.get("state", "Lagos").replace("'", "''")
        lga = agent.get("lga", "").replace("'", "''")
        uin = agent.get("uin", f"UIN{i:09d}")
        postal_code = f"{100001 + i}"

        # Check if agent exists
        check_query = f"""
        SELECT id FROM agent WHERE email = '{email}@54agent.com';
        """
        result = db.execute(text(check_query)).fetchone()

        if not result:
            # Insert agent
            agent_query = f"""
            INSERT INTO agent (
                id, first_name, last_name, name, email, phone_number, uin,
                keycloak_id, tenant_id, agent_role, status, onboarding_status, 
                kyc_verification_status, business_name, business_address, 
                city, state, lga, postal_code, is_approved, created_at, updated_at
            ) VALUES (
                '{agent_uuid}',
                '{first_name}',
                '{last_name}',
                '{agent_name}',
                '{email}@54agent.com',
                '{agent['phone']}',
                '{uin}',
                '{keycloak_id}',
                '{SAMPLE_TENANT}',
                'AGENT',
                'ACTIVE',
                'COMPLETED',
                'VERIFIED',
                '{business_name}',
                '{agent["city"]}, {state}, Nigeria',
                '{agent["city"]}',
                '{state}',
                '{lga}',
                '{postal_code}',
                true,
                NOW(),
                NOW()
            ) ON CONFLICT (email) DO NOTHING;
            """
            agent_queries.append(agent_query)

            # Insert business
            business_query = f"""
            INSERT INTO agent_businesses (
                id, business_id, tenant_id, business_name, business_type,
                industry, country, address, agent_id, agent_keycloak_id,
                is_verified, verification_status, contact_phone,
                created_at, updated_at
            ) VALUES (
                '{uuid.uuid4()}',
                '{business_id}',
                '{SAMPLE_TENANT}',
                '{business_name}',
                'Retail',
                'Retail & Trade',
                'Nigeria',
                '{agent['city']}, Nigeria',
                '{agent_uuid}',
                '{keycloak_id}',
                true,
                'APPROVED',
                '{agent['phone']}',
                NOW(),
                NOW()
            ) ON CONFLICT (business_id) DO NOTHING;
            """
            business_queries.append(business_query)

    # Execute queries
    for query in agent_queries:
        try:
            db.execute(text(query))
            db.commit()
        except Exception as e:
            print(f"  Warning: Could not insert agent: {e}")
            db.rollback()

    for query in business_queries:
        try:
            db.execute(text(query))
            db.commit()
        except Exception as e:
            print(f"  Warning: Could not insert business: {e}")
            db.rollback()

    print(f"✓ Seeded {len(SAMPLE_AGENTS)} agents and businesses")


def main():
    """Main seeding function"""
    print("=" * 60)
    print("SEEDING REALTIME NOTIFICATION SERVICE DATA")
    print("=" * 60)

    db = SessionLocal()

    try:
        # Clear existing data
        clear_existing_data(db)

        # Seed agents and businesses
        # seed_agent_businesses(db)

        # Seed realtime service data
        geofences = seed_geofences(db)
        locations = seed_locations(db, geofences)
        violations = seed_violations(db, geofences)
        notifications = seed_transaction_notifications(db)

        print("\n" + "=" * 60)
        print("SEEDING COMPLETE!")
        print("=" * 60)
        print("\nSummary:")
        print(f"  • Agents: {len(SAMPLE_AGENTS)}")
        print(f"  • Geofences: {len(geofences)}")
        print(f"  • Location records: {len(locations)}")
        print(f"  • Violations: {len(violations)}")
        print(f"  • Transaction notifications: {len(notifications)}")
        print("\nTest with:")
        print(
            "  curl https://54agent.upi.dev/realtime/api/v1/admin/violations/active?hours=48"
        )
        print(
            f"  curl https://54agent.upi.dev/realtime/api/v1/geofence/list/{SAMPLE_AGENTS[0]['agent_id']}"
        )

    except Exception as e:
        print(f"\n❌ Error during seeding: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
