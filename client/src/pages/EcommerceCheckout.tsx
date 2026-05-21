import { useState } from "react";
import { trpc } from "@/lib/trpc";
import { haptic } from "@/lib/haptics";

const STEPS = ["Shipping", "Payment", "Review"] as const;

export default function EcommerceCheckout() {
  const customerId = 1;
  const [step, setStep] = useState(0);
  const [paymentMethod, setPaymentMethod] = useState("card");
  const [submitting, setSubmitting] = useState(false);
  const [orderResult, setOrderResult] = useState<any>(null);

  const [address, setAddress] = useState({
    street: "",
    city: "",
    state: "",
    country: "Nigeria",
    zipCode: "",
    phone: "",
  });

  const { data: cart } = trpc.ecommerceCart.getCart.useQuery({
    customerId,
  }) as any;
  const createOrder = trpc.ecommerceOrders.createFromCart.useMutation({
    onSuccess: (data: any) => {
      setSubmitting(false);
      setOrderResult(data);
      haptic("success");
    },
    onError: () => {
      setSubmitting(false);
      haptic("error");
    },
  }) as any;

  const handleSubmit = () => {
    setSubmitting(true);
    createOrder.mutate({
      customerId,
      merchantId: 1,
      paymentMethod,
      shippingAddress: address,
    });
  };

  if (orderResult) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center p-6 max-w-lg mx-auto text-center space-y-4">
        <div className="w-20 h-20 rounded-full bg-green-100 flex items-center justify-center text-4xl text-green-600">
          ✓
        </div>
        <h1 className="text-2xl font-bold text-green-700">Order Placed!</h1>
        <p className="text-gray-600">Order #{orderResult.orderNumber}</p>
        <p className="text-lg font-medium">
          Total: {orderResult.currency}{" "}
          {Number(orderResult.total).toLocaleString()}
        </p>
        <div className="flex gap-3 justify-center mt-6">
          <a
            href="/ecommerce/orders"
            className="px-6 py-3 bg-blue-600 text-white rounded-xl font-medium touch-target"
          >
            View Orders
          </a>
          <a
            href="/ecommerce/catalog"
            className="px-6 py-3 border rounded-xl font-medium touch-target"
          >
            Continue Shopping
          </a>
        </div>
      </div>
    );
  }

  const subTotal = cart?.subTotal || 0;
  const tax = subTotal * 0.075;
  const shipping = subTotal >= 50000 ? 0 : 500;
  const total = subTotal + tax + shipping;

  return (
    <div className="min-h-screen flex flex-col bg-gray-50">
      {/* Step Indicator (P0) */}
      <div className="bg-white border-b safe-top">
        <div className="max-w-4xl mx-auto px-4 py-4">
          <h1 className="text-xl font-bold mb-3">Checkout</h1>
          <div className="flex items-center gap-2">
            {STEPS.map((s, i) => (
              <div key={s} className="flex items-center gap-2 flex-1">
                <button
                  onClick={() => {
                    if (i < step) {
                      setStep(i);
                      haptic("micro");
                    }
                  }}
                  className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold transition-all touch-target ${
                    i <= step
                      ? "bg-green-600 text-white"
                      : "bg-gray-200 text-gray-500"
                  }`}
                  aria-label={`Step ${i + 1}: ${s}`}
                  aria-current={i === step ? "step" : undefined}
                >
                  {i < step ? "✓" : i + 1}
                </button>
                <span
                  className={`text-xs font-medium ${i <= step ? "text-green-700" : "text-gray-400"}`}
                >
                  {s}
                </span>
                {i < STEPS.length - 1 && (
                  <div
                    className={`flex-1 h-0.5 rounded ${i < step ? "bg-green-500" : "bg-gray-200"}`}
                  />
                )}
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Step Content */}
      <div className="flex-1 overflow-y-auto pb-32">
        <div className="max-w-4xl mx-auto p-4">
          <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
            {/* Main Content */}
            <div className="lg:col-span-3">
              {/* Step 0: Shipping */}
              {step === 0 && (
                <div className="bg-white rounded-xl p-5 space-y-4 shadow-sm">
                  <h2 className="text-lg font-semibold">Shipping Address</h2>
                  <input
                    placeholder="Street Address"
                    value={address.street}
                    onChange={e =>
                      setAddress({ ...address, street: e.target.value })
                    }
                    required
                    autoComplete="street-address"
                    className="w-full px-4 py-3 border rounded-xl text-base touch-target"
                  />
                  <div className="grid grid-cols-2 gap-3">
                    <input
                      placeholder="City"
                      value={address.city}
                      onChange={e =>
                        setAddress({ ...address, city: e.target.value })
                      }
                      required
                      autoComplete="address-level2"
                      className="px-4 py-3 border rounded-xl text-base touch-target"
                    />
                    <input
                      placeholder="State"
                      value={address.state}
                      onChange={e =>
                        setAddress({ ...address, state: e.target.value })
                      }
                      required
                      autoComplete="address-level1"
                      className="px-4 py-3 border rounded-xl text-base touch-target"
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <input
                      placeholder="Zip Code"
                      value={address.zipCode}
                      onChange={e =>
                        setAddress({ ...address, zipCode: e.target.value })
                      }
                      required
                      autoComplete="postal-code"
                      inputMode="numeric"
                      className="px-4 py-3 border rounded-xl text-base touch-target"
                    />
                    <input
                      placeholder="Phone Number"
                      value={address.phone}
                      onChange={e =>
                        setAddress({ ...address, phone: e.target.value })
                      }
                      required
                      autoComplete="tel"
                      inputMode="tel"
                      type="tel"
                      className="px-4 py-3 border rounded-xl text-base touch-target"
                    />
                  </div>
                </div>
              )}

              {/* Step 1: Payment */}
              {step === 1 && (
                <div className="bg-white rounded-xl p-5 space-y-3 shadow-sm">
                  <h2 className="text-lg font-semibold">Payment Method</h2>
                  {[
                    {
                      value: "card",
                      label: "💳 Debit/Credit Card",
                      desc: "Visa, Mastercard",
                    },
                    {
                      value: "bank_transfer",
                      label: "🏦 Bank Transfer",
                      desc: "Direct bank payment",
                    },
                    {
                      value: "ussd",
                      label: "📱 USSD",
                      desc: "Pay via USSD code",
                    },
                    {
                      value: "mobile_money",
                      label: "📲 Mobile Money",
                      desc: "MTN MoMo, Airtel Money",
                    },
                    {
                      value: "cash_on_delivery",
                      label: "💵 Cash on Delivery",
                      desc: "Pay when delivered",
                    },
                  ].map(method => (
                    <label
                      key={method.value}
                      className={`flex items-center gap-3 p-4 border-2 rounded-xl cursor-pointer transition-all touch-target ${
                        paymentMethod === method.value
                          ? "border-green-500 bg-green-50"
                          : "border-gray-200 hover:border-gray-300"
                      }`}
                    >
                      <input
                        type="radio"
                        name="payment"
                        value={method.value}
                        checked={paymentMethod === method.value}
                        onChange={e => {
                          setPaymentMethod(e.target.value);
                          haptic("micro");
                        }}
                        className="w-5 h-5"
                      />
                      <div>
                        <span className="font-medium">{method.label}</span>
                        <p className="text-xs text-gray-500">{method.desc}</p>
                      </div>
                    </label>
                  ))}
                </div>
              )}

              {/* Step 2: Review */}
              {step === 2 && (
                <div className="bg-white rounded-xl p-5 space-y-4 shadow-sm">
                  <h2 className="text-lg font-semibold">Order Review</h2>
                  <div className="space-y-3">
                    <div className="p-3 bg-gray-50 rounded-lg">
                      <p className="text-xs text-gray-500 mb-1">Ship to</p>
                      <p className="text-sm font-medium">
                        {address.street}, {address.city}, {address.state}
                      </p>
                      <p className="text-xs text-gray-500">{address.phone}</p>
                    </div>
                    <div className="p-3 bg-gray-50 rounded-lg">
                      <p className="text-xs text-gray-500 mb-1">Payment</p>
                      <p className="text-sm font-medium capitalize">
                        {paymentMethod.replace(/_/g, " ")}
                      </p>
                    </div>
                  </div>
                  {cart?.items?.map((item: any) => (
                    <div
                      key={item.id}
                      className="flex justify-between text-sm py-2 border-b last:border-0"
                    >
                      <span>
                        {item.name} × {item.quantity}
                      </span>
                      <span className="font-medium">
                        ₦
                        {(
                          Number(item.unitPrice) * item.quantity
                        ).toLocaleString()}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Order Summary Sidebar (desktop) */}
            <div className="lg:col-span-2 hidden lg:block">
              <div className="bg-white rounded-xl p-5 shadow-sm space-y-3 sticky top-4">
                <h2 className="text-lg font-bold">Order Summary</h2>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span>Subtotal</span>
                    <span>₦{subTotal.toLocaleString()}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>VAT (7.5%)</span>
                    <span>₦{Math.round(tax).toLocaleString()}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Shipping</span>
                    <span>{shipping === 0 ? "Free" : `₦${shipping}`}</span>
                  </div>
                  <hr />
                  <div className="flex justify-between font-bold text-lg">
                    <span>Total</span>
                    <span>₦{Math.round(total).toLocaleString()}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Sticky Bottom CTA (P0: mobile-first) */}
      <div className="fixed bottom-0 left-0 right-0 bg-white border-t shadow-lg safe-bottom z-40">
        <div className="max-w-4xl mx-auto p-4">
          {/* Mobile order summary */}
          <div className="flex justify-between items-center mb-3 lg:hidden">
            <span className="text-sm text-gray-500">Total</span>
            <span className="text-lg font-bold">
              ₦{Math.round(total).toLocaleString()}
            </span>
          </div>
          <div className="flex gap-3">
            {step > 0 && (
              <button
                onClick={() => {
                  setStep(step - 1);
                  haptic("micro");
                }}
                className="px-6 py-3 border-2 rounded-xl font-medium text-gray-700 transition-all active:scale-95 touch-target"
              >
                Back
              </button>
            )}
            <button
              onClick={() => {
                if (step < 2) {
                  setStep(step + 1);
                  haptic("tap");
                } else {
                  handleSubmit();
                }
              }}
              disabled={submitting || !cart?.items?.length}
              className="flex-1 py-3 bg-green-600 text-white rounded-xl font-bold text-base hover:bg-green-700 disabled:opacity-50 transition-all active:scale-95 touch-target"
            >
              {submitting
                ? "Processing..."
                : step < 2
                  ? `Continue to ${STEPS[step + 1]}`
                  : `Pay ₦${Math.round(total).toLocaleString()}`}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
