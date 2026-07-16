/**
 * KYC Verification Component
 * Multi-step customer identity verification
 * Supports Nigerian KYC requirements (NIN, BVN, etc.)
 */

import React, { useState } from 'react';

const KYC_API = process.env.REACT_APP_KYC_API || 'http://localhost:8098';

export default function KYCVerification({ customerId }) {
  const [step, setStep] = useState(1);
  const [kycData, setKycData] = useState({
    customer_id: customerId,
    first_name: '',
    last_name: '',
    middle_name: '',
    date_of_birth: '',
    phone_number: '',
    email: '',
    address: '',
    city: '',
    state: '',
    nin: '',
    bvn: '',
    tier: 'tier_1'
  });
  
  const [documents, setDocuments] = useState({
    nin_verified: false,
    bvn_verified: false,
    utility_bill: null,
    selfie: null
  });
  
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(false);

  const handleInputChange = (e) => {
    setKycData({
      ...kycData,
      [e.target.name]: e.target.value
    });
  };

  const handleFileUpload = (e, docType) => {
    const file = e.target.files[0];
    if (file) {
      const reader = new FileReader();
      reader.onloadend = () => {
        setDocuments({
          ...documents,
          [docType]: reader.result
        });
      };
      reader.readAsDataURL(file);
    }
  };

  const registerKYC = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch(`${KYC_API}/kyc/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(kycData)
      });
      
      const data = await response.json();
      
      if (data.success) {
        setStep(2);
      } else {
        setError(data.error || 'Registration failed');
      }
    } catch (err) {
      setError('Network error. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const verifyNIN = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch(`${KYC_API}/kyc/verify/nin?customer_id=${customerId}&nin=${kycData.nin}`, {
        method: 'POST'
      });
      
      const data = await response.json();
      
      if (data.success) {
        setDocuments({ ...documents, nin_verified: true });
      } else {
        setError(data.error || 'NIN verification failed');
      }
    } catch (err) {
      setError('Network error. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const verifyBVN = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch(`${KYC_API}/kyc/verify/bvn?customer_id=${customerId}&bvn=${kycData.bvn}`, {
        method: 'POST'
      });
      
      const data = await response.json();
      
      if (data.success) {
        setDocuments({ ...documents, bvn_verified: true });
      } else {
        setError(data.error || 'BVN verification failed');
      }
    } catch (err) {
      setError('Network error. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const submitKYC = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch(`${KYC_API}/kyc/approve?customer_id=${customerId}`, {
        method: 'POST'
      });
      
      const data = await response.json();
      
      if (data.success) {
        setSuccess(true);
        setStep(4);
      } else {
        setError(data.error || 'KYC approval failed');
      }
    } catch (err) {
      setError('Network error. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="kyc-container">
      <div className="kyc-header">
        <h1>KYC Verification</h1>
        <div className="progress-bar">
          <div className={`step ${step >= 1 ? 'active' : ''}`}>1. Personal Info</div>
          <div className={`step ${step >= 2 ? 'active' : ''}`}>2. Documents</div>
          <div className={`step ${step >= 3 ? 'active' : ''}`}>3. Verification</div>
          <div className={`step ${step >= 4 ? 'active' : ''}`}>4. Complete</div>
        </div>
      </div>

      {error && (
        <div className="alert alert-error">
          ❌ {error}
        </div>
      )}

      {/* Step 1: Personal Information */}
      {step === 1 && (
        <div className="kyc-step">
          <h2>Personal Information</h2>
          <div className="form-grid">
            <div className="form-group">
              <label>First Name *</label>
              <input
                type="text"
                name="first_name"
                value={kycData.first_name}
                onChange={handleInputChange}
                required
              />
            </div>
            <div className="form-group">
              <label>Last Name *</label>
              <input
                type="text"
                name="last_name"
                value={kycData.last_name}
                onChange={handleInputChange}
                required
              />
            </div>
            <div className="form-group">
              <label>Middle Name</label>
              <input
                type="text"
                name="middle_name"
                value={kycData.middle_name}
                onChange={handleInputChange}
              />
            </div>
            <div className="form-group">
              <label>Date of Birth *</label>
              <input
                type="date"
                name="date_of_birth"
                value={kycData.date_of_birth}
                onChange={handleInputChange}
                required
              />
            </div>
            <div className="form-group">
              <label>Phone Number *</label>
              <input
                type="tel"
                name="phone_number"
                value={kycData.phone_number}
                onChange={handleInputChange}
                placeholder="+234XXXXXXXXXX"
                required
              />
            </div>
            <div className="form-group">
              <label>Email</label>
              <input
                type="email"
                name="email"
                value={kycData.email}
                onChange={handleInputChange}
              />
            </div>
            <div className="form-group full-width">
              <label>Address *</label>
              <input
                type="text"
                name="address"
                value={kycData.address}
                onChange={handleInputChange}
                required
              />
            </div>
            <div className="form-group">
              <label>City *</label>
              <input
                type="text"
                name="city"
                value={kycData.city}
                onChange={handleInputChange}
                required
              />
            </div>
            <div className="form-group">
              <label>State *</label>
              <select name="state" value={kycData.state} onChange={handleInputChange} required>
                <option value="">Select State</option>
                <option value="Abia">Abia</option>
                <option value="Adamawa">Adamawa</option>
                <option value="Akwa Ibom">Akwa Ibom</option>
                <option value="Anambra">Anambra</option>
                <option value="Bauchi">Bauchi</option>
                <option value="Bayelsa">Bayelsa</option>
                <option value="Benue">Benue</option>
                <option value="Borno">Borno</option>
                <option value="Cross River">Cross River</option>
                <option value="Delta">Delta</option>
                <option value="Ebonyi">Ebonyi</option>
                <option value="Edo">Edo</option>
                <option value="Ekiti">Ekiti</option>
                <option value="Enugu">Enugu</option>
                <option value="FCT Abuja">FCT Abuja</option>
                <option value="Gombe">Gombe</option>
                <option value="Imo">Imo</option>
                <option value="Jigawa">Jigawa</option>
                <option value="Kaduna">Kaduna</option>
                <option value="Kano">Kano</option>
                <option value="Katsina">Katsina</option>
                <option value="Kebbi">Kebbi</option>
                <option value="Kogi">Kogi</option>
                <option value="Kwara">Kwara</option>
                <option value="Lagos">Lagos</option>
                <option value="Nasarawa">Nasarawa</option>
                <option value="Niger">Niger</option>
                <option value="Ogun">Ogun</option>
                <option value="Ondo">Ondo</option>
                <option value="Osun">Osun</option>
                <option value="Oyo">Oyo</option>
                <option value="Plateau">Plateau</option>
                <option value="Rivers">Rivers</option>
                <option value="Sokoto">Sokoto</option>
                <option value="Taraba">Taraba</option>
                <option value="Yobe">Yobe</option>
                <option value="Zamfara">Zamfara</option>
              </select>
            </div>
            <div className="form-group">
              <label>KYC Tier</label>
              <select name="tier" value={kycData.tier} onChange={handleInputChange}>
                <option value="tier_1">Tier 1 (₦300,000 daily limit)</option>
                <option value="tier_2">Tier 2 (₦1,000,000 daily limit)</option>
                <option value="tier_3">Tier 3 (Unlimited)</option>
              </select>
            </div>
          </div>
          <button className="btn-primary" onClick={registerKYC} disabled={loading}>
            {loading ? 'Processing...' : 'Continue'}
          </button>
        </div>
      )}

      {/* Step 2: Document Upload */}
      {step === 2 && (
        <div className="kyc-step">
          <h2>Identity Verification</h2>
          
          <div className="document-section">
            <h3>National Identity Number (NIN)</h3>
            <div className="form-group">
              <input
                type="text"
                name="nin"
                value={kycData.nin}
                onChange={handleInputChange}
                placeholder="Enter 11-digit NIN"
                maxLength="11"
              />
              <button onClick={verifyNIN} disabled={loading || documents.nin_verified}>
                {documents.nin_verified ? '✓ Verified' : 'Verify NIN'}
              </button>
            </div>
          </div>

          <div className="document-section">
            <h3>Bank Verification Number (BVN)</h3>
            <div className="form-group">
              <input
                type="text"
                name="bvn"
                value={kycData.bvn}
                onChange={handleInputChange}
                placeholder="Enter 11-digit BVN"
                maxLength="11"
              />
              <button onClick={verifyBVN} disabled={loading || documents.bvn_verified}>
                {documents.bvn_verified ? '✓ Verified' : 'Verify BVN'}
              </button>
            </div>
          </div>

          <div className="document-section">
            <h3>Utility Bill (Optional for Tier 1)</h3>
            <input
              type="file"
              accept="image/*,application/pdf"
              onChange={(e) => handleFileUpload(e, 'utility_bill')}
            />
            {documents.utility_bill && <span className="file-uploaded">✓ File uploaded</span>}
          </div>

          <div className="document-section">
            <h3>Selfie Photo</h3>
            <input
              type="file"
              accept="image/*"
              onChange={(e) => handleFileUpload(e, 'selfie')}
            />
            {documents.selfie && <span className="file-uploaded">✓ Photo uploaded</span>}
          </div>

          <div className="button-group">
            <button className="btn-secondary" onClick={() => setStep(1)}>Back</button>
            <button 
              className="btn-primary" 
              onClick={() => setStep(3)}
              disabled={!documents.nin_verified || !documents.bvn_verified}
            >
              Continue
            </button>
          </div>
        </div>
      )}

      {/* Step 3: Review & Submit */}
      {step === 3 && (
        <div className="kyc-step">
          <h2>Review & Submit</h2>
          
          <div className="review-section">
            <h3>Personal Information</h3>
            <div className="review-item">
              <span>Name:</span>
              <span>{kycData.first_name} {kycData.middle_name} {kycData.last_name}</span>
            </div>
            <div className="review-item">
              <span>Date of Birth:</span>
              <span>{kycData.date_of_birth}</span>
            </div>
            <div className="review-item">
              <span>Phone:</span>
              <span>{kycData.phone_number}</span>
            </div>
            <div className="review-item">
              <span>Address:</span>
              <span>{kycData.address}, {kycData.city}, {kycData.state}</span>
            </div>
          </div>

          <div className="review-section">
            <h3>Verified Documents</h3>
            <div className="review-item">
              <span>NIN:</span>
              <span>{documents.nin_verified ? '✓ Verified' : '✗ Not verified'}</span>
            </div>
            <div className="review-item">
              <span>BVN:</span>
              <span>{documents.bvn_verified ? '✓ Verified' : '✗ Not verified'}</span>
            </div>
            <div className="review-item">
              <span>Utility Bill:</span>
              <span>{documents.utility_bill ? '✓ Uploaded' : '✗ Not uploaded'}</span>
            </div>
            <div className="review-item">
              <span>Selfie:</span>
              <span>{documents.selfie ? '✓ Uploaded' : '✗ Not uploaded'}</span>
            </div>
          </div>

          <div className="review-section">
            <h3>KYC Tier</h3>
            <div className="tier-info">
              <strong>{kycData.tier.toUpperCase().replace('_', ' ')}</strong>
              <p>
                {kycData.tier === 'tier_1' && 'Daily limit: ₦300,000'}
                {kycData.tier === 'tier_2' && 'Daily limit: ₦1,000,000'}
                {kycData.tier === 'tier_3' && 'Daily limit: Unlimited'}
              </p>
            </div>
          </div>

          <div className="button-group">
            <button className="btn-secondary" onClick={() => setStep(2)}>Back</button>
            <button className="btn-primary" onClick={submitKYC} disabled={loading}>
              {loading ? 'Submitting...' : 'Submit KYC'}
            </button>
          </div>
        </div>
      )}

      {/* Step 4: Success */}
      {step === 4 && success && (
        <div className="kyc-step success-step">
          <div className="success-icon">✓</div>
          <h2>KYC Verification Complete!</h2>
          <p>Your identity has been successfully verified.</p>
          <div className="success-details">
            <p><strong>Tier:</strong> {kycData.tier.toUpperCase().replace('_', ' ')}</p>
            <p><strong>Status:</strong> Verified</p>
          </div>
          <button className="btn-primary" onClick={() => window.location.href = '/dashboard'}>
            Go to Dashboard
          </button>
        </div>
      )}

      <style jsx>{`
        .kyc-container {
          max-width: 800px;
          margin: 0 auto;
          padding: 20px;
        }

        .kyc-header h1 {
          text-align: center;
          margin-bottom: 30px;
        }

        .progress-bar {
          display: flex;
          justify-content: space-between;
          margin-bottom: 40px;
        }

        .progress-bar .step {
          flex: 1;
          padding: 10px;
          text-align: center;
          background: #f0f0f0;
          border-radius: 4px;
          margin: 0 5px;
          font-size: 14px;
        }

        .progress-bar .step.active {
          background: #667eea;
          color: white;
          font-weight: 600;
        }

        .alert {
          padding: 15px;
          border-radius: 6px;
          margin-bottom: 20px;
        }

        .alert-error {
          background: #fee;
          color: #c00;
          border: 1px solid #fcc;
        }

        .kyc-step {
          background: white;
          padding: 30px;
          border-radius: 12px;
          box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }

        .form-grid {
          display: grid;
          grid-template-columns: repeat(2, 1fr);
          gap: 20px;
          margin-bottom: 30px;
        }

        .form-group {
          display: flex;
          flex-direction: column;
        }

        .form-group.full-width {
          grid-column: 1 / -1;
        }

        .form-group label {
          margin-bottom: 8px;
          font-weight: 500;
        }

        .form-group input,
        .form-group select {
          padding: 10px;
          border: 1px solid #ddd;
          border-radius: 4px;
          font-size: 14px;
        }

        .document-section {
          margin-bottom: 30px;
          padding: 20px;
          background: #f8f9fa;
          border-radius: 8px;
        }

        .document-section h3 {
          margin-bottom: 15px;
        }

        .document-section .form-group {
          flex-direction: row;
          gap: 10px;
        }

        .document-section input[type="file"] {
          margin-top: 10px;
        }

        .file-uploaded {
          color: #10b981;
          font-weight: 500;
          margin-top: 10px;
          display: block;
        }

        .button-group {
          display: flex;
          gap: 15px;
          justify-content: flex-end;
        }

        .btn-primary,
        .btn-secondary {
          padding: 12px 30px;
          border: none;
          border-radius: 6px;
          font-weight: 600;
          cursor: pointer;
          font-size: 16px;
        }

        .btn-primary {
          background: #667eea;
          color: white;
        }

        .btn-primary:hover:not(:disabled) {
          background: #5568d3;
        }

        .btn-primary:disabled {
          background: #ccc;
          cursor: not-allowed;
        }

        .btn-secondary {
          background: #e5e7eb;
          color: #374151;
        }

        .btn-secondary:hover {
          background: #d1d5db;
        }

        .review-section {
          margin-bottom: 30px;
        }

        .review-section h3 {
          margin-bottom: 15px;
          padding-bottom: 10px;
          border-bottom: 2px solid #e5e7eb;
        }

        .review-item {
          display: flex;
          justify-content: space-between;
          padding: 10px 0;
          border-bottom: 1px solid #f0f0f0;
        }

        .tier-info {
          padding: 15px;
          background: #f0f4ff;
          border-radius: 6px;
        }

        .success-step {
          text-align: center;
        }

        .success-icon {
          font-size: 64px;
          color: #10b981;
          margin-bottom: 20px;
        }

        .success-details {
          margin: 30px 0;
          padding: 20px;
          background: #f0fdf4;
          border-radius: 8px;
        }
      `}</style>
    </div>
  );
}

