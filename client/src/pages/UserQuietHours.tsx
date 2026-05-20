import { useState, useEffect } from "react";
import { trpc } from "@/lib/trpc";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";

const DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const TIMEZONES = [
  "Africa/Lagos",
  "Africa/Nairobi",
  "Africa/Cairo",
  "Africa/Johannesburg",
  "UTC",
  "Europe/London",
  "America/New_York",
];

export default function UserQuietHours() {
  const userId = "user_001";
  // @ts-ignore Sprint 85
  const configQ = trpc.quietHours.get.useQuery({ userId });
  // @ts-ignore Sprint 85
  const statusQ = trpc.quietHours.checkStatus.useQuery({ userId });
  const updateMut = trpc.quietHours.update.useMutation({
    onSuccess: () => {
      configQ.refetch();
      statusQ.refetch();
      toast.success("Quiet hours updated");
    },
  });

  const [enabled, setEnabled] = useState(false);
  const [startTime, setStartTime] = useState("22:00");
  const [endTime, setEndTime] = useState("07:00");
  const [timezone, setTimezone] = useState("Africa/Lagos");
  const [overrideForCritical, setOverrideForCritical] = useState(true);
  const [daysOfWeek, setDaysOfWeek] = useState<number[]>([0, 1, 2, 3, 4, 5, 6]);

  useEffect(() => {
    if (configQ.data) {
      setEnabled(configQ.data.enabled);
      // @ts-ignore Sprint 85
      setStartTime(configQ.data.startTime);
      // @ts-ignore Sprint 85
      setEndTime(configQ.data.endTime);
      setTimezone(configQ.data.timezone);
      // @ts-ignore Sprint 85
      setOverrideForCritical(configQ.data.overrideForCritical);
      setDaysOfWeek(configQ.data.daysOfWeek);
    }
  }, [configQ.data]);

  const toggleDay = (day: number) => {
    setDaysOfWeek(prev =>
      prev.includes(day) ? prev.filter(d => d !== day) : [...prev, day]
    );
  };

  const handleSave = () => {
    updateMut.mutate({
      // @ts-ignore Sprint 85
      userId,
      enabled,
      startTime,
      endTime,
      timezone,
      overrideForCritical,
      daysOfWeek,
    });
  };

  return (
    <div className="min-h-screen bg-gray-950 text-white p-6">
      <div className="max-w-3xl mx-auto space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">Quiet Hours</h1>
            <p className="text-gray-400">
              Configure when notifications should be silenced
            </p>
          </div>
          <a href="/" className="text-sm text-gray-400 hover:text-white">
            ← Back
          </a>
        </div>

        {/* Status */}
        <Card className="bg-gray-900 border-gray-800">
          <CardContent className="pt-4 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div
                className={`w-4 h-4 rounded-full ${statusQ.data?.inQuietHours ? "bg-yellow-500 animate-pulse" : "bg-green-500"}`}
              />
              <span className="text-lg font-medium text-white">
                {statusQ.data?.inQuietHours
                  ? "Currently in Quiet Hours"
                  : "Notifications Active"}
              </span>
            </div>
            {statusQ.data?.inQuietHours &&
              statusQ.data?.overrideForCritical && (
                <Badge className="bg-red-600 text-white">
                  Critical alerts bypass quiet hours
                </Badge>
              )}
          </CardContent>
        </Card>

        {/* Configuration */}
        <Card className="bg-gray-900 border-gray-800">
          <CardHeader>
            <CardTitle className="text-white">Configuration</CardTitle>
            <CardDescription className="text-gray-400">
              Set your preferred quiet hours window
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* Enable toggle */}
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-300">Enable Quiet Hours</span>
              <button
                onClick={() => setEnabled(!enabled)}
                className={`w-12 h-6 rounded-full transition-colors ${enabled ? "bg-blue-600" : "bg-gray-700"}`}
              >
                <div
                  className={`w-5 h-5 bg-white rounded-full transition-transform ${enabled ? "translate-x-6" : "translate-x-0.5"}`}
                />
              </button>
            </div>

            {/* Time window */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-sm text-gray-400 mb-1 block">
                  Start Time
                </label>
                <Input
                  type="time"
                  value={startTime}
                  onChange={e => setStartTime(e.target.value)}
                  className="bg-gray-800 border-gray-700 text-white"
                />
              </div>
              <div>
                <label className="text-sm text-gray-400 mb-1 block">
                  End Time
                </label>
                <Input
                  type="time"
                  value={endTime}
                  onChange={e => setEndTime(e.target.value)}
                  className="bg-gray-800 border-gray-700 text-white"
                />
              </div>
            </div>

            {/* Timezone */}
            <div>
              <label className="text-sm text-gray-400 mb-1 block">
                Timezone
              </label>
              <select
                value={timezone}
                onChange={e => setTimezone(e.target.value)}
                className="w-full bg-gray-800 border border-gray-700 rounded-md px-3 py-2 text-white text-sm"
              >
                {TIMEZONES.map(tz => (
                  <option key={tz} value={tz}>
                    {tz}
                  </option>
                ))}
              </select>
            </div>

            {/* Days of week */}
            <div>
              <label className="text-sm text-gray-400 mb-2 block">
                Active Days
              </label>
              <div className="flex gap-2">
                {DAYS.map((day, i) => (
                  <button
                    key={i}
                    onClick={() => toggleDay(i)}
                    className={`w-10 h-10 rounded-lg text-xs font-medium transition-colors ${daysOfWeek.includes(i) ? "bg-blue-600 text-white" : "bg-gray-800 text-gray-400 hover:bg-gray-700"}`}
                  >
                    {day}
                  </button>
                ))}
              </div>
            </div>

            {/* Override for critical */}
            <div className="flex items-center justify-between">
              <div>
                <span className="text-sm text-gray-300">
                  Allow Critical Alerts
                </span>
                <p className="text-xs text-gray-500">
                  Critical severity alerts will bypass quiet hours
                </p>
              </div>
              <button
                onClick={() => setOverrideForCritical(!overrideForCritical)}
                className={`w-12 h-6 rounded-full transition-colors ${overrideForCritical ? "bg-blue-600" : "bg-gray-700"}`}
              >
                <div
                  className={`w-5 h-5 bg-white rounded-full transition-transform ${overrideForCritical ? "translate-x-6" : "translate-x-0.5"}`}
                />
              </button>
            </div>

            <Button
              onClick={handleSave}
              disabled={updateMut.isPending}
              className="w-full"
            >
              {updateMut.isPending ? "Saving..." : "Save Quiet Hours"}
            </Button>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
