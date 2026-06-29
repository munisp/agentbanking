#!/usr/bin/env node

/**
 * Create a test verification session
 * 
 * This script creates a test verification session and returns the verification URL
 * that can be used to test the verification UI.
 */

const API_BASE_URL = process.env.VITE_VERIFICATION_API_URL || 'http://localhost:8080';
const CLIENT_ID = process.env.TEST_CLIENT_ID || 'test-client-id';
const CLIENT_SECRET = process.env.TEST_CLIENT_SECRET || 'test-client-secret';

async function createTestVerification() {
  try {
    console.log('\n🔧 Creating test verification session...\n');

    const response = await fetch(`${API_BASE_URL}/kyc/initialize-verification`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-client-id': CLIENT_ID,
        'x-client-secret': CLIENT_SECRET,
      },
      body: JSON.stringify({
        user: {
          firstName: 'Test',
          lastName: 'User',
          phone: '+1234567890',
          UIN: `test-user-${Date.now()}`,
          dateOfBirth: '1990-01-01',
        },
        identityProvider: 'LIVENESS',
        redirectUrl: 'http://localhost:8005/success',
        metadata: {
          testMode: true,
          createdBy: 'test-script',
        },
      }),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(`Failed to create verification: ${JSON.stringify(error, null, 2)}`);
    }

    const result = await response.json();
    
    console.log('✅ Verification session created successfully!\n');
    console.log('📋 Verification URL:');
    console.log(`   ${result.url}\n`);
    console.log('🔗 Or open directly:');
    console.log(`   ${result.url.replace('http://localhost:8005', 'http://localhost:8005')}\n`);
    
    // Extract verification ID for reference
    const urlObj = new URL(result.url);
    const verificationId = urlObj.searchParams.get('verification_id');
    console.log('🆔 Verification ID:', verificationId);
    console.log('\n💡 Copy the URL above and paste it in your browser to start verification.\n');

  } catch (error) {
    console.error('\n❌ Error:', error.message);
    console.error('\n💡 Make sure:');
    console.error('   1. Verification service is running on', API_BASE_URL);
    console.error('   2. You have created a test client in the database');
    console.error('   3. Or set TEST_CLIENT_ID and TEST_CLIENT_SECRET environment variables\n');
    console.error('📚 To create a test client, run:');
    console.error('   cd services/verification-service');
    console.error('   npm run create-test-client\n');
    process.exit(1);
  }
}

createTestVerification();
