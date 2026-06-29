import { useState } from "react";
import { haptic } from "@/lib/haptics";
import DashboardLayout from "@/components/DashboardLayout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

const NIGERIAN_STATES = [
  "Abia",
  "Adamawa",
  "Akwa Ibom",
  "Anambra",
  "Bauchi",
  "Bayelsa",
  "Benue",
  "Borno",
  "Cross River",
  "Delta",
  "Ebonyi",
  "Edo",
  "Ekiti",
  "Enugu",
  "FCT",
  "Gombe",
  "Imo",
  "Jigawa",
  "Kaduna",
  "Kano",
  "Katsina",
  "Kebbi",
  "Kogi",
  "Kwara",
  "Lagos",
  "Nasarawa",
  "Niger",
  "Ogun",
  "Ondo",
  "Osun",
  "Oyo",
  "Plateau",
  "Rivers",
  "Sokoto",
  "Taraba",
  "Yobe",
  "Zamfara",
];

const STORE_CATEGORIES = [
  "Electronics",
  "Phones & Accessories",
  "Fashion",
  "Groceries",
  "Health & Beauty",
  "Home & Garden",
  "Auto Parts",
  "Books & Stationery",
  "Sports & Fitness",
  "Baby Products",
  "Computing",
  "Gaming",
  "Food & Beverages",
  "Building Materials",
  "Farming & Agriculture",
];

const DAYS = [
  "monday",
  "tuesday",
  "wednesday",
  "thursday",
  "friday",
  "saturday",
  "sunday",
] as const;

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
  const [hours, setHours] = useState<
    Record<string, { open: string; close: string }>
  >({
    monday: { open: "08:00", close: "18:00" },
    tuesday: { open: "08:00", close: "18:00" },
    wednesday: { open: "08:00", close: "18:00" },
    thursday: { open: "08:00", close: "18:00" },
    friday: { open: "08:00", close: "18:00" },
    saturday: { open: "09:00", close: "16:00" },
  });

  const { data: existingStore } = {data: null, isLoading: false, refetch: () => {}};

  const registerStore = {
    mutate: () => { haptic("success"); setStep(4); },
    mutateAsync: async () => { haptic("success"); setStep(4); },
    isPending: false, isLoading: false,
  } as any;

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
      agentId: 1,
      agentCode: "AGT001",
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
      <DashboardLayout>
        <div className="p-6 space-y-6">
          <div>
            <h1 className="text-2xl font-bold text-foreground">Store Setup</h1>
            <p className="text-muted-foreground">
              Manage your online storefront
            </p>
          </div>

          <Card>
            <CardContent className="pt-6 text-center">
              <div className="text-5xl mb-3">🏪</div>
              <h2 className="text-2xl font-bold text-foreground">
                {existingStore.storeName}
              </h2>
              <p className="text-muted-foreground mt-1">Your store is live!</p>
              <Badge
                variant="outline"
                className="mt-4 bg-green-500/10 text-green-500 border-green-500/20"
              >
                <span className="w-2 h-2 bg-green-500 rounded-full mr-2" />
                {existingStore.status}
              </Badge>
              <p className="text-sm text-muted-foreground mt-3">
                Store URL: /store/{existingStore.slug}
              </p>
            </CardContent>
          </Card>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <Card>
              <CardContent className="pt-4 text-center">
                <p className="text-2xl font-bold text-foreground">
                  {existingStore.totalSales}
                </p>
                <p className="text-xs text-muted-foreground">Total Sales</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-4 text-center">
                <p className="text-2xl font-bold text-foreground">
                  ₦{Number(existingStore.totalRevenue).toLocaleString()}
                </p>
                <p className="text-xs text-muted-foreground">Revenue</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-4 text-center">
                <p className="text-2xl font-bold text-foreground">
                  {existingStore.reviewCount}
                </p>
                <p className="text-xs text-muted-foreground">Reviews</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-4 text-center">
                <p className="text-2xl font-bold text-foreground">
                  {Number(existingStore.averageRating).toFixed(1)}
                </p>
                <p className="text-xs text-muted-foreground">Rating</p>
              </CardContent>
            </Card>
          </div>

          <div className="flex gap-3">
            <Button asChild className="flex-1">
              <a href={`/store/${existingStore.slug}`}>View My Store</a>
            </Button>
            <Button asChild variant="outline" className="flex-1">
              <a href="/ecommerce/storefront">Manage Products</a>
            </Button>
          </div>
        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout>
      <div className="p-6 space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Store Setup</h1>
          <p className="text-muted-foreground">
            Digitize your physical store and sell to customers online
          </p>
        </div>

        {/* Progress Steps */}
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 mb-2">
              {[1, 2, 3].map(s => (
                <div key={s} className="flex items-center gap-2 flex-1">
                  <div
                    className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold ${
                      s <= step
                        ? "bg-primary text-primary-foreground"
                        : "bg-muted text-muted-foreground"
                    }`}
                  >
                    {s}
                  </div>
                  {s < 3 && (
                    <div
                      className={`flex-1 h-1 rounded ${
                        s < step ? "bg-primary" : "bg-muted"
                      }`}
                    />
                  )}
                </div>
              ))}
            </div>
            <p className="text-sm text-muted-foreground">
              {step === 1 && "Store Details"}
              {step === 2 && "Location & Hours"}
              {step === 3 && "Review & Launch"}
            </p>
          </CardContent>
        </Card>

        {/* Step 1: Store Details */}
        {step === 1 && (
          <Card>
            <CardHeader>
              <CardTitle>Create Your Online Store</CardTitle>
              <p className="text-sm text-muted-foreground">
                Set up takes less than 5 minutes.
              </p>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <label className="text-sm font-medium text-foreground block mb-1">
                  Store Name *
                </label>
                <Input
                  placeholder="e.g. Mama Ngozi Electronics"
                  value={form.storeName}
                  onChange={e =>
                    setForm({ ...form, storeName: e.target.value })
                  }
                />
              </div>

              <div>
                <label className="text-sm font-medium text-foreground block mb-1">
                  Description
                </label>
                <textarea
                  placeholder="Tell customers about your store..."
                  value={form.description}
                  onChange={e =>
                    setForm({ ...form, description: e.target.value })
                  }
                  rows={3}
                  className="w-full px-3 py-2 border border-input bg-background rounded-md text-sm text-foreground placeholder:text-muted-foreground"
                />
              </div>

              <div>
                <label className="text-sm font-medium text-foreground block mb-1">
                  Phone
                </label>
                <Input
                  type="tel"
                  placeholder="+234..."
                  value={form.phone}
                  onChange={e => setForm({ ...form, phone: e.target.value })}
                />
              </div>

              <div>
                <label className="text-sm font-medium text-foreground block mb-1">
                  Email
                </label>
                <Input
                  type="email"
                  placeholder="store@example.com"
                  value={form.email}
                  onChange={e => setForm({ ...form, email: e.target.value })}
                />
              </div>

              <div>
                <label className="text-sm font-medium text-foreground block mb-2">
                  Categories
                </label>
                <div className="flex flex-wrap gap-2">
                  {STORE_CATEGORIES.map(cat => (
                    <button
                      key={cat}
                      onClick={() => {
                        toggleCategory(cat);
                        haptic("micro");
                      }}
                      className={`px-3 py-1.5 rounded-full text-sm border transition-colors ${
                        form.categories.includes(cat)
                          ? "bg-primary text-primary-foreground border-primary"
                          : "bg-card text-foreground border-border hover:bg-accent"
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
                    onChange={e =>
                      setForm({ ...form, deliveryEnabled: e.target.checked })
                    }
                    className="w-5 h-5 rounded"
                  />
                  <span className="text-sm text-foreground">
                    Offer Delivery
                  </span>
                </label>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={form.pickupEnabled}
                    onChange={e =>
                      setForm({ ...form, pickupEnabled: e.target.checked })
                    }
                    className="w-5 h-5 rounded"
                  />
                  <span className="text-sm text-foreground">Offer Pickup</span>
                </label>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Step 2: Location & Business Hours */}
        {step === 2 && (
          <Card>
            <CardHeader>
              <CardTitle>Location & Business Hours</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <label className="text-sm font-medium text-foreground block mb-1">
                  Address
                </label>
                <Input
                  placeholder="123 Market Road"
                  value={form.address}
                  onChange={e => setForm({ ...form, address: e.target.value })}
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-sm font-medium text-foreground block mb-1">
                    City
                  </label>
                  <Input
                    placeholder="Lagos"
                    value={form.city}
                    onChange={e => setForm({ ...form, city: e.target.value })}
                  />
                </div>
                <div>
                  <label className="text-sm font-medium text-foreground block mb-1">
                    State
                  </label>
                  <select
                    value={form.state}
                    onChange={e => setForm({ ...form, state: e.target.value })}
                    className="w-full h-10 px-3 border border-input bg-background rounded-md text-sm text-foreground"
                  >
                    <option value="">Select</option>
                    {NIGERIAN_STATES.map(s => (
                      <option key={s} value={s}>
                        {s}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div>
                <label className="text-sm font-medium text-foreground block mb-1">
                  LGA
                </label>
                <Input
                  placeholder="Ikeja"
                  value={form.lga}
                  onChange={e => setForm({ ...form, lga: e.target.value })}
                />
              </div>

              <div>
                <h3 className="font-medium text-sm text-foreground mb-2">
                  Business Hours
                </h3>
                <div className="space-y-2">
                  {DAYS.map(day => (
                    <div key={day} className="flex items-center gap-3">
                      <span className="w-24 text-sm capitalize text-muted-foreground">
                        {day}
                      </span>
                      {hours[day] ? (
                        <>
                          <input
                            type="time"
                            value={hours[day].open}
                            onChange={e =>
                              setHours(h => ({
                                ...h,
                                [day]: { ...h[day], open: e.target.value },
                              }))
                            }
                            className="px-2 py-1.5 border border-input bg-background rounded-lg text-sm text-foreground"
                          />
                          <span className="text-muted-foreground">—</span>
                          <input
                            type="time"
                            value={hours[day].close}
                            onChange={e =>
                              setHours(h => ({
                                ...h,
                                [day]: { ...h[day], close: e.target.value },
                              }))
                            }
                            className="px-2 py-1.5 border border-input bg-background rounded-lg text-sm text-foreground"
                          />
                          <button
                            onClick={() =>
                              setHours(h => {
                                const n = { ...h };
                                delete n[day];
                                return n;
                              })
                            }
                            className="text-destructive text-xs"
                          >
                            Closed
                          </button>
                        </>
                      ) : (
                        <button
                          onClick={() =>
                            setHours(h => ({
                              ...h,
                              [day]: { open: "08:00", close: "18:00" },
                            }))
                          }
                          className="text-sm text-primary"
                        >
                          Set hours
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Step 3: Review & Launch */}
        {step === 3 && (
          <Card>
            <CardHeader>
              <CardTitle>Review & Launch</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="text-center">
                <div className="text-5xl mb-2">🏪</div>
                <h3 className="text-lg font-bold text-foreground">
                  {form.storeName}
                </h3>
                {form.description && (
                  <p className="text-sm text-muted-foreground mt-1">
                    {form.description}
                  </p>
                )}
              </div>

              <div className="border-t border-border pt-3 space-y-2 text-sm">
                {form.city && (
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Location</span>
                    <span className="text-foreground">
                      {form.city}, {form.state}
                    </span>
                  </div>
                )}
                {form.phone && (
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Phone</span>
                    <span className="text-foreground">{form.phone}</span>
                  </div>
                )}
                {form.categories.length > 0 && (
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Categories</span>
                    <span className="text-foreground text-right">
                      {form.categories.join(", ")}
                    </span>
                  </div>
                )}
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Delivery</span>
                  <span className="text-foreground">
                    {form.deliveryEnabled ? "Yes" : "No"}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Pickup</span>
                  <span className="text-foreground">
                    {form.pickupEnabled ? "Yes" : "No"}
                  </span>
                </div>
              </div>

              <div className="border-t border-border pt-3">
                <p className="text-xs text-muted-foreground">
                  Platform commission: 5.00% on each sale + 7.5% VAT on
                  commission. You keep the rest!
                </p>
              </div>

              {registerStore.error && (
                <div className="bg-destructive/10 border border-destructive/20 rounded-lg p-3 text-sm text-destructive">
                  {(registerStore.error as any).message}
                </div>
              )}
            </CardContent>
          </Card>
        )}

        {/* Step 4: Success */}
        {step === 4 && (
          <Card>
            <CardContent className="pt-6 text-center py-12 space-y-4">
              <div className="text-6xl">🎉</div>
              <h2 className="text-2xl font-bold text-foreground">
                Store Created!
              </h2>
              <p className="text-muted-foreground">
                Your online store is now live. Start adding products to reach
                customers across Nigeria.
              </p>
              <div className="flex flex-col gap-3 max-w-xs mx-auto pt-4">
                <Button asChild>
                  <a href="/ecommerce/storefront">Add Products</a>
                </Button>
                <Button asChild variant="outline">
                  <a href="/ecommerce/mall">View Mall</a>
                </Button>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Navigation Buttons */}
        {step <= 3 && (
          <div className="flex gap-3">
            {step > 1 && (
              <Button
                variant="outline"
                onClick={() => {
                  setStep(step - 1);
                  haptic("micro");
                }}
              >
                Back
              </Button>
            )}
            <Button
              className="flex-1"
              onClick={() => {
                haptic("micro");
                if (step < 3) setStep(step + 1);
                else handleSubmit();
              }}
              disabled={step === 1 && !form.storeName.trim()}
            >
              {step === 3
                ? registerStore.isPending
                  ? "Creating..."
                  : "Launch Store"
                : "Next"}
            </Button>
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}
