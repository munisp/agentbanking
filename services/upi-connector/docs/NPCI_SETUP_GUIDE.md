# UPI NPCI Integration Setup Guide

## 📋 Overview

This guide explains how to obtain and configure NPCI (National Payments Corporation of India) credentials for UPI integration.

---

## 🔑 Step 1: Obtain NPCI Credentials

### 1.1 Register as Payment Service Provider (PSP)

**Process:**
1. Visit [NPCI Official Website](https://www.npci.org.in)
2. Navigate to "UPI" → "Become a PSP"
3. Fill out the PSP application form
4. Submit required documents:
   - Company registration certificate
   - Banking license (if applicable)
   - Financial statements
   - Technical infrastructure details
   - Security audit reports

**Timeline:** 4-8 weeks for approval

### 1.2 Complete Technical Integration

**Requirements:**
1. **Infrastructure Setup:**
   - Dedicated servers with 99.9% uptime
   - Redundant network connectivity
   - Disaster recovery setup
   - Security compliance (ISO 27001, PCI DSS)

2. **Technical Specifications:**
   - Support for UPI 2.0 specifications
   - API integration capability
   - Real-time transaction processing
   - Webhook handling

3. **Security Requirements:**
   - SSL/TLS certificates
   - IP whitelisting
   - Encryption at rest and in transit
   - Regular security audits

### 1.3 Obtain API Credentials

After approval, NPCI will provide:
- **Merchant ID:** Unique identifier for your organization
- **API Key:** Public key for API authentication
- **API Secret:** Private key for request signing
- **PSP Code:** Your PSP identifier (e.g., "NRP")
- **Bank Code:** Associated bank code

---

## 🔧 Step 2: Configure Environment Variables

### 2.1 Create Environment File

Create `.env` file in the `upi-connector` directory:

```bash
# NPCI UPI Configuration
NPCI_MERCHANT_ID=your_merchant_id_here
NPCI_API_KEY=your_api_key_here
NPCI_API_SECRET=your_api_secret_here
NPCI_PSP_CODE=NRP
NPCI_BANK_CODE=NRPBANK

# Environment
UPI_ENVIRONMENT=production  # or sandbox for testing

# Callback URLs
UPI_CALLBACK_URL=https://your-domain.com/api/v1
UPI_NOTIFICATION_URL=https://your-domain.com/api/v1

# Security
UPI_ENCRYPTION_KEY=your_encryption_key_here
UPI_SIGNING_KEY=your_signing_key_here
```

### 2.2 Secure Credentials Storage

**For Development:**
```bash
# Use .env file (never commit to git)
cp .env.example .env
# Edit .env with your credentials
```

**For Production:**
```bash
# Use secrets management system
# AWS Secrets Manager
aws secretsmanager create-secret \
  --name npci-upi-credentials \
  --secret-string file://credentials.json

# Or Kubernetes Secrets
kubectl create secret generic npci-credentials \
  --from-literal=merchant-id=$NPCI_MERCHANT_ID \
  --from-literal=api-key=$NPCI_API_KEY \
  --from-literal=api-secret=$NPCI_API_SECRET
```

---

## 🧪 Step 3: Test in Sandbox Environment

### 3.1 Configure Sandbox

Update `config/npci_config.yaml`:

```yaml
environment: sandbox
npci:
  api_base_url: "https://sandbox.npci.org.in/upi/v1"
development:
  use_sandbox: true
  test_merchant_id: "TEST_MERCHANT_001"
```

### 3.2 Run Sandbox Tests

```bash
# Test connectivity
go run cmd/test_connectivity.go

# Test VPA validation
go run cmd/test_vpa.go test@nrp

# Test payment flow
go run cmd/test_payment.go
```

### 3.3 Sandbox Test Scenarios

**Test VPAs:**
- `success@npci` - Always succeeds
- `failure@npci` - Always fails
- `timeout@npci` - Simulates timeout
- `pending@npci` - Returns pending status

**Test Amounts:**
- ₹1.00 - Success
- ₹2.00 - Insufficient funds
- ₹3.00 - Invalid VPA
- ₹4.00 - Transaction timeout

---

## 🚀 Step 4: Production Deployment

### 4.1 Pre-Production Checklist

- [ ] NPCI credentials obtained and verified
- [ ] Environment variables configured
- [ ] Sandbox testing completed successfully
- [ ] Security audit passed
- [ ] IP whitelisting configured
- [ ] SSL certificates installed
- [ ] Monitoring and alerting setup
- [ ] Disaster recovery plan in place
- [ ] Team training completed

### 4.2 Switch to Production

Update `config/npci_config.yaml`:

```yaml
environment: production
npci:
  api_base_url: "https://api.npci.org.in/upi/v1"
production:
  strict_mode: true
  require_https: true
  certificate_pinning: true
```

### 4.3 Production Verification

```bash
# Verify credentials
./scripts/verify_npci_credentials.sh

# Test connectivity
./scripts/test_npci_connection.sh

# Run health checks
./scripts/health_check.sh
```

---

## 📊 Step 5: Monitoring and Maintenance

### 5.1 Setup Monitoring

**Metrics to Monitor:**
- Transaction success rate
- API response times
- Error rates
- Daily transaction volumes
- Webhook delivery success

**Tools:**
- Prometheus for metrics
- Grafana for dashboards
- ELK Stack for logs
- PagerDuty for alerts

### 5.2 Regular Maintenance

**Daily:**
- Monitor transaction volumes
- Check error logs
- Verify webhook deliveries

**Weekly:**
- Review performance metrics
- Analyze failure patterns
- Update documentation

**Monthly:**
- Security audit
- Credential rotation (if required)
- Compliance reporting
- Performance optimization

---

## 🔒 Security Best Practices

### 6.1 Credential Management

1. **Never hardcode credentials**
   - Use environment variables
   - Use secrets management systems
   - Rotate credentials regularly

2. **Secure storage**
   - Encrypt at rest
   - Use access controls
   - Audit access logs

3. **Network security**
   - Use HTTPS only
   - Implement IP whitelisting
   - Use certificate pinning

### 6.2 Transaction Security

1. **Validate all inputs**
   - VPA format validation
   - Amount range checks
   - Transaction type verification

2. **Implement rate limiting**
   - Per user limits
   - Per IP limits
   - Global limits

3. **Monitor for fraud**
   - Unusual transaction patterns
   - Multiple failed attempts
   - High-value transactions

---

## 🆘 Troubleshooting

### Common Issues

**Issue 1: Authentication Failed**
```
Error: Invalid API credentials
```
**Solution:**
- Verify NPCI_MERCHANT_ID is correct
- Check NPCI_API_KEY and NPCI_API_SECRET
- Ensure credentials are for correct environment (sandbox vs production)

**Issue 2: Connection Timeout**
```
Error: Connection timeout to NPCI API
```
**Solution:**
- Check network connectivity
- Verify firewall rules
- Ensure IP is whitelisted by NPCI
- Check NPCI service status

**Issue 3: Invalid Signature**
```
Error: Request signature verification failed
```
**Solution:**
- Verify signature algorithm (SHA256)
- Check API secret is correct
- Ensure timestamp is within acceptable range
- Review signature generation code

**Issue 4: VPA Not Found**
```
Error: VPA does not exist
```
**Solution:**
- Verify VPA format (username@psp)
- Check PSP handle is valid
- Ensure VPA is registered with NPCI
- Try VPA validation endpoint first

---

## 📞 Support

### NPCI Support Contacts

**Technical Support:**
- Email: upi-support@npci.org.in
- Phone: +91-22-XXXX-XXXX
- Portal: https://support.npci.org.in

**Business Queries:**
- Email: business@npci.org.in
- Phone: +91-22-XXXX-XXXX

**Emergency (24/7):**
- Phone: +91-22-XXXX-XXXX
- Email: emergency@npci.org.in

### Internal Support

**DevOps Team:**
- Slack: #upi-integration
- Email: devops@nigerianremittance.com

**Security Team:**
- Email: security@nigerianremittance.com
- On-call: PagerDuty

---

## 📚 Additional Resources

### Documentation
- [NPCI UPI Specifications](https://www.npci.org.in/what-we-do/upi/product-documentation)
- [UPI 2.0 API Guide](https://www.npci.org.in/upi-api-guide)
- [Security Guidelines](https://www.npci.org.in/security-guidelines)

### Training
- NPCI UPI Integration Workshop
- Payment Security Best Practices
- Fraud Prevention Training

### Compliance
- RBI Guidelines for Payment Systems
- PCI DSS Compliance
- ISO 27001 Certification

---

## ✅ Checklist Summary

### Development Phase
- [ ] Understand UPI specifications
- [ ] Setup development environment
- [ ] Configure sandbox credentials
- [ ] Implement API integration
- [ ] Write unit tests
- [ ] Test in sandbox

### Pre-Production Phase
- [ ] Apply for PSP registration
- [ ] Complete security audit
- [ ] Setup production infrastructure
- [ ] Obtain production credentials
- [ ] Configure monitoring
- [ ] Conduct load testing

### Production Phase
- [ ] Deploy to production
- [ ] Verify connectivity
- [ ] Process test transactions
- [ ] Monitor metrics
- [ ] Setup alerts
- [ ] Train support team

### Post-Production
- [ ] Daily monitoring
- [ ] Weekly reviews
- [ ] Monthly audits
- [ ] Continuous improvement

---

**Last Updated:** October 26, 2025  
**Version:** 1.0  
**Status:** Ready for Implementation

