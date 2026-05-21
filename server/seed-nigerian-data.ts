/**
 * Nigerian Data Seed Script
 * Seeds the entire platform with realistic Nigerian data across all tables.
 *
 * Usage: npx tsx server/seed-nigerian-data.ts
 */
import pg from "pg";

const { Pool } = pg;

const pool = new Pool({
  connectionString:
    process.env.DATABASE_URL ||
    "postgresql://postgres:postgres@localhost:5432/ngapp",
});

// ─── Nigerian Reference Data ─────────────────────────────────────────────────

const NIGERIAN_STATES = [
  "Lagos", "Abuja", "Kano", "Rivers", "Oyo", "Kaduna", "Ogun", "Anambra",
  "Edo", "Delta", "Enugu", "Imo", "Abia", "Borno", "Bauchi", "Kwara",
  "Osun", "Ekiti", "Ondo", "Cross River", "Akwa Ibom", "Plateau", "Niger",
  "Benue", "Nasarawa", "Kogi", "Taraba", "Adamawa", "Gombe", "Yobe",
  "Zamfara", "Sokoto", "Kebbi", "Jigawa", "Katsina", "Bayelsa", "Ebonyi",
];

const NIGERIAN_CITIES: Record<string, string[]> = {
  Lagos: ["Ikeja", "Lekki", "Victoria Island", "Surulere", "Yaba", "Oshodi", "Ajah", "Ikoyi", "Mushin", "Agege"],
  Abuja: ["Garki", "Wuse", "Maitama", "Asokoro", "Gwarinpa", "Kubwa", "Nyanya", "Lugbe"],
  Kano: ["Nassarawa", "Fagge", "Gwale", "Tarauni", "Ungogo", "Dala", "Kumbotso"],
  Rivers: ["Port Harcourt", "Obio-Akpor", "Eleme", "Bonny", "Okrika", "Oyigbo"],
  Oyo: ["Ibadan", "Ogbomoso", "Oyo Town", "Iseyin", "Saki", "Eruwa"],
  Kaduna: ["Kaduna North", "Kaduna South", "Zaria", "Kafanchan", "Birnin Gwari"],
  Ogun: ["Abeokuta", "Sagamu", "Ijebu-Ode", "Ota", "Ilaro", "Ifo"],
  Anambra: ["Onitsha", "Awka", "Nnewi", "Ekwulobia", "Ihiala"],
  Edo: ["Benin City", "Auchi", "Ekpoma", "Uromi", "Irrua"],
  Delta: ["Warri", "Asaba", "Sapele", "Agbor", "Ughelli", "Ozoro"],
  Enugu: ["Enugu", "Nsukka", "Agbani", "Udi", "Oji River"],
  Imo: ["Owerri", "Orlu", "Okigwe", "Oguta"],
  Abia: ["Aba", "Umuahia", "Ohafia", "Arochukwu"],
};

const NIGERIAN_BANKS = [
  "Access Bank", "GTBank", "First Bank", "UBA", "Zenith Bank",
  "Fidelity Bank", "Sterling Bank", "Union Bank", "Wema Bank",
  "Stanbic IBTC", "FCMB", "Ecobank", "Polaris Bank", "Keystone Bank",
  "Kuda Bank", "OPay", "PalmPay", "Moniepoint",
];

const NIGERIAN_FIRST_NAMES = [
  "Adebayo", "Chidinma", "Oluwaseun", "Ngozi", "Emeka", "Funmilayo",
  "Chukwuemeka", "Aisha", "Obinna", "Yetunde", "Tunde", "Amaka",
  "Ibrahim", "Folake", "Olu", "Chiamaka", "Musa", "Temitope",
  "Ifeanyi", "Bukola", "Abdullahi", "Nneka", "Segun", "Halima",
  "Chidi", "Titilayo", "Yakubu", "Chioma", "Dele", "Fatima",
  "Obiora", "Shade", "Uche", "Bintu", "Obi", "Zainab",
  "Nnamdi", "Jumoke", "Bala", "Mercy", "Kingsley", "Habiba",
  "Victor", "Adetola", "Sunday", "Khadijah", "Peter", "Adeola",
  "Godwin", "Patience",
];

const NIGERIAN_LAST_NAMES = [
  "Okafor", "Adeyemi", "Mohammed", "Okonkwo", "Balogun", "Abubakar",
  "Eze", "Ogundimu", "Ibrahim", "Nwosu", "Adeleke", "Sani",
  "Okoro", "Akande", "Aliyu", "Igwe", "Fashola", "Yusuf",
  "Nwankwo", "Oladipo", "Garba", "Chukwu", "Olaleye", "Danjuma",
  "Onyeka", "Jimoh", "Madu", "Ayodeji", "Bello", "Ugochukwu",
  "Oni", "Ahmad", "Obi", "Lawal", "Nwachukwu", "Adamu",
  "Ikenna", "Salami", "Agu", "Bakare", "Dikko", "Obaseki",
  "Osuji", "Abdulkadir", "Emenike", "Afolabi",
];

const NIGERIAN_PRODUCTS: { name: string; category: number; priceRange: [number, number] }[] = [
  // Electronics (1)
  { name: "Hisense 43\" Smart TV", category: 1, priceRange: [145000, 195000] },
  { name: "LG Inverter Air Conditioner 1.5HP", category: 1, priceRange: [280000, 350000] },
  { name: "Thermocool Generator 3.5KVA", category: 1, priceRange: [350000, 450000] },
  { name: "Scanfrost Refrigerator 250L", category: 1, priceRange: [185000, 220000] },
  { name: "JBL Bluetooth Speaker Flip 6", category: 1, priceRange: [35000, 55000] },
  { name: "Binatone Blender 1.5L", category: 1, priceRange: [15000, 25000] },
  // Phones & Accessories (2)
  { name: "Samsung Galaxy A54 5G", category: 2, priceRange: [220000, 280000] },
  { name: "iPhone 15 128GB", category: 2, priceRange: [650000, 750000] },
  { name: "Tecno Camon 20 Pro", category: 2, priceRange: [150000, 185000] },
  { name: "Infinix Note 30 Pro", category: 2, priceRange: [130000, 165000] },
  { name: "Oraimo Power Bank 20000mAh", category: 2, priceRange: [8000, 12000] },
  { name: "Airpods Pro 2nd Gen", category: 2, priceRange: [85000, 120000] },
  { name: "Phone Screen Protector (Tempered Glass)", category: 2, priceRange: [1500, 3000] },
  { name: "Samsung Galaxy S24 Ultra", category: 2, priceRange: [900000, 1100000] },
  // Fashion (3)
  { name: "Ankara Fabric (6 yards)", category: 3, priceRange: [3500, 8000] },
  { name: "Men's Native Agbada Set", category: 3, priceRange: [25000, 65000] },
  { name: "Women's Lace Iro & Buba", category: 3, priceRange: [15000, 45000] },
  { name: "Palm Slippers (Handmade)", category: 3, priceRange: [5000, 15000] },
  { name: "Adire Fabric (5 yards)", category: 3, priceRange: [8000, 20000] },
  { name: "Men's Kaftan (Senator)", category: 3, priceRange: [12000, 35000] },
  { name: "Beaded Jewelry Set", category: 3, priceRange: [5000, 25000] },
  // Groceries (4)
  { name: "Golden Penny Semolina 10kg", category: 4, priceRange: [7500, 9500] },
  { name: "Dangote Sugar 50kg", category: 4, priceRange: [45000, 55000] },
  { name: "Kings Vegetable Oil 5L", category: 4, priceRange: [8000, 11000] },
  { name: "Indomie Noodles (Carton of 40)", category: 4, priceRange: [12000, 15000] },
  { name: "Bag of Rice (50kg Local)", category: 4, priceRange: [55000, 75000] },
  { name: "Peak Milk Tin (400g x 12)", category: 4, priceRange: [9500, 12000] },
  { name: "Maggi Seasoning (Carton)", category: 4, priceRange: [4500, 6000] },
  { name: "Bournvita 900g Tin", category: 4, priceRange: [3500, 5000] },
  // Health & Beauty (5)
  { name: "Oriflame Skincare Set", category: 5, priceRange: [15000, 25000] },
  { name: "Cantu Shea Butter Leave-In", category: 5, priceRange: [4500, 7000] },
  { name: "Black Soap (Natural 500g)", category: 5, priceRange: [1000, 3000] },
  { name: "Shea Butter (Unrefined 500g)", category: 5, priceRange: [2000, 4000] },
  { name: "Nivea Body Lotion 400ml", category: 5, priceRange: [2500, 4000] },
  // Home & Garden (6)
  { name: "Mouka Foam Mattress 6x6", category: 6, priceRange: [85000, 150000] },
  { name: "Rechargeable Standing Fan", category: 6, priceRange: [25000, 45000] },
  { name: "Plastic Storage Containers Set", category: 6, priceRange: [8000, 15000] },
  { name: "Solar Panel 200W", category: 6, priceRange: [65000, 95000] },
  { name: "Inverter Battery 200AH", category: 6, priceRange: [120000, 180000] },
  // Auto Parts (7)
  { name: "Car Battery (75AH)", category: 7, priceRange: [35000, 55000] },
  { name: "Engine Oil (5L Synthetic)", category: 7, priceRange: [12000, 20000] },
  { name: "Brake Pads (Front Set)", category: 7, priceRange: [8000, 15000] },
  // Food & Beverages (8)
  { name: "Palm Wine (Fresh, 5L)", category: 8, priceRange: [3000, 5000] },
  { name: "Zobo Drink (Hibiscus, 1L x 12)", category: 8, priceRange: [3600, 5000] },
  { name: "Suya Spice Mix (1kg)", category: 8, priceRange: [2500, 4000] },
  { name: "Dried Fish (Stockfish, 1kg)", category: 8, priceRange: [8000, 12000] },
  { name: "Garri (White, 50kg bag)", category: 8, priceRange: [20000, 32000] },
  { name: "Ogiri (Locust Bean, 500g)", category: 8, priceRange: [1500, 3000] },
  { name: "Egusi (Ground, 2kg)", category: 8, priceRange: [6000, 9000] },
  { name: "Pepper Soup Spice (500g)", category: 8, priceRange: [2000, 3500] },
  // Computing (9)
  { name: "HP Laptop 15 (Core i5)", category: 9, priceRange: [350000, 480000] },
  { name: "USB Flash Drive 64GB", category: 9, priceRange: [3500, 6000] },
  { name: "Wireless Mouse & Keyboard Combo", category: 9, priceRange: [8000, 15000] },
  { name: "External Hard Drive 1TB", category: 9, priceRange: [25000, 40000] },
  // Building Materials (10)
  { name: "Dangote Cement (50kg)", category: 10, priceRange: [5500, 7000] },
  { name: "Roofing Sheets (Bundle of 20)", category: 10, priceRange: [120000, 180000] },
  { name: "Iron Rods (12mm, Bundle)", category: 10, priceRange: [350000, 450000] },
  { name: "PVC Ceiling (Box of 10)", category: 10, priceRange: [15000, 25000] },
  // Farming (11)
  { name: "NPK Fertilizer (50kg)", category: 11, priceRange: [18000, 25000] },
  { name: "Maize Seeds (Hybrid, 10kg)", category: 11, priceRange: [8000, 12000] },
  { name: "Knapsack Sprayer 16L", category: 11, priceRange: [15000, 25000] },
  { name: "Poultry Feed (25kg)", category: 11, priceRange: [12000, 18000] },
  // Baby Products (12)
  { name: "Baby Diapers (Mega Pack)", category: 12, priceRange: [8000, 15000] },
  { name: "Baby Formula (900g)", category: 12, priceRange: [6000, 12000] },
  { name: "Baby Cot (Wooden)", category: 12, priceRange: [35000, 65000] },
  // Sports (13)
  { name: "Football (Nike Official)", category: 13, priceRange: [15000, 30000] },
  { name: "Running Shoes (Adidas)", category: 13, priceRange: [25000, 55000] },
  { name: "Gym Dumbbell Set (20kg)", category: 13, priceRange: [20000, 40000] },
];

const STORE_NAMES = [
  "Mama Ngozi Electronics", "Alhaji Musa General Store", "Baba Alaye Fashion House",
  "ChiChi Beauty Palace", "Emeka Motors & Parts", "Funmi's Kitchen Supplies",
  "Iya Basira Groceries", "Kingsley Tech Hub", "Nkechi Home & Garden",
  "Olu Phone Centre", "Prince Digital World", "Queen's Fabrics & Accessories",
  "Rasheed Building Materials", "Sunday Farm Inputs", "Titi Baby Store",
  "Uncle Joe Sports", "Vitality Health Store", "Wale's Book Corner",
  "Xpress Mobile Accessories", "Yemi Computing Centre", "Zainab Ankara Palace",
  "Dada Electronics Mart", "Ejiro's Food Market", "Garba Agro Supply",
  "Hauwa Fashion World", "Ikenna Auto Parts", "Jide Power Solutions",
  "Kunle Furniture Store", "Lateef Phone Repairs", "Mama Iyabo Provisions",
];

const TERMINAL_MODELS = [
  "PAX A920 MAX", "PAX A920 Pro", "Moniepoint POS", "OPay Terminal S1",
  "Verifone X990", "Ingenico Move 5000", "PAX D200T", "Sunmi V2 Pro",
];

// ─── Helpers ─────────────────────────────────────────────────────────────────

function rand(min: number, max: number): number {
  return Math.floor(Math.random() * (max - min + 1)) + min;
}
function pick<T>(arr: readonly T[]): T {
  return arr[Math.floor(Math.random() * arr.length)];
}
function pickN<T>(arr: readonly T[], n: number): T[] {
  const shuffled = [...arr].sort(() => 0.5 - Math.random());
  return shuffled.slice(0, n);
}
function nigerianPhone(): string {
  const prefixes = ["0803", "0805", "0806", "0807", "0808", "0809", "0810", "0812", "0813", "0814", "0815", "0816", "0817", "0818", "0902", "0903", "0904", "0905", "0906", "0907", "0908", "0909", "0912", "0913", "0915", "0916"];
  return pick(prefixes) + String(rand(1000000, 9999999));
}
function nigerianBVN(): string {
  return "22" + String(rand(100000000, 999999999));
}
function nigerianNIN(): string {
  return String(rand(10000000000, 99999999999));
}
function randomDate(daysBack: number): Date {
  const now = new Date();
  return new Date(now.getTime() - rand(0, daysBack * 24 * 60 * 60 * 1000));
}
function slugify(name: string): string {
  return name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");
}

// ─── Seed Functions ──────────────────────────────────────────────────────────

async function seedAgents(count: number = 30) {
  console.log(`  Seeding ${count} agents...`);
  const values: string[] = [];
  const params: unknown[] = [];
  let idx = 0;

  for (let i = 1; i <= count; i++) {
    const state = pick(NIGERIAN_STATES);
    const cities = NIGERIAN_CITIES[state] || [state];
    const city = pick(cities);
    const firstName = pick(NIGERIAN_FIRST_NAMES);
    const lastName = pick(NIGERIAN_LAST_NAMES);
    const tier = pick(["Bronze", "Silver", "Gold", "Platinum"] as const);
    const role = i <= 3 ? "supervisor" : i <= 6 ? "agent_manager" : "agent";

    const row = [
      `AG${String(i).padStart(5, "0")}`,
      `${firstName} ${lastName}`,
      nigerianPhone(),
      `${firstName.toLowerCase()}.${lastName.toLowerCase()}${i}@54link.ng`,
      `${city}, ${state}`,
      pick(TERMINAL_MODELS),
      `SN${rand(100000, 999999)}`,
      tier,
      role,
      "$2b$10$fakehashforseeddataonly" + rand(100, 999),
      String(rand(50000, 5000000)),
      String(rand(1000000, 10000000)),
      String(rand(5000, 500000)),
      rand(100, 50000),
      rand(0, 120),
      i,
      true,
      false,
      true,
    ];
    const placeholders = row.map(() => `$${++idx}`);
    values.push(`(${placeholders.join(", ")})`);
    params.push(...row);
  }

  await pool.query(
    `INSERT INTO agents ("agentCode", name, phone, email, location, "terminalModel", "terminalSerial", tier, role, "pinHash", "floatBalance", "floatLimit", "commissionBalance", "loyaltyPoints", streak, rank, "isActive", "floatLocked", "terminalEnabled")
     VALUES ${values.join(", ")}
     ON CONFLICT ("agentCode") DO NOTHING`,
    params
  );
}

async function seedCustomers(count: number = 50) {
  console.log(`  Seeding ${count} customers...`);
  const values: string[] = [];
  const params: unknown[] = [];
  let idx = 0;

  for (let i = 1; i <= count; i++) {
    const firstName = pick(NIGERIAN_FIRST_NAMES);
    const lastName = pick(NIGERIAN_LAST_NAMES);
    const state = pick(Object.keys(NIGERIAN_CITIES));
    const city = pick(NIGERIAN_CITIES[state]);
    const streets = ["Adeola Odeku St", "Allen Avenue", "Awolowo Way", "Bode Thomas St", "Herbert Macaulay Way", "Ikorodu Rd", "Marina", "Broad St", "Ahmadu Bello Way", "Tafawa Balewa Square"];

    const row = [
      firstName,
      lastName,
      nigerianPhone(),
      `${firstName.toLowerCase()}${lastName.toLowerCase()}${i}@gmail.com`,
      nigerianBVN(),
      nigerianNIN(),
      `${rand(1970, 2000)}-${String(rand(1, 12)).padStart(2, "0")}-${String(rand(1, 28)).padStart(2, "0")}`,
      `${rand(1, 200)} ${pick(streets)}, ${city}, ${state}`,
      pick(["active", "active", "active", "pending_kyc"] as const),
      rand(1, 3),
      String(rand(1000, 500000)),
      String(pick([50000, 200000, 500000, 1000000])),
    ];
    const placeholders = row.map(() => `$${++idx}`);
    values.push(`(${placeholders.join(", ")})`);
    params.push(...row);
  }

  await pool.query(
    `INSERT INTO customers ("firstName", "lastName", phone, email, bvn, nin, "dateOfBirth", address, status, "kycLevel", "walletBalance", "dailyLimit")
     VALUES ${values.join(", ")}
     ON CONFLICT (phone) DO NOTHING`,
    params
  );
}

async function seedTransactions(agentCount: number, count: number = 200) {
  console.log(`  Seeding ${count} transactions...`);
  const txTypes = ["Cash In", "Cash Out", "Transfer", "Card Payment", "QR Payment", "Airtime", "Bill Payment"] as const;
  const channels = ["Cash", "Card", "USSD", "QR", "NFC", "App"] as const;
  const statuses = ["success", "success", "success", "success", "pending", "failed"] as const;

  const values: string[] = [];
  const params: unknown[] = [];
  let idx = 0;

  for (let i = 1; i <= count; i++) {
    const type = pick(txTypes);
    const amount = type === "Airtime" ? rand(100, 5000) : rand(500, 500000);
    const fee = Math.floor(amount * 0.01);
    const commission = Math.floor(fee * 0.5);
    const status = pick(statuses);
    const isTransfer = type === "Transfer";

    const row = [
      `TXN${String(i).padStart(8, "0")}${rand(10, 99)}`,
      rand(1, agentCount),
      type,
      String(amount),
      String(fee),
      String(commission),
      "NGN",
      `${pick(NIGERIAN_FIRST_NAMES)} ${pick(NIGERIAN_LAST_NAMES)}`,
      nigerianPhone(),
      isTransfer ? pick(NIGERIAN_BANKS) : null,
      isTransfer ? String(rand(1000000000, 9999999999)) : null,
      pick(channels),
      status,
      randomDate(90).toISOString(),
    ];
    const placeholders = row.map(() => `$${++idx}`);
    values.push(`(${placeholders.join(", ")})`);
    params.push(...row);
  }

  await pool.query(
    `INSERT INTO transactions (ref, "agentId", type, amount, fee, commission, currency, "customerName", "customerPhone", "destinationBank", "destinationAccount", channel, status, "createdAt")
     VALUES ${values.join(", ")}
     ON CONFLICT (ref) DO NOTHING`,
    params
  );
}

async function seedAgentStores(agentCount: number, count: number = 20) {
  console.log(`  Seeding ${count} agent stores...`);
  const values: string[] = [];
  const params: unknown[] = [];
  let idx = 0;

  for (let i = 1; i <= count; i++) {
    const storeName = STORE_NAMES[i - 1] || `${pick(NIGERIAN_FIRST_NAMES)}'s Store`;
    const state = pick(Object.keys(NIGERIAN_CITIES));
    const city = pick(NIGERIAN_CITIES[state]);
    const cats = pickN(["Electronics", "Fashion", "Groceries", "Phones", "Health & Beauty", "Home & Garden", "Food", "Computing", "Auto Parts"], rand(2, 4));

    const row = [
      i, // agent_id
      `AG${String(i).padStart(5, "0")}`, // agent_code
      slugify(storeName), // slug
      storeName, // store_name
      `Welcome to ${storeName}! We offer quality products at the best prices in ${city}, ${state}. Fast delivery available across Nigeria.`, // description
      pick(["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#06b6d4"]), // theme_color
      nigerianPhone(), // phone
      `${slugify(storeName)}@54link.ng`, // email
      `${rand(1, 100)} ${pick(["Market Road", "Main Street", "Junction", "Shopping Complex", "Trade Fair"])} , ${city}`, // address
      city, // city
      state, // state
      city, // lga
      String((rand(600, 1000) / 100).toFixed(4)), // latitude (Nigeria ~4-14N)
      String((rand(300, 1500) / 100).toFixed(4)), // longitude (Nigeria ~3-15E)
      JSON.stringify(cats), // categories
      true, // delivery_enabled
      true, // pickup_enabled
      String(rand(2000, 10000)), // min_order_amount
      "5.00", // platform_commission_pct
      i <= 15 ? "active" : "pending", // status
      i <= 15, // is_verified
      rand(10, 500), // total_sales
      String(rand(100000, 5000000)), // total_revenue
      String((rand(35, 50) / 10).toFixed(2)), // average_rating
      rand(5, 100), // review_count
    ];
    const placeholders = row.map(() => `$${++idx}`);
    values.push(`(${placeholders.join(", ")})`);
    params.push(...row);
  }

  await pool.query(
    `INSERT INTO agent_stores (agent_id, agent_code, slug, store_name, description, theme_color, phone, email, address, city, state, lga, latitude, longitude, categories, delivery_enabled, pickup_enabled, min_order_amount, platform_commission_pct, status, is_verified, total_sales, total_revenue, average_rating, review_count)
     VALUES ${values.join(", ")}
     ON CONFLICT (agent_id) DO NOTHING`,
    params
  );
}

async function seedProducts(storeCount: number) {
  const count = 80;
  console.log(`  Seeding ${count} products...`);
  const values: string[] = [];
  const params: unknown[] = [];
  let idx = 0;

  for (let i = 1; i <= count; i++) {
    const prod = NIGERIAN_PRODUCTS[(i - 1) % NIGERIAN_PRODUCTS.length];
    const price = rand(prod.priceRange[0], prod.priceRange[1]);
    const merchantId = rand(1, storeCount);

    const row = [
      `SKU${String(i).padStart(6, "0")}`, // sku
      i <= NIGERIAN_PRODUCTS.length ? prod.name : `${prod.name} (Pack ${Math.ceil(i / NIGERIAN_PRODUCTS.length)})`, // name
      `High quality ${prod.name}. Sourced from trusted Nigerian suppliers. Fast delivery across Nigeria.`, // description
      prod.category, // category_id
      String(price), // price
      "NGN", // currency
      true, // is_active
      "active", // status
      merchantId, // merchant_id
      merchantId, // agent_id
      String(rand(1, 50)), // weight
      JSON.stringify(pickN(["bestseller", "new", "promo", "limited", "bulk", "wholesale", "retail"], rand(1, 3))), // tags
      JSON.stringify({ brand: pick(["Generic", "Premium", "Local", "Imported"]), condition: "new" }), // attributes
    ];
    const placeholders = row.map(() => `$${++idx}`);
    values.push(`(${placeholders.join(", ")})`);
    params.push(...row);
  }

  await pool.query(
    `INSERT INTO ecommerce_products (sku, name, description, category_id, price, currency, is_active, status, merchant_id, agent_id, weight, tags, attributes)
     VALUES ${values.join(", ")}
     ON CONFLICT (sku) DO NOTHING`,
    params
  );
}

async function seedInventory(productCount: number) {
  console.log(`  Seeding inventory for ${productCount} products...`);
  const values: string[] = [];
  const params: unknown[] = [];
  let idx = 0;

  for (let i = 1; i <= productCount; i++) {
    const row = [
      `SKU${String(i).padStart(6, "0")}`, // sku
      i, // product_id
      rand(5, 500), // quantity
      rand(0, 10), // reserved
      rand(5, 20), // reorder_point
      "default", // warehouse_id
    ];
    const placeholders = row.map(() => `$${++idx}`);
    values.push(`(${placeholders.join(", ")})`);
    params.push(...row);
  }

  await pool.query(
    `INSERT INTO ecommerce_inventory (sku, product_id, quantity, reserved, reorder_point, warehouse_id)
     VALUES ${values.join(", ")}
     ON CONFLICT (sku) DO NOTHING`,
    params
  );
}

async function seedOrders(customerCount: number, storeCount: number, count: number = 60) {
  console.log(`  Seeding ${count} orders...`);
  const statuses = ["pending", "processing", "shipped", "delivered", "delivered", "delivered", "cancelled"] as const;
  const paymentMethods = ["card", "bank_transfer", "wallet", "cash_on_delivery", "ussd"];

  const values: string[] = [];
  const params: unknown[] = [];
  let idx = 0;

  for (let i = 1; i <= count; i++) {
    const state = pick(Object.keys(NIGERIAN_CITIES));
    const city = pick(NIGERIAN_CITIES[state]);
    const subTotal = rand(5000, 200000);
    const tax = Math.round(subTotal * 0.075);
    const shipping = rand(0, 1) === 1 ? rand(500, 3000) : 0;
    const total = subTotal + tax + shipping;
    const merchantId = rand(1, storeCount);

    const row = [
      `ORD-${String(i).padStart(6, "0")}`, // order_number
      rand(1, customerCount), // customer_id
      merchantId, // merchant_id
      merchantId, // agent_id
      pick(statuses), // status
      String(subTotal), // sub_total
      String(tax), // tax
      String(shipping), // shipping_fee
      "0", // discount
      String(total), // total
      "NGN", // currency
      pick(paymentMethods), // payment_method
      `PAY${rand(100000, 999999)}`, // payment_ref
      JSON.stringify({
        street: `${rand(1, 200)} ${pick(["Awolowo Rd", "Broad St", "Adeola Odeku", "Allen Ave", "Bode Thomas", "Ahmadu Bello Way"])}`,
        city,
        state,
        country: "Nigeria",
        zip: String(rand(100000, 999999)),
      }), // shipping_address
      randomDate(60).toISOString(), // created_at
    ];
    const placeholders = row.map(() => `$${++idx}`);
    values.push(`(${placeholders.join(", ")})`);
    params.push(...row);
  }

  await pool.query(
    `INSERT INTO ecommerce_orders (order_number, customer_id, merchant_id, agent_id, status, sub_total, tax, shipping_fee, discount, total, currency, payment_method, payment_ref, shipping_address, created_at)
     VALUES ${values.join(", ")}
     ON CONFLICT (order_number) DO NOTHING`,
    params
  );
}

async function seedOrderItems(orderCount: number, productCount: number) {
  console.log(`  Seeding order items...`);
  const values: string[] = [];
  const params: unknown[] = [];
  let idx = 0;

  for (let orderId = 1; orderId <= orderCount; orderId++) {
    const numItems = rand(1, 4);
    for (let j = 0; j < numItems; j++) {
      const prodIdx = rand(1, productCount);
      const price = rand(2000, 100000);
      const qty = rand(1, 5);
      const row = [
        orderId,
        prodIdx,
        `SKU${String(prodIdx).padStart(6, "0")}`,
        NIGERIAN_PRODUCTS[(prodIdx - 1) % NIGERIAN_PRODUCTS.length].name,
        qty,
        String(price),
        String(price * qty),
      ];
      const placeholders = row.map(() => `$${++idx}`);
      values.push(`(${placeholders.join(", ")})`);
      params.push(...row);
    }
  }

  await pool.query(
    `INSERT INTO ecommerce_order_items (order_id, product_id, sku, name, quantity, unit_price, total)
     VALUES ${values.join(", ")}`,
    params
  );
}

async function seedFraudAlerts(agentCount: number) {
  const count = 15;
  console.log(`  Seeding ${count} fraud alerts...`);
  const types = ["velocity_breach", "unusual_amount", "geo_anomaly", "device_mismatch", "duplicate_transaction"];
  const values: string[] = [];
  const params: unknown[] = [];
  let idx = 0;

  for (let i = 1; i <= count; i++) {
    const type = pick(types);
    const row = [
      rand(1, agentCount), // agentId
      pick(["critical", "high", "medium", "low"]), // severity
      type, // type
      `${pick(NIGERIAN_FIRST_NAMES)} ${pick(NIGERIAN_LAST_NAMES)}`, // customerName
      String(rand(50000, 2000000)), // amount
      `Suspicious activity: ${type.replace(/_/g, " ")} detected for agent AG${String(rand(1, agentCount)).padStart(5, "0")} at ${pick(["Lagos", "Abuja", "Kano", "PH"])}`, // reason
      pick(["open", "investigating", "resolved", "dismissed"]), // status
    ];
    const placeholders = row.map(() => `$${++idx}`);
    values.push(`(${placeholders.join(", ")})`);
    params.push(...row);
  }

  await pool.query(
    `INSERT INTO fraud_alerts ("agentId", severity, type, "customerName", amount, reason, status)
     VALUES ${values.join(", ")}`,
    params
  );
}

async function seedProductReviews(productCount: number, customerCount: number) {
  const count = 40;
  console.log(`  Seeding ${count} product reviews...`);
  const reviewTexts = [
    "Excellent quality! Delivered on time to my doorstep in Lagos.",
    "Good product but delivery from Abuja took too long.",
    "Very satisfied with this purchase. Na correct product!",
    "The item no be as dem describe am. Expected better quality.",
    "Amazing value for money. I recommend am for everybody!",
    "E dey okay for the price. Average quality sha.",
    "Superb! My family loves it. God bless the seller.",
    "Fast delivery and well packaged. Kudos!",
    "Good for the price. No wahala at all.",
    "Best purchase this month! You fit trust this seller.",
    "Item arrived quickly. Very happy with the quality.",
    "Na original product. No fake. 5 stars!",
  ];
  const values: string[] = [];
  const params: unknown[] = [];
  let idx = 0;

  for (let i = 1; i <= count; i++) {
    const firstName = pick(NIGERIAN_FIRST_NAMES);
    const lastName = pick(NIGERIAN_LAST_NAMES);
    const row = [
      rand(1, productCount), // product_id
      rand(1, 20), // store_id
      rand(1, customerCount), // customer_id
      `${firstName} ${lastName}`, // customer_name
      rand(3, 5), // rating
      pick(["Great product!", "Worth every naira", "Good quality", "Very satisfied", "Recommended!", "Na correct one!"]), // title
      pick(reviewTexts), // body
      rand(0, 1) === 1, // is_verified_purchase
      rand(0, 15), // helpful_count
      randomDate(45).toISOString(), // created_at
    ];
    const placeholders = row.map(() => `$${++idx}`);
    values.push(`(${placeholders.join(", ")})`);
    params.push(...row);
  }

  await pool.query(
    `INSERT INTO product_reviews (product_id, store_id, customer_id, customer_name, rating, title, body, is_verified_purchase, helpful_count, created_at)
     VALUES ${values.join(", ")}`,
    params
  );
}

async function seedDeliveryZones(storeCount: number) {
  const zoneNames = ["Within City (Same Day)", "Interstate (2-3 Days)", "Express (Next Day)", "Economy (4-7 Days)"];
  const values: string[] = [];
  const params: unknown[] = [];
  let idx = 0;

  for (let storeId = 1; storeId <= Math.min(storeCount, 15); storeId++) {
    const numZones = rand(2, 4);
    for (let j = 0; j < numZones; j++) {
      const row = [
        storeId, // store_id
        zoneNames[j] || "Standard", // zone_name
        String(rand(500, 5000)), // delivery_fee
        rand(30, 180), // estimated_minutes
        true, // is_active
      ];
      const placeholders = row.map(() => `$${++idx}`);
      values.push(`(${placeholders.join(", ")})`);
      params.push(...row);
    }
  }
  console.log(`  Seeding ${values.length} delivery zones...`);
  await pool.query(
    `INSERT INTO delivery_zones (store_id, zone_name, delivery_fee, estimated_minutes, is_active)
     VALUES ${values.join(", ")}`,
    params
  );
}

async function seedAuditLog(agentCount: number) {
  const count = 50;
  console.log(`  Seeding ${count} audit log entries...`);
  const actions = ["login", "transaction.create", "float.topup", "agent.update", "kyc.verify", "store.create", "product.add", "order.update", "dispute.open", "config.change"];
  const values: string[] = [];
  const params: unknown[] = [];
  let idx = 0;

  for (let i = 1; i <= count; i++) {
    const agentId = rand(1, agentCount);
    const row = [
      agentId,
      `AG${String(agentId).padStart(5, "0")}`,
      pick(actions),
      pick(["transaction", "agent", "store", "product", "order", "system"]),
      `197.210.${rand(1, 255)}.${rand(1, 255)}`,
      "54Link POS Shell/3.0 (Android 13)",
      pick(["success", "success", "success", "failure"]),
      JSON.stringify({ platform: "android", deviceId: `DEV${rand(1000, 9999)}` }),
      randomDate(30).toISOString(),
    ];
    const placeholders = row.map(() => `$${++idx}`);
    values.push(`(${placeholders.join(", ")})`);
    params.push(...row);
  }

  await pool.query(
    `INSERT INTO audit_log ("agentId", "agentCode", action, resource, "ipAddress", "userAgent", status, metadata, "createdAt")
     VALUES ${values.join(", ")}`,
    params
  );
}

async function seedLoyaltyHistory(agentCount: number) {
  const count = 40;
  console.log(`  Seeding ${count} loyalty entries...`);
  const types = ["earned", "redeemed", "bonus", "challenge"] as const;
  const descriptions = ["Daily login streak", "Transaction milestone", "Referral bonus", "Monthly challenge", "Tier upgrade bonus", "Birthday reward", "Top performer"];
  const values: string[] = [];
  const params: unknown[] = [];
  let idx = 0;

  for (let i = 1; i <= count; i++) {
    const points = rand(10, 500);
    const row = [
      rand(1, agentCount),
      pick(types),
      points,
      pick(descriptions),
      rand(100, 50000), // balanceAfter
      randomDate(60).toISOString(),
    ];
    const placeholders = row.map(() => `$${++idx}`);
    values.push(`(${placeholders.join(", ")})`);
    params.push(...row);
  }

  await pool.query(
    `INSERT INTO loyalty_history ("agentId", type, points, description, "balanceAfter", "createdAt")
     VALUES ${values.join(", ")}`,
    params
  );
}

// ─── Main ────────────────────────────────────────────────────────────────────

async function main() {
  console.log("🇳🇬 Nigerian Data Seed — Starting...\n");

  try {
    await pool.query("SELECT 1");
    console.log("  ✓ Database connected\n");

    const AGENT_COUNT = 30;
    const CUSTOMER_COUNT = 50;
    const STORE_COUNT = 20;
    const PRODUCT_COUNT = 80;
    const ORDER_COUNT = 60;

    console.log("━━━ Seeding Core Data ━━━");
    await seedAgents(AGENT_COUNT);
    await seedCustomers(CUSTOMER_COUNT);

    console.log("\n━━━ Seeding Transactions & Activity ━━━");
    await seedTransactions(AGENT_COUNT, 200);
    await seedFraudAlerts(AGENT_COUNT);
    await seedAuditLog(AGENT_COUNT);
    await seedLoyaltyHistory(AGENT_COUNT);

    console.log("\n━━━ Seeding E-Commerce ━━━");
    await seedAgentStores(AGENT_COUNT, STORE_COUNT);
    await seedProducts(STORE_COUNT);
    await seedInventory(PRODUCT_COUNT);
    await seedOrders(CUSTOMER_COUNT, STORE_COUNT, ORDER_COUNT);
    await seedOrderItems(ORDER_COUNT, PRODUCT_COUNT);
    await seedProductReviews(PRODUCT_COUNT, CUSTOMER_COUNT);
    await seedDeliveryZones(STORE_COUNT);

    console.log("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
    console.log("🇳🇬 Seed Complete!");
    console.log(`   ${AGENT_COUNT} agents`);
    console.log(`   ${CUSTOMER_COUNT} customers`);
    console.log(`   200 transactions`);
    console.log(`   ${STORE_COUNT} agent stores`);
    console.log(`   ${PRODUCT_COUNT} products with inventory`);
    console.log(`   ${ORDER_COUNT} orders with ~150 order items`);
    console.log(`   40 product reviews`);
    console.log(`   15 fraud alerts`);
    console.log(`   50 audit log entries`);
    console.log(`   40 loyalty history entries`);
    console.log("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n");
  } catch (err) {
    console.error("Seed failed:", err);
    process.exit(1);
  } finally {
    await pool.end();
  }
}

main();
