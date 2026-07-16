import { Card } from '@/components/ui/card';
import { Shield, CheckCircle } from 'lucide-react';
import { useTenantBranding } from '@/contexts/TenantBrandingContext';
import { onboardingService } from '@/services/onboarding';
import { useEffect } from 'react';
import { useLocation } from 'wouter';

export default function KYC() {
  const [, setLocation] = useLocation();
  const { primaryColor, secondaryColor, name, logoUrl } = useTenantBranding();
  const onboardingData = onboardingService.getOnboardingData();

  useEffect(() => {
    // If onboarding is not complete, redirect to onboarding
    if (!onboardingService.isOnboardingComplete()) {
      setLocation('/admin/onboarding');
    }
  }, [setLocation]);

  return (
    <div 
      className="min-h-screen flex flex-col"
      style={{
        background: `linear-gradient(to bottom right, ${primaryColor}15, ${secondaryColor}15)`
      }}
    >
      {/* Header with Logo */}
      <div className="w-full py-6 px-4 border-b border-gray-200 dark:border-slate-700 bg-white/80 dark:bg-slate-900/80 backdrop-blur-sm">
        <div className="max-w-4xl mx-auto flex items-center gap-4">
          {logoUrl && (
            <img 
              src={logoUrl} 
              alt={`${name} logo`} 
              className="w-12 h-12 rounded object-contain" 
            />
          )}
          <div>
            <h1 
              className="text-2xl font-bold"
              style={{ color: primaryColor }}
            >
              {name}
            </h1>
            <p className="text-sm text-gray-600 dark:text-gray-400">KYC Verification</p>
          </div>
        </div>
      </div>

      <div className="flex-1 container py-8">
        <div className="max-w-4xl mx-auto">
          <Card className="p-8 shadow-lg border-0 bg-white/95 dark:bg-slate-800/95 backdrop-blur-sm">
            <div className="text-center mb-8">
              <div
                className="w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-4"
                style={{ backgroundColor: primaryColor || '#2563eb' }}
              >
                <Shield className="w-8 h-8 text-white" />
              </div>
              <h2 className="text-3xl font-bold mb-2" style={{ color: primaryColor }}>
                KYC Verification
              </h2>
              <p className="text-gray-600 dark:text-gray-400">
                Your onboarding information has been submitted successfully
              </p>
            </div>

          {onboardingData && (
            <div className="space-y-4 mb-8">
              <div className="bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg p-4 flex items-start gap-3">
                <CheckCircle className="w-5 h-5 text-green-600 dark:text-green-400 mt-0.5 flex-shrink-0" />
                <div>
                  <h3 className="font-semibold text-green-900 dark:text-green-100 mb-1">
                    Onboarding Complete
                  </h3>
                  <p className="text-sm text-green-700 dark:text-green-300">
                    Your information has been submitted. KYC verification is in progress.
                  </p>
                </div>
              </div>

              <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-4">
                <h3 className="font-semibold text-blue-900 dark:text-blue-100 mb-3">
                  Submitted Information
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                  <div>
                    <span className="text-gray-600 dark:text-gray-400">Name:</span>
                    <span className="ml-2 font-medium">{onboardingData.name}</span>
                  </div>
                  <div>
                    <span className="text-gray-600 dark:text-gray-400">Email:</span>
                    <span className="ml-2 font-medium">{onboardingData.email}</span>
                  </div>
                  <div>
                    <span className="text-gray-600 dark:text-gray-400">Phone:</span>
                    <span className="ml-2 font-medium">{onboardingData.phone}</span>
                  </div>
                  <div>
                    <span className="text-gray-600 dark:text-gray-400">Address:</span>
                    <span className="ml-2 font-medium">{onboardingData.address}</span>
                  </div>
                  <div>
                    <span className="text-gray-600 dark:text-gray-400">City:</span>
                    <span className="ml-2 font-medium">{onboardingData.city}</span>
                  </div>
                  <div>
                    <span className="text-gray-600 dark:text-gray-400">State:</span>
                    <span className="ml-2 font-medium">{onboardingData.state}</span>
                  </div>
                </div>
              </div>
            </div>
          )}

          <div className="bg-gray-50 dark:bg-slate-800 rounded-lg p-6">
            <h3 className="font-semibold mb-2">Next Steps</h3>
            <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
              Your KYC verification is being processed. This typically takes 24-48 hours.
              You will be notified once the verification is complete.
            </p>
            <p className="text-xs text-gray-500 dark:text-gray-500">
              Note: This is a placeholder screen. Replace with actual KYC implementation when ready.
            </p>
          </div>

            {/* TODO: Replace this section with actual KYC API integration
            Example:
            const kycStatus = await kycService.getStatus();
            const kycDocuments = await kycService.getDocuments();
            */}
          </Card>
        </div>
      </div>
    </div>
  );
}

