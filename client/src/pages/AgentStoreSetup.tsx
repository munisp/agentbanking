import { useState } from "react";
import { trpc } from "@/lib/trpc";
import { haptic } from "@/lib/haptics";

const NIGERIAN_STATES = [
  "Abia", "Adamawa", "Akwa Ibom", "Anambra", "Bauchi", "Bayelsa", "Benue",
  "Borno", "Cross River", "Delta", "Ebonyi", "Edo", "Ekiti", "Enugu", "FCT",
  "Gombe", "Imo", "Jigawa", "Kaduna", "Kano", "Katsina", "Kebbi", "Kogi",
  "Kwara", "Lagos", "Nasarawa", "Niger", "Ogun", "Ondo", "Osun", "Oyo",
  "Plateau", "Rivers", "Sokoto", "Taraba", "Yobe", "Zamfara",
];

const STORE_CATEGORIES = [
  "Electronics", "Phones & Accessories", "Fashion", "Groceries",
  "Health & Beauty", "Home & Garden", "Auto Parts", "Books & Stationery",
  "Sports & Fitness", "Baby Products", "Computing", "Gaming",
  "Food & Beverages", "Building Materials", "Farming & Agriculture",
];

const DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"] as const;

export default function AgentStoreSetup() {
  const [step, setStep] = useState(1);
  const [form, setForm] = useState({
    storeName: "",
    description: "",
    phone: "",
    email: "",
    address: "",
    city: "",
    state: "",
    lga: "",
    categories: [] as string[],
    deliveryEnabled: true,
    pickupEnabled: true,
  });
  const [hours, setHours] = useState<Record<string, { open: string; close: string }>>({
    monday: { open: "08:00", close: "18:00" },
    tuesday: { open: "08:00", close: "18:00" },
    wednesday: { open: "08:00", close: "18:00" },
    thursday: { open: "08:00", close: "18:00" },
    friday: { open: "08:00", close: "18:00" },
    saturday: { open: "09:00", close: "16:00" },
  });

  const { data: existingStore } = trpc.agentStore.getMyStore.useQuery(
    { agentId: 1 }
  ) as any;

  const registerStore = trpc.agentStore.registerStore.useMutation({
    onSuccess: () => {
      haptic("success");
      setStep(4);
    },
  }) as any;

  const toggleCategory = (cat: string) => {
    setForm(prev => ({
      ...prev,
      categories: prev.categories.includes(cat)
        ? prev.categories.filter(c => c !== cat)
        : [...prev.categories, cat],
    }));
  };

  const handleSubmit = () => {
    registerStore.mutate({
      agentId: 1, // From auth context
      agentCode: "AGT001", // From auth context
      storeName: form.storeName,
      description: form.description || undefined,
      phone: form.phone || undefined,
      email: form.email || undefined,
      address: form.address || undefined,
      city: form.city || undefined,
      state: form.state || undefined,
      lga: form.lga || undefined,
      categories: form.categories,
      deliveryEnabled: form.deliveryEnabled,
      pickupEnabled: form.pickupEnabled,
      businessHours: hours,
    });
  };

  if (existingStore) {
    return (
      <div className="min-h-screen bg-gray-50 p-4 safe-top safe-bottom">
        <div className="max-w-2xl mx-auto space-y-6">
          <div className="bg-white rounded-2xl border p-6 text-center">
            <div className="text-5xl mb-3">🏪</div>
            <h1 className="text-2xl font-bold">{existingStore.storeName}</h1>
            <p className="text-gray-500 mt-1">Your store is live!</p>
            <div className="mt-4 inline-flex items-center gap-2 bg-green-50 text-green-700 px-4 py-2 rounded-full text-sm font-medium">
              <span className="w-2 h-2 bg-green-500 rounded-full" />
              {existingStore.status}
            </div>
            <p className="text-sm text-gray-400 mt-3">
              Store URL: /store/{existingStore.slug}
            </p>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="bg-white border rounded-xl p-4 text-center">
              <p className="text-2xl font-bold">{existingStore.totalSales}</p>
              <p className="text-xs text-gray-500">Total Sales</p>
            </div>
            <div className="bg-white border rounded-xl p-4 text-center">
              <p className="text-2xl font-bold">₦{Number(existingStore.totalRevenue).toLocaleString()}</p>
              <p className="text-xs text-gray-500">Revenue</p>
            </div>
            <div className="bg-white border rounded-xl p-4 text-center">
              <p className="text-2xl font-bold">{existingStore.reviewCount}</p>
              <p className="text-xs text-gray-500">Reviews</p>
            </div>
            <div className="bg-white border rounded-xl p-4 text-center">
              <p className="text-2xl font-bold">⭐ {Number(existingStore.averageRating).toFixed(1)}</p>
              <p className="text-xs text-gray-500">Rating</p>
            </div>
          </div>

          <div className="flex gap-3">
            <a
              href={`/store/${existingStore.slug}`}
              className="flex-1 px-4 py-3 bg-blue-600 text-white rounded-xl text-center font-medium touch-target"
            >
              View My Store
            </a>
            <a
              href="/ecommerce/storefront"
              className="flex-1 px-4 py-3 border rounded-xl text-center font-medium touch-target"
            >
              Manage Products
            </a>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 safe-top safe-bottom">
      {/* Progress Steps */}
      <div className="bg-white border-b sticky top-0 z-20 safe-top">
        <div className="max-w-2xl mx-auto px-4 py-3">
          <div className="flex items-center gap-2 mb-2">
            {[1, 2, 3].map(s => (
              <div key={s} className="flex items-center gap-2 flex-1">
                <div
                  className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold ${
                    s <= step
                      ? "bg-blue-600 text-white"
                      : "bg-gray-200 text-gray-500"
                  }`}
                >
                  {s}
                </div>
                {s < 3 && (
                  <div
                    className={`flex-1 h-1 rounded ${
                      s < step ? "bg-blue-600" : "bg-gray-200"
                    }`}
                  />
                )}
              </div>
            ))}
          </div>
          <p className="text-sm text-gray-500">
            {step === 1 && "Store Details"}
            {step === 2 && "Location & Hours"}
            {step === 3 && "Review & Launch"}
          </p>
        </div>
      </div>

      <div className="max-w-2xl mx-auto p-4 pb-24">
        {/* Step 1: Store Details */}
        {step === 1 && (
          <div className="space-y-4">
            <h2 className="text-xl font-bold">Create Your Online Store</h2>
            <p className="text-sm text-gray-500">
              Digitize your physical store and sell to customers online. Set up takes less than 5 minutes.
            </p>

            <div className="space-y-3">
              <div>
                <label className="text-sm font-medium text-gray-700 block mb-1">Store Name *</label>
                <input
                  placeholder="e.g. Mama Ngozi Electronics"
                  value={form.storeName}
                  onChange={e => setForm({ ...form, storeName: e.target.value })}
                  className="w-full px-4 py-3 border rounded-xl text-base touch-target"
                />
              </div>

              <div>
                <label className="text-sm font-medium text-gray-700 block mb-1">Description</label>
                <textarea
                  placeholder="Tell customers about your store..."
                  value={form.description}
                  onChange={e => setForm({ ...form, description: e.target.value })}
                  rows={3}
                  className="w-full px-4 py-3 border rounded-xl text-base"
                />
              </div>

              <div>
                <label className="text-sm font-medium text-gray-700 block mb-1">Phone</label>
                <input
                  type="tel"
                  placeholder="+234..."
                  value={form.phone}
                  onChange={e => setForm({ ...form, phone: e.target.value })}
                  className="w-full px-4 py-3 border rounded-xl text-base touch-target"
                />
              </div>

              <div>
                <label className="text-sm font-medium text-gray-700 block mb-1">Email</label>
                <input
                  type="email"
                  placeholder="store@example.com"
                  value={form.email}
                  onChange={e => setForm({ ...form, email: e.target.value })}
                  className="w-full px-4 py-3 border rounded-xl text-base touch-target"
                />
              </div>

              <div>
                <label className="text-sm font-medium text-gray-700 block mb-2">Categories</label>
                <div className="flex flex-wrap gap-2">
                  {STORE_CATEGORIES.map(cat => (
                    <button
                      key={cat}
                      onClick={() => { toggleCategory(cat); haptic("micro"); }}
                      className={`px-3 py-1.5 rounded-full text-sm border transition-colors ${
                        form.categories.includes(cat)
                          ? "bg-blue-600 text-white border-blue-600"
                          : "bg-white text-gray-700 border-gray-300"
                      }`}
                    >
                      {cat}
                    </button>
                  ))}
                </div>
              </div>

              <div className="flex gap-4 pt-2">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={form.deliveryEnabled}
                    onChange={e => setForm({ ...form, deliveryEnabled: e.target.checked })}
                    className="w-5 h-5 rounded"
                  />
                  <span className="text-sm">Offer Delivery</span>
                </label>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={form.pickupEnabled}
                    onChange={e => setForm({ ...form, pickupEnabled: e.target.checked })}
                    className="w-5 h-5 rounded"
                  />
                  <span className="text-sm">Offer Pickup</span>
                </label>
              </div>
            </div>
          </div>
        )}

        {/* Step 2: Location & Business Hours */}
        {step === 2 && (
          <div className="space-y-4">
            <h2 className="text-xl font-bold">Location & Business Hours</h2>

            <div className="space-y-3">
              <div>
                <label className="text-sm font-medium text-gray-700 block mb-1">Address</label>
                <input
                  placeholder="123 Market Road"
                  value={form.address}
                  onChange={e => setForm({ ...form, address: e.target.value })}
                  className="w-full px-4 py-3 border rounded-xl text-base touch-target"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-sm font-medium text-gray-700 block mb-1">City</label>
                  <input
                    placeholder="Lagos"
                    value={form.city}
                    onChange={e => setForm({ ...form, city: e.target.value })}
                    className="w-full px-4 py-3 border rounded-xl text-base touch-target"
                  />
                </div>
                <div>
                  <label className="text-sm font-medium text-gray-700 block mb-1">State</label>
                  <select
                    value={form.state}
                    onChange={e => setForm({ ...form, state: e.target.value })}
                    className="w-full px-4 py-3 border rounded-xl text-base touch-target"
                  >
                    <option value="">Select</option>
                    {NIGERIAN_STATES.map(s => (
                      <option key={s} value={s}>{s}</option>
                    ))}
                  </select>
                </div>
              </div>

              <div>
                <label className="text-sm font-medium text-gray-700 block mb-1">LGA</label>
                <input
                  placeholder="Ikeja"
                  value={form.lga}
                  onChange={e => setForm({ ...form, lga: e.target.value })}
                  className="w-full px-4 py-3 border rounded-xl text-base touch-target"
                />
              </div>
            </div>

            <div>
              <h3 className="font-medium text-sm text-gray-700 mb-2">Business Hours</h3>
              <div className="space-y-2">
                {DAYS.map(day => (
                  <div key={day} className="flex items-center gap-3">
                    <span className="w-24 text-sm capitalize text-gray-600">{day}</span>
                    {hours[day] ? (
                      <>
                        <input
                          type="time"
                          value={hours[day].open}
                          onChange={e => setHours(h => ({ ...h, [day]: { ...h[day], open: e.target.value } }))}
                          className="px-2 py-1.5 border rounded-lg text-sm"
                        />
                        <span className="text-gray-400">—</span>
                        <input
                          type="time"
                          value={hours[day].close}
                          onChange={e => setHours(h => ({ ...h, [day]: { ...h[day], close: e.target.value } }))}
                          className="px-2 py-1.5 border rounded-lg text-sm"
                        />
                        <button
                          onClick={() => setHours(h => { const n = { ...h }; delete n[day]; return n; })}
                          className="text-red-500 text-xs"
                        >
                          Closed
                        </button>
                      </>
                    ) : (
                      <button
                        onClick={() => setHours(h => ({ ...h, [day]: { open: "08:00", close: "18:00" } }))}
                        className="text-sm text-blue-600"
                      >
                        Set hours
                      </button>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Step 3: Review & Launch */}
        {step === 3 && (
          <div className="space-y-4">
            <h2 className="text-xl font-bold">Review & Launch</h2>

            <div className="bg-white border rounded-2xl p-5 space-y-4">
              <div className="text-center">
                <div className="text-5xl mb-2">🏪</div>
                <h3 className="text-lg font-bold">{form.storeName}</h3>
                {form.description && (
                  <p className="text-sm text-gray-500 mt-1">{form.description}</p>
                )}
              </div>

              <div className="border-t pt-3 space-y-2 text-sm">
                {form.city && (
                  <div className="flex justify-between">
                    <span className="text-gray-500">Location</span>
                    <span>{form.city}, {form.state}</span>
                  </div>
                )}
                {form.phone && (
                  <div className="flex justify-between">
                    <span className="text-gray-500">Phone</span>
                    <span>{form.phone}</span>
                  </div>
                )}
                {form.categories.length > 0 && (
                  <div className="flex justify-between">
                    <span className="text-gray-500">Categories</span>
                    <span className="text-right">{form.categories.join(", ")}</span>
                  </div>
                )}
                <div className="flex justify-between">
                  <span className="text-gray-500">Delivery</span>
                  <span>{form.deliveryEnabled ? "Yes" : "No"}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Pickup</span>
                  <span>{form.pickupEnabled ? "Yes" : "No"}</span>
                </div>
              </div>

              <div className="border-t pt-3">
                <p className="text-xs text-gray-400">
                  Platform commission: 5.00% on each sale + 7.5% VAT on commission.
                  You keep the rest!
                </p>
              </div>
            </div>

            {registerStore.error && (
              <div className="bg-red-50 border border-red-200 rounded-xl p-3 text-sm text-red-700">
                {(registerStore.error as any).message}
              </div>
            )}
          </div>
        )}

        {/* Step 4: Success */}
        {step === 4 && (
          <div className="text-center py-12 space-y-4">
            <div className="text-6xl">🎉</div>
            <h2 className="text-2xl font-bold">Store Created!</h2>
            <p className="text-gray-500">
              Your online store is now live. Start adding products to reach customers across Nigeria.
            </p>
            <div className="flex flex-col gap-3 max-w-xs mx-auto pt-4">
              <a
                href="/ecommerce/storefront"
                className="px-6 py-3 bg-blue-600 text-white rounded-xl font-medium touch-target"
              >
                Add Products
              </a>
              <a
                href="/ecommerce/mall"
                className="px-6 py-3 border rounded-xl font-medium touch-target"
              >
                View Mall
              </a>
            </div>
          </div>
        )}
      </div>

      {/* Bottom Nav */}
      {step <= 3 && (
        <div className="fixed bottom-0 left-0 right-0 bg-white border-t p-4 safe-bottom">
          <div className="max-w-2xl mx-auto flex gap-3">
            {step > 1 && (
              <button
                onClick={() => { setStep(step - 1); haptic("micro"); }}
                className="px-6 py-3 border rounded-xl font-medium touch-target"
              >
                Back
              </button>
            )}
            <button
              onClick={() => {
                haptic("micro");
                if (step < 3) setStep(step + 1);
                else handleSubmit();
              }}
              disabled={step === 1 && !form.storeName.trim()}
              className="flex-1 px-6 py-3 bg-blue-600 text-white rounded-xl font-medium touch-target disabled:opacity-50"
            >
              {step === 3
                ? registerStore.isPending
                  ? "Creating..."
                  : "Launch Store"
                : "Next"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
