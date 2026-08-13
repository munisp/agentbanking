import { trpc } from "../lib/trpc";
import { usePosStore } from "../store/posStore";
import { BORDER, CARD, DISP, GAMIFICATION_EMPTY, GOLD, GamificationData, MONO, TILE_CUSTOM_KEY, TileCustomization } from "./POSShell.shared";

export function PhoneInput({
  value,
  onChange,
  label = "Customer Phone Number",
}: {
  value: string;
  onChange: (v: string) => void;
  label?: string;
}) {
  return (
    <div className="px-4 pb-2">
      <div className="text-xs text-gray-500 mb-1" style={{ fontFamily: DISP }}>
        {label}
      </div>
      <input
        type="tel"
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder="0800 000 0000"
        className="w-full rounded-xl px-4 py-3 text-white text-base outline-none"
        style={{
          background: CARD,
          border: `1px solid ${BORDER}`,
          fontFamily: MONO,
        }}
      />
    </div>
  );
}


export function AmountDisplay({ value, label }: { value: string; label: string }) {
  const num = parseFloat(value || "0");
  return (
    <div className="flex flex-col items-center py-6 gap-1">
      <div
        className="text-xs text-gray-500 uppercase tracking-widest"
        style={{ fontFamily: DISP }}
      >
        {label}
      </div>
      <div
        className="text-4xl font-bold"
        style={{ fontFamily: MONO, color: GOLD }}
      >
        ₦
        {num.toLocaleString("en-NG", {
          minimumFractionDigits: value.includes(".") ? 2 : 0,
        })}
      </div>
    </div>
  );
}


export function useGamification(): GamificationData {
  const { data: loyaltyProfile } = trpc.loyalty.profile.useQuery(undefined, {
    retry: false,
    refetchInterval: 60000,
  }) as any;
  const storeAgent = usePosStore(s => s.agent);
  return {
    ...GAMIFICATION_EMPTY,
    points: loyaltyProfile?.points ?? null,
    level: loyaltyProfile?.tier ? loyaltyProfile.tier + " Agent" : null,
    streak: storeAgent?.streak ?? null,
    rank: storeAgent?.rank ?? null,
  };
}


export function saveTileCustomizations(c: TileCustomization) {
  localStorage.setItem(TILE_CUSTOM_KEY, JSON.stringify(c));
}

