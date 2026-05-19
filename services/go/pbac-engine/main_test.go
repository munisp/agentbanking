package main

import (
	"testing"
)

func TestAdminFullAccess(t *testing.T) {
	engine := NewPBACEngine()
	resp := engine.Evaluate(AuthzRequest{
		Subject:  SubjectContext{UserID: "admin1", Roles: []string{"admin"}},
		Resource: ResourceTarget{ID: "/api/transactions/create"},
		Action:   "create",
		Context:  RequestContext{Amount: 500000},
	})
	if !resp.Allowed {
		t.Errorf("Admin should have full access, got denied: %s", resp.Reason)
	}
}

func TestDenyHighValueWithoutMFA(t *testing.T) {
	engine := NewPBACEngine()
	// Non-admin user, high value, no MFA
	resp := engine.Evaluate(AuthzRequest{
		Subject:  SubjectContext{UserID: "user1", Roles: []string{"user"}},
		Resource: ResourceTarget{ID: "/api/transactions/create"},
		Action:   "create",
		Context:  RequestContext{Amount: 2000000, MFAVerified: false},
	})
	if resp.Allowed {
		t.Error("Should deny high-value transaction without MFA")
	}
	if resp.MatchedPolicy != "default-deny-high-value-no-mfa" {
		t.Errorf("Expected policy 'default-deny-high-value-no-mfa', got '%s'", resp.MatchedPolicy)
	}
}

func TestAllowHighValueWithMFA(t *testing.T) {
	engine := NewPBACEngine()
	// High value but MFA verified — the deny condition won't match
	resp := engine.Evaluate(AuthzRequest{
		Subject:  SubjectContext{UserID: "user1", Roles: []string{"user"}},
		Resource: ResourceTarget{ID: "/api/transactions/create"},
		Action:   "create",
		Context:  RequestContext{Amount: 2000000, MFAVerified: true},
	})
	// Should be default deny since no allow policy matches for "user" role
	// But the high-value-no-mfa deny won't fire since MFA is verified
	if resp.MatchedPolicy == "default-deny-high-value-no-mfa" {
		t.Error("Should not match high-value-no-mfa when MFA is verified")
	}
}

func TestGeoRestriction(t *testing.T) {
	engine := NewPBACEngine()
	resp := engine.Evaluate(AuthzRequest{
		Subject:  SubjectContext{UserID: "user1", Roles: []string{"user"}},
		Resource: ResourceTarget{ID: "/api/transactions/create"},
		Action:   "create",
		Context:  RequestContext{GeoCountry: "KP"},
	})
	if resp.Allowed {
		t.Error("Should deny requests from sanctioned countries")
	}
	if resp.MatchedPolicy != "default-geo-restriction" {
		t.Errorf("Expected geo-restriction policy, got '%s'", resp.MatchedPolicy)
	}
}

func TestKYCLevelRestriction(t *testing.T) {
	engine := NewPBACEngine()
	resp := engine.Evaluate(AuthzRequest{
		Subject:  SubjectContext{UserID: "user1", Roles: []string{"user"}, KYCLevel: 1},
		Resource: ResourceTarget{ID: "/api/transactions/create"},
		Action:   "create",
		Context:  RequestContext{Amount: 75000},
	})
	if resp.Allowed {
		t.Error("KYC level 1 should be denied for amounts > 50K")
	}
}

func TestRiskScoreBlock(t *testing.T) {
	engine := NewPBACEngine()
	resp := engine.Evaluate(AuthzRequest{
		Subject:  SubjectContext{UserID: "user1", Roles: []string{"user"}},
		Resource: ResourceTarget{ID: "/api/transactions/create"},
		Action:   "create",
		Context:  RequestContext{RiskScore: 0.95},
	})
	if resp.Allowed {
		t.Error("Should deny requests with high risk score")
	}
}

func TestUSSDAmountCap(t *testing.T) {
	engine := NewPBACEngine()
	resp := engine.Evaluate(AuthzRequest{
		Subject:  SubjectContext{UserID: "user1", Roles: []string{"user"}},
		Resource: ResourceTarget{ID: "/api/transactions/create"},
		Action:   "create",
		Context:  RequestContext{Channel: "ussd", Amount: 200000},
	})
	if resp.Allowed {
		t.Error("USSD transactions above 100K should be denied")
	}
}

func TestViewerReadOnly(t *testing.T) {
	engine := NewPBACEngine()
	resp := engine.Evaluate(AuthzRequest{
		Subject:  SubjectContext{UserID: "viewer1", Roles: []string{"viewer"}},
		Resource: ResourceTarget{ID: "/api/agents"},
		Action:   "delete",
		Context:  RequestContext{},
	})
	if resp.Allowed {
		t.Error("Viewer should not be able to delete")
	}
}

func TestPolicyCreation(t *testing.T) {
	engine := NewPBACEngine()
	initialCount := len(engine.policies)

	engine.mu.Lock()
	engine.policies["test-policy"] = &Policy{
		ID: "test-policy", Name: "Test", Effect: "deny",
		Priority: 500, Enabled: true,
		Subjects:  []SubjectMatcher{{Type: "role", Value: "tester", Op: "eq"}},
		Resources: []ResourceMatcher{{Type: "endpoint", Value: "/api/test", Op: "eq"}},
		Actions:   []string{"create"},
	}
	engine.mu.Unlock()

	if len(engine.policies) != initialCount+1 {
		t.Error("Policy count should have increased by 1")
	}
}

func TestDefaultDenyNoMatchingPolicy(t *testing.T) {
	engine := NewPBACEngine()
	resp := engine.Evaluate(AuthzRequest{
		Subject:  SubjectContext{UserID: "unknown", Roles: []string{"unknown_role"}},
		Resource: ResourceTarget{ID: "/api/secret"},
		Action:   "read",
		Context:  RequestContext{},
	})
	if resp.Allowed {
		t.Error("Should default deny when no policy matches")
	}
	if resp.MatchedPolicy != "default-deny" {
		t.Errorf("Expected 'default-deny', got '%s'", resp.MatchedPolicy)
	}
}

// TestPBAC is the top-level PBAC integration test suite
func TestPBAC(t *testing.T) {
	engine := NewPBACEngine()
	// Verify engine initializes with default policies
	if len(engine.policies) == 0 {
		t.Error("PBAC engine should initialize with default policies")
	}
	// Verify admin access
	resp := engine.Evaluate(AuthzRequest{
		Subject:  SubjectContext{UserID: "admin1", Roles: []string{"admin"}},
		Resource: ResourceTarget{ID: "/api/transactions/create"},
		Action:   "create",
		Context:  RequestContext{Amount: 500000},
	})
	if !resp.Allowed {
		t.Error("TestPBAC: Admin should have full access")
	}
	// Verify default deny
	resp2 := engine.Evaluate(AuthzRequest{
		Subject:  SubjectContext{UserID: "unknown", Roles: []string{"unknown"}},
		Resource: ResourceTarget{ID: "/api/secret"},
		Action:   "delete",
		Context:  RequestContext{},
	})
	if resp2.Allowed {
		t.Error("TestPBAC: Should default deny unknown roles")
	}
}

func TestEvalPerformance(t *testing.T) {
	engine := NewPBACEngine()
	req := AuthzRequest{
		Subject:  SubjectContext{UserID: "user1", Roles: []string{"user"}},
		Resource: ResourceTarget{ID: "/api/transactions/create"},
		Action:   "create",
		Context:  RequestContext{Amount: 500, Channel: "web"},
	}

	// Evaluate 1000 times and check average time
	for i := 0; i < 1000; i++ {
		resp := engine.Evaluate(req)
		if resp.EvalTimeMs > 10.0 {
			t.Errorf("Evaluation took too long: %.2fms", resp.EvalTimeMs)
		}
	}
}
