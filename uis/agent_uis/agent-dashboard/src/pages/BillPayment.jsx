import {
    Calculator,
    CreditCard,
    Heart,
    Receipt,
    Smartphone,
    Tv,
    Wifi,
    Zap,
} from "lucide-react";
import React, { useState } from "react";

const NIGERIAN_ORGANIZATIONS = [
  {
    id: "rccg",
    name: "Redeemed Christian Church of God (RCCG)",
    type: "Religious",
    religion: "Christian",
    account: "0123456789",
    bank: "First Bank",
  },
  {
    id: "winners",
    name: "Living Faith Church (Winners Chapel)",
    type: "Religious",
    religion: "Christian",
    account: "0234567890",
    bank: "Zenith Bank",
  },
  {
    id: "deeper-life",
    name: "Deeper Life Bible Church",
    type: "Religious",
    religion: "Christian",
    account: "0345678901",
    bank: "GTBank",
  },
  {
    id: "mountain-fire",
    name: "Mountain of Fire and Miracles (MFM)",
    type: "Religious",
    religion: "Christian",
    account: "0456789012",
    bank: "Access Bank",
  },
  {
    id: "daystar",
    name: "Daystar Christian Centre",
    type: "Religious",
    religion: "Christian",
    account: "0567890123",
    bank: "UBA",
  },
  {
    id: "houseontherock",
    name: "The House On The Rock Church",
    type: "Religious",
    religion: "Christian",
    account: "0678901234",
    bank: "Stanbic IBTC",
  },
  {
    id: "christ-embassy",
    name: "Christ Embassy (Believers LoveWorld)",
    type: "Religious",
    religion: "Christian",
    account: "0789012345",
    bank: "First Bank",
  },
  {
    id: "salvation-ministries",
    name: "Salvation Ministries",
    type: "Religious",
    religion: "Christian",
    account: "0890123456",
    bank: "Zenith Bank",
  },
  {
    id: "nscia",
    name: "Nigerian Supreme Council for Islamic Affairs (NSCIA)",
    type: "Religious",
    religion: "Muslim",
    account: "0901234567",
    bank: "Jaiz Bank",
  },
  {
    id: "national-mosque",
    name: "National Mosque of Nigeria (Abuja)",
    type: "Religious",
    religion: "Muslim",
    account: "1012345678",
    bank: "First Bank",
  },
  {
    id: "central-mosque-lagos",
    name: "Lagos Central Mosque",
    type: "Religious",
    religion: "Muslim",
    account: "1123456789",
    bank: "Zenith Bank",
  },
  {
    id: "jibwis",
    name: "Jama'atu Izalatul Bid'ah Wa'ikamatis Sunnah (JIBWIS)",
    type: "Religious",
    religion: "Muslim",
    account: "1234567891",
    bank: "Jaiz Bank",
  },
  {
    id: "nasfat",
    name: "Nasrul-Lahi-l-Fatih Society (NASFAT)",
    type: "Religious",
    religion: "Muslim",
    account: "2345678902",
    bank: "GTBank",
  },
  {
    id: "ansar-ud-deen",
    name: "Ansar-Ud-Deen Society of Nigeria",
    type: "Religious",
    religion: "Muslim",
    account: "3456789013",
    bank: "Access Bank",
  },
  {
    id: "tariqa",
    name: "Tariqa Tijaniyya Foundation Nigeria",
    type: "Religious",
    religion: "Muslim",
    account: "4567890124",
    bank: "UBA",
  },
  {
    id: "red-cross",
    name: "Nigerian Red Cross Society",
    type: "NGO",
    account: "1234567890",
    bank: "GTBank",
  },
  {
    id: "unicef-nigeria",
    name: "UNICEF Nigeria",
    type: "NGO",
    account: "2345678901",
    bank: "First Bank",
  },
  {
    id: "sos-nigeria",
    name: "SOS Children's Villages Nigeria",
    type: "NGO",
    account: "3456789012",
    bank: "Access Bank",
  },
  {
    id: "nannm",
    name: "Nigerian Association of Nurses and Midwives (NANNM) Welfare Fund",
    type: "NGO",
    account: "4567890123",
    bank: "UBA",
  },
  {
    id: "actionaid",
    name: "ActionAid Nigeria",
    type: "NGO",
    account: "5678901234",
    bank: "Zenith Bank",
  },
  {
    id: "cece-yara",
    name: "Cece Yara Foundation (Child Protection)",
    type: "NGO",
    account: "6789012345",
    bank: "GTBank",
  },
  {
    id: "jos-widows",
    name: "Widows and Orphans Empowerment Organisation (WEWE)",
    type: "NGO",
    account: "7890123456",
    bank: "Stanbic IBTC",
  },
  {
    id: "project-pink-blue",
    name: "Project Pink Blue (Cancer Awareness)",
    type: "NGO",
    account: "8901234567",
    bank: "First Bank",
  },
  {
    id: "orphanage-lagos",
    name: "Lagos State Orphanage Support",
    type: "NGO",
    account: "9012345678",
    bank: "Access Bank",
  },
  {
    id: "slum2school",
    name: "Slum2School Africa",
    type: "NGO",
    account: "0123456780",
    bank: "Zenith Bank",
  },
];

const BillPayment = () => {
  const [selectedCategory, setSelectedCategory] = useState("electricity");
  const [selectedOrganization, setSelectedOrganization] = useState(null);
  const [organizationFilter, setOrganizationFilter] = useState("all");
  const [paymentForm, setPaymentForm] = useState({
    category: "electricity",
    provider: "",
    accountNumber: "",
    amount: "",
    customerName: "",
    taxpayerName: "",
    tin: "",
    invoiceNumber: "",
    taxPeriod: "",
    description: "",
  });

  const VAT_RATE = 0.075;
  const taxableAmount = Number(paymentForm.amount || 0);
  const vatAmount =
    selectedCategory === "vat"
      ? Number((taxableAmount * VAT_RATE).toFixed(2))
      : 0;
  const vatTotalAmount = Number((taxableAmount + vatAmount).toFixed(2));

  const categories = [
    {
      id: "electricity",
      name: "Electricity",
      icon: Zap,
      color: "bg-yellow-100 text-yellow-600",
    },
    {
      id: "airtime",
      name: "Airtime",
      icon: Smartphone,
      color: "bg-green-100 text-green-600",
    },
    {
      id: "data",
      name: "Data",
      icon: Wifi,
      color: "bg-[#E8F4F8] text-[var(--tenant-primary-color,#002082)]",
    },
    {
      id: "cable",
      name: "Cable TV",
      icon: Tv,
      color: "bg-purple-100 text-purple-600",
    },
    {
      id: "giving",
      name: "Giving/Donate",
      icon: Heart,
      color: "bg-pink-100 text-pink-600",
    },
    {
      id: "vat",
      name: "Nigerian VAT",
      icon: Calculator,
      color: "bg-[#E8F4F8] text-[var(--tenant-primary-color,#002082)]",
    },
  ];

  const providers = {
    electricity: ["IKEDC", "EKEDC", "AEDC", "PHED", "KAEDC"],
    airtime: ["MTN", "Glo", "Airtel", "9mobile"],
    data: ["MTN Data", "Glo Data", "Airtel Data", "9mobile Data"],
    cable: ["DSTV", "GOtv", "StarTimes", "ShowMax"],
  };

  const recentPayments = [
    {
      id: 1,
      type: "Electricity",
      provider: "IKEDC",
      amount: 15000,
      date: "2026-02-20",
      status: "completed",
    },
    {
      id: 2,
      type: "Airtime",
      provider: "MTN",
      amount: 5000,
      date: "2026-02-19",
      status: "completed",
    },
    {
      id: 3,
      type: "Data",
      provider: "Airtel Data",
      amount: 3000,
      date: "2026-02-18",
      status: "completed",
    },
    {
      id: 4,
      type: "Cable TV",
      provider: "DSTV",
      amount: 8500,
      date: "2026-02-17",
      status: "completed",
    },
  ];

  const handleSubmit = (e) => {
    e.preventDefault();

    if (selectedCategory === "giving") {
      const org = NIGERIAN_ORGANIZATIONS.find(
        (o) => o.id === selectedOrganization,
      );
      console.log("Donation:", {
        category: "giving",
        organization_name: org?.name,
        organization_type: org?.type,
        amount: paymentForm.amount,
        account: org?.account,
        bank: org?.bank,
      });
      return;
    }

    if (selectedCategory === "vat") {
      if (
        !paymentForm.taxpayerName ||
        !paymentForm.tin ||
        !paymentForm.invoiceNumber ||
        !paymentForm.taxPeriod ||
        !paymentForm.amount
      ) {
        console.log("VAT payment validation failed");
        return;
      }

      console.log("VAT Payment:", {
        category: "vat",
        transaction_type: "BILL_PAYMENT",
        taxpayer_name: paymentForm.taxpayerName,
        tin: paymentForm.tin,
        invoice_number: paymentForm.invoiceNumber,
        tax_period: paymentForm.taxPeriod,
        description: paymentForm.description,
        tax_rate: VAT_RATE,
        taxable_amount: taxableAmount,
        vat_amount: vatAmount,
        total_amount: vatTotalAmount,
      });
      return;
    }

    console.log("Payment:", paymentForm);
    // Handle payment logic
  };

  const getFilteredOrganizations = () => {
    if (organizationFilter === "all") return NIGERIAN_ORGANIZATIONS;
    return NIGERIAN_ORGANIZATIONS.filter(
      (org) => org.type.toLowerCase() === organizationFilter,
    );
  };

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setPaymentForm((prev) => ({ ...prev, [name]: value }));
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Bill Payment</h1>
        <p className="text-gray-600 mt-1">
          Pay utility bills, VAT, airtime, data, and more
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Payment Form */}
        <div className="lg:col-span-2">
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-6">
              New Payment
            </h2>

            {/* Category Selection */}
            <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-6">
              {categories.map((category) => (
                <button
                  key={category.id}
                  type="button"
                  onClick={() => {
                    setSelectedCategory(category.id);
                    setSelectedOrganization(null);
                    setPaymentForm((prev) => ({
                      ...prev,
                      category: category.id,
                      provider: "",
                    }));
                  }}
                  className={`flex flex-col items-center p-4 border-2 rounded-lg transition-all ${
                    selectedCategory === category.id
                      ? "border-[var(--tenant-primary-color,#002082)] bg-[#E8F4F8]"
                      : "border-gray-200 hover:border-gray-300"
                  }`}
                >
                  <div className={`p-3 rounded-lg mb-2 ${category.color}`}>
                    <category.icon className="h-6 w-6" />
                  </div>
                  <span className="text-sm font-medium">{category.name}</span>
                </button>
              ))}
            </div>

            {selectedCategory === "vat" && (
              <div className="mb-6 rounded-xl border border-[#D6EAF2] bg-[#F4FAFC] p-4">
                <p className="text-sm font-semibold text-[var(--tenant-primary-color,#002082)]">
                  Nigerian VAT collections
                </p>
                <p className="text-sm text-gray-600 mt-1">
                  VAT is calculated at 7.5% of the taxable amount before
                  submission.
                </p>
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-4">
              {/* Giving/Donation Form */}
              {selectedCategory === "giving" && (
                <div className="space-y-4">
                  {/* Organization Filter */}
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Organization Type
                    </label>
                    <div className="flex gap-2">
                      <button
                        type="button"
                        onClick={() => setOrganizationFilter("all")}
                        className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                          organizationFilter === "all"
                            ? "bg-[var(--tenant-primary-color,#002082)] text-white"
                            : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                        }`}
                      >
                        All
                      </button>
                      <button
                        type="button"
                        onClick={() => setOrganizationFilter("religious")}
                        className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                          organizationFilter === "religious"
                            ? "bg-[var(--tenant-primary-color,#002082)] text-white"
                            : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                        }`}
                      >
                        Religious
                      </button>
                      <button
                        type="button"
                        onClick={() => setOrganizationFilter("ngo")}
                        className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                          organizationFilter === "ngo"
                            ? "bg-[var(--tenant-primary-color,#002082)] text-white"
                            : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                        }`}
                      >
                        NGOs
                      </button>
                    </div>
                  </div>

                  {/* Organization Selection */}
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Choose Where to Give
                    </label>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3 max-h-96 overflow-y-auto">
                      {getFilteredOrganizations().map((org) => (
                        <button
                          key={org.id}
                          type="button"
                          onClick={() => setSelectedOrganization(org.id)}
                          className={`p-4 border-2 rounded-lg text-left transition-all ${
                            selectedOrganization === org.id
                              ? "border-[var(--tenant-primary-color,#002082)] bg-[#E8F4F8]"
                              : "border-gray-200 hover:border-gray-300"
                          }`}
                        >
                          <div className="flex justify-between items-start mb-2">
                            <div className="flex-1">
                              <p className="font-medium text-sm text-gray-900">
                                {org.name}
                              </p>
                              <p className="text-xs text-gray-500 mt-1">
                                {org.bank} • {org.account}
                              </p>
                            </div>
                            <span className="px-2 py-1 bg-gray-100 text-gray-600 text-xs rounded">
                              {org.type === "Religious"
                                ? org.religion
                                : org.type}
                            </span>
                          </div>
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Amount */}
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Donation Amount
                    </label>
                    <div className="relative">
                      <span className="absolute left-4 top-1/2 transform -translate-y-1/2 text-gray-500">
                        ₦
                      </span>
                      <input
                        type="number"
                        name="amount"
                        value={paymentForm.amount}
                        onChange={handleInputChange}
                        required
                        placeholder="0.00"
                        min="100"
                        className="w-full pl-8 pr-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[var(--tenant-primary-color,#002082)] focus:border-transparent"
                      />
                    </div>
                  </div>

                  {/* Submit Button for Donation */}
                  <button
                    type="submit"
                    disabled={!selectedOrganization || !paymentForm.amount}
                    className="w-full flex items-center justify-center px-6 py-3 bg-pink-600 text-white rounded-lg hover:bg-pink-700 transition-colors font-medium disabled:bg-gray-300 disabled:cursor-not-allowed"
                  >
                    <Heart className="h-5 w-5 mr-2" />
                    Complete Donation
                  </button>
                </div>
              )}

              {/* VAT Form */}
              {selectedCategory === "vat" && (
                <div className="space-y-4">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        Taxpayer Name
                      </label>
                      <input
                        type="text"
                        name="taxpayerName"
                        value={paymentForm.taxpayerName}
                        onChange={handleInputChange}
                        required
                        placeholder="Company or individual name"
                        className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[var(--tenant-primary-color,#002082)] focus:border-transparent"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        TIN
                      </label>
                      <input
                        type="text"
                        name="tin"
                        value={paymentForm.tin}
                        onChange={handleInputChange}
                        required
                        placeholder="Tax Identification Number"
                        className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[var(--tenant-primary-color,#002082)] focus:border-transparent"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        Invoice / Assessment Number
                      </label>
                      <input
                        type="text"
                        name="invoiceNumber"
                        value={paymentForm.invoiceNumber}
                        onChange={handleInputChange}
                        required
                        placeholder="VAT invoice reference"
                        className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[var(--tenant-primary-color,#002082)] focus:border-transparent"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        Tax Period
                      </label>
                      <input
                        type="text"
                        name="taxPeriod"
                        value={paymentForm.taxPeriod}
                        onChange={handleInputChange}
                        required
                        placeholder="e.g. Q1 2026"
                        className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[var(--tenant-primary-color,#002082)] focus:border-transparent"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Taxable Amount
                    </label>
                    <div className="relative">
                      <span className="absolute left-4 top-1/2 transform -translate-y-1/2 text-gray-500">
                        ₦
                      </span>
                      <input
                        type="number"
                        name="amount"
                        value={paymentForm.amount}
                        onChange={handleInputChange}
                        required
                        placeholder="0.00"
                        min="1"
                        className="w-full pl-8 pr-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[var(--tenant-primary-color,#002082)] focus:border-transparent"
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div className="rounded-xl border border-gray-200 bg-white p-4">
                      <p className="text-xs text-gray-500">VAT rate</p>
                      <p className="text-lg font-semibold text-gray-900">
                        7.5%
                      </p>
                    </div>
                    <div className="rounded-xl border border-gray-200 bg-white p-4">
                      <p className="text-xs text-gray-500">VAT amount</p>
                      <p className="text-lg font-semibold text-gray-900">
                        ₦{vatAmount.toLocaleString()}
                      </p>
                    </div>
                    <div className="rounded-xl border border-gray-200 bg-white p-4">
                      <p className="text-xs text-gray-500">Total payable</p>
                      <p className="text-lg font-semibold text-gray-900">
                        ₦{vatTotalAmount.toLocaleString()}
                      </p>
                    </div>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Description
                    </label>
                    <textarea
                      name="description"
                      value={paymentForm.description}
                      onChange={handleInputChange}
                      rows="3"
                      placeholder="Optional VAT payment notes"
                      className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[var(--tenant-primary-color,#002082)] focus:border-transparent"
                    />
                  </div>

                  <button
                    type="submit"
                    disabled={
                      !paymentForm.taxpayerName ||
                      !paymentForm.tin ||
                      !paymentForm.invoiceNumber ||
                      !paymentForm.taxPeriod ||
                      !paymentForm.amount
                    }
                    className="w-full flex items-center justify-center px-6 py-3 bg-[var(--tenant-primary-color,#002082)] text-white rounded-lg hover:bg-[var(--tenant-primary-color,#003047)] transition-colors font-medium disabled:bg-gray-300 disabled:cursor-not-allowed"
                  >
                    <Calculator className="h-5 w-5 mr-2" />
                    Submit VAT Payment
                  </button>
                </div>
              )}

              {/* Regular Bill Payment Form */}
              {selectedCategory !== "giving" && selectedCategory !== "vat" && (
                <>
                  {/* Provider */}
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Provider
                    </label>
                    <select
                      name="provider"
                      value={paymentForm.provider}
                      onChange={handleInputChange}
                      required
                      className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[var(--tenant-primary-color,#002082)] focus:border-transparent"
                    >
                      <option value="">Select provider</option>
                      {providers[selectedCategory].map((provider) => (
                        <option key={provider} value={provider}>
                          {provider}
                        </option>
                      ))}
                    </select>
                  </div>

                  {/* Account Number / Phone Number */}
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      {selectedCategory === "airtime" ||
                      selectedCategory === "data"
                        ? "Phone Number"
                        : selectedCategory === "cable"
                          ? "Smart Card Number"
                          : "Meter Number"}
                    </label>
                    <input
                      type="text"
                      name="accountNumber"
                      value={paymentForm.accountNumber}
                      onChange={handleInputChange}
                      required
                      placeholder={
                        selectedCategory === "airtime" ||
                        selectedCategory === "data"
                          ? "080XXXXXXXX"
                          : selectedCategory === "cable"
                            ? "Enter smart card number"
                            : "Enter meter number"
                      }
                      className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[var(--tenant-primary-color,#002082)] focus:border-transparent"
                    />
                  </div>

                  {/* Customer Name (auto-populated in real scenario) */}
                  {(selectedCategory === "electricity" ||
                    selectedCategory === "cable") && (
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        Customer Name
                      </label>
                      <input
                        type="text"
                        name="customerName"
                        value={paymentForm.customerName}
                        onChange={handleInputChange}
                        placeholder="Will be auto-filled after verification"
                        className="w-full px-4 py-3 border border-gray-300 rounded-lg bg-gray-50"
                        disabled
                      />
                    </div>
                  )}

                  {/* Amount */}
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Amount
                    </label>
                    {selectedCategory === "data" ? (
                      <select
                        name="amount"
                        value={paymentForm.amount}
                        onChange={handleInputChange}
                        required
                        className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[var(--tenant-primary-color,#002082)] focus:border-transparent"
                      >
                        <option value="">Select data plan</option>
                        <option value="1000">1GB - ₦1,000</option>
                        <option value="2000">2GB - ₦2,000</option>
                        <option value="3000">5GB - ₦3,000</option>
                        <option value="5000">10GB - ₦5,000</option>
                      </select>
                    ) : (
                      <div className="relative">
                        <span className="absolute left-4 top-1/2 transform -translate-y-1/2 text-gray-500">
                          ₦
                        </span>
                        <input
                          type="number"
                          name="amount"
                          value={paymentForm.amount}
                          onChange={handleInputChange}
                          required
                          placeholder="0.00"
                          min="100"
                          className="w-full pl-8 pr-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[var(--tenant-primary-color,#002082)] focus:border-transparent"
                        />
                      </div>
                    )}
                  </div>

                  {/* Submit Button */}
                  <button
                    type="submit"
                    className="w-full flex items-center justify-center px-6 py-3 bg-[var(--tenant-primary-color,#002082)] text-white rounded-lg hover:bg-[var(--tenant-primary-color,#003047)] transition-colors font-medium"
                  >
                    <CreditCard className="h-5 w-5 mr-2" />
                    Make Payment
                  </button>
                </>
              )}
            </form>
          </div>
        </div>

        {/* Recent Payments */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">
            Recent Payments
          </h2>
          <div className="space-y-4">
            {recentPayments.map((payment) => (
              <div key={payment.id} className="p-4 bg-gray-50 rounded-lg">
                <div className="flex items-start justify-between mb-2">
                  <div>
                    <p className="font-medium text-gray-900 text-sm">
                      {payment.type}
                    </p>
                    <p className="text-xs text-gray-500">{payment.provider}</p>
                  </div>
                  <Receipt className="h-4 w-4 text-gray-400" />
                </div>
                <div className="flex justify-between items-center mt-2">
                  <span className="text-sm font-semibold text-gray-900">
                    ₦{payment.amount.toLocaleString()}
                  </span>
                  <span className="text-xs text-gray-500">{payment.date}</span>
                </div>
                <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800 mt-2">
                  {payment.status}
                </span>
              </div>
            ))}
          </div>
          <button className="w-full mt-4 px-4 py-2 text-sm text-[var(--tenant-primary-color,#002082)] hover:bg-[#E8F4F8] rounded-lg transition-colors font-medium">
            View All Payments
          </button>
        </div>
      </div>
    </div>
  );
};

export default BillPayment;
