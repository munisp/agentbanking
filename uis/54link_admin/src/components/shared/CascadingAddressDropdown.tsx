import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { addressData } from "@/lib/addressData";
import { useEffect, useMemo } from "react";

export interface City {
  name: string;
}

export interface State {
  name: string;
  cities: City[];
}

export interface Country {
  name: string;
  code: string;
  states: State[];
}

interface CascadingAddressDropdownProps {
  country: string;
  state: string;
  city: string;
  onCountryChange: (value: string) => void;
  onStateChange: (value: string) => void;
  onCityChange: (value: string) => void;
  primaryColor?: string;
  disabled?: boolean;
}

export default function CascadingAddressDropdown({
  country,
  state,
  city,
  onCountryChange,
  onStateChange,
  onCityChange,
  primaryColor,
  disabled = false,
}: CascadingAddressDropdownProps) {
  // Focus on Nigeria only
  const nigeriaData = useMemo(() => {
    return addressData.find((c) => c.name === "Nigeria");
  }, []);

  // Get available states from Nigeria
  const availableStates = useMemo(() => {
    return nigeriaData?.states || [];
  }, [nigeriaData]);

  // Get available cities based on selected state
  const availableCities = useMemo(() => {
    if (!state) return [];
    const selectedState = availableStates.find((s) => s.name === state);
    return selectedState?.cities.map((c) => c.name) || [];
  }, [state, availableStates]);

  // Auto-set country to Nigeria on mount
  useEffect(() => {
    if (!country && nigeriaData) {
      onCountryChange("Nigeria");
    }
  }, [country, nigeriaData, onCountryChange]);

  const handleStateChange = (value: string) => {
    console.log("State selected:", value);
    onStateChange(value);
    // Reset city when state changes
    if (city) {
      onCityChange("");
    }
  };

  const handleCityChange = (value: string) => {
    console.log("City selected:", value);
    onCityChange(value);
  };

  console.log("=== CascadingAddressDropdown Debug ===");
  console.log("Available states:", availableStates.length);
  console.log("Current state value:", state);
  console.log("Available cities:", availableCities.length, availableCities);
  console.log("Current city value:", city);
  console.log("City dropdown disabled?", !state || disabled);

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      {/* Country Dropdown - Fixed to Nigeria */}
      <div className="space-y-2">
        <Label htmlFor="country">Country *</Label>
        <Select
          value="Nigeria"
          onValueChange={() => {}} // No-op since it's fixed
          disabled={disabled}
        >
          <SelectTrigger
            id="country"
            className="w-full"
            style={
              primaryColor
                ? ({ "--tw-ring-color": primaryColor } as React.CSSProperties)
                : undefined
            }
          >
            <SelectValue placeholder="Nigeria" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="Nigeria">Nigeria</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* State/Province Dropdown */}
      <div className="space-y-2">
        <Label htmlFor="state">State/Province *</Label>
        <Select
          value={state || undefined}
          onValueChange={handleStateChange}
          disabled={disabled}
        >
          <SelectTrigger
            id="state"
            className="w-full"
            style={
              primaryColor
                ? ({ "--tw-ring-color": primaryColor } as React.CSSProperties)
                : undefined
            }
          >
            <SelectValue placeholder="Select state" />
          </SelectTrigger>
          <SelectContent className="max-h-[300px]">
            {availableStates.map((stateItem) => (
              <SelectItem key={stateItem.name} value={stateItem.name}>
                {stateItem.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* City Dropdown */}
      <div className="space-y-2">
        <Label htmlFor="city">City *</Label>
        <Select
          key={`city-${state}`}
          value={city || undefined}
          onValueChange={handleCityChange}
          disabled={!state || disabled}
        >
          <SelectTrigger
            id="city"
            className="w-full"
            style={
              primaryColor
                ? ({ "--tw-ring-color": primaryColor } as React.CSSProperties)
                : undefined
            }
          >
            <SelectValue placeholder="Select city" />
          </SelectTrigger>
          <SelectContent className="max-h-[300px]">
            {availableCities.length > 0 ? (
              availableCities.map((cityName) => (
                <SelectItem key={cityName} value={cityName}>
                  {cityName}
                </SelectItem>
              ))
            ) : (
              <div className="px-2 py-1.5 text-sm text-muted-foreground">
                No cities available
              </div>
            )}
          </SelectContent>
        </Select>
      </div>
    </div>
  );
}
