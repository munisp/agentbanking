import React, { useEffect, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { CheckCircle, ArrowRight } from 'lucide-react';
import { storage } from '../../utils/storage.js';

const OnboardingCompletionScreen = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const [accountType, setAccountType] = useState('');

  useEffect(() => {
    const type = location.state?.accountType || storage.getAccountType();
    setAccountType(type);
  }, [location]);

  // ── Success ──────────────────────────────────────────────────────────────────
  return (
    <div className="min-h-screen bg-gradient-to-br from-green-50 to-blue-50 flex items-center justify-center py-12 px-4">
      <div className="max-w-2xl w-full">
        <div className="bg-white rounded-3xl shadow-2xl p-12 text-center space-y-8">
          <div className="flex justify-center">
            <div className="w-32 h-32 bg-green-500 rounded-full flex items-center justify-center shadow-2xl shadow-green-200">
              <CheckCircle className="w-20 h-20 text-white" />
            </div>
          </div>

          <div className="space-y-4">
            <h1 className="text-4xl font-bold text-gray-900">🎉 All Set!</h1>
            <p className="text-xl text-gray-600">Your account has been created successfully.</p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 py-6">
            <div className="bg-green-50 rounded-xl p-4">
              <div className="text-3xl mb-2">✅</div>
              <div className="text-sm font-semibold text-gray-900">Account Type</div>
              <div className="text-sm text-gray-600 capitalize">{accountType || 'Individual'}</div>
            </div>
            <div className="bg-blue-50 rounded-xl p-4">
              <div className="text-3xl mb-2">🔒</div>
              <div className="text-sm font-semibold text-gray-900">Verified</div>
              <div className="text-sm text-gray-600">Identity Confirmed</div>
            </div>
            <div className="bg-purple-50 rounded-xl p-4">
              <div className="text-3xl mb-2">🏦</div>
              <div className="text-sm font-semibold text-gray-900">CBN Compliant</div>
              <div className="text-sm text-gray-600">Fully Registered</div>
            </div>
          </div>

          <div className="bg-gray-50 rounded-2xl p-6 text-left">
            <h2 className="text-lg font-bold text-gray-900 mb-4">What's Next?</h2>
            <ul className="space-y-3">
              {[
                'Access your digital wallet',
                'Make deposits and withdrawals',
                'Send money to friends and family',
                'Pay bills and buy airtime',
                'Apply for loans and credit',
              ].map((item, index) => (
                <li key={index} className="flex items-center gap-3">
                  <div className="w-6 h-6 bg-green-500 rounded-full flex items-center justify-center flex-shrink-0">
                    <CheckCircle className="w-4 h-4 text-white" />
                  </div>
                  <span className="text-gray-700">{item}</span>
                </li>
              ))}
            </ul>
          </div>

          <button
            onClick={() => navigate('/')}
            className="w-full py-4 bg-green-600 text-white font-bold rounded-xl hover:bg-green-700 transition-colors shadow-xl shadow-green-200 text-lg flex items-center justify-center gap-2"
          >
            Go to Dashboard
            <ArrowRight className="w-6 h-6" />
          </button>

          <p className="text-sm text-gray-500">
            Need help?{' '}
            <a href="mailto:support@54agent.com" className="text-green-600 hover:underline">
              support@54agent.com
            </a>
          </p>
        </div>
      </div>
    </div>
  );
};

export default OnboardingCompletionScreen;
