package keycloak

import (
	"context"
	"fmt"

	"github.com/Nerzal/gocloak/v13"
	"workflow-orchestrator/pkg/logger"
)

// Client represents a Keycloak client for authentication and authorization
type Client struct {
	client *gocloak.GoCloak
	config *Config
	token  *gocloak.JWT
}

// Config holds Keycloak configuration
type Config struct {
	URL          string
	Realm        string
	ClientID     string
	ClientSecret string
	AdminUser    string
	AdminPass    string
}

// UserInfo represents user information from Keycloak
type UserInfo struct {
	UserID   string   `json:"user_id"`
	Username string   `json:"username"`
	Email    string   `json:"email"`
	Roles    []string `json:"roles"`
	TenantID string   `json:"tenant_id"`
}

// NewClient creates a new Keycloak client
func NewClient(config *Config) (*Client, error) {
	client := gocloak.NewClient(config.URL)

	// Login as admin to get access token
	token, err := client.LoginAdmin(context.Background(), config.AdminUser, config.AdminPass, "master")
	if err != nil {
		return nil, fmt.Errorf("failed to login to Keycloak: %w", err)
	}

	return &Client{
		client: client,
		config: config,
		token:  token,
	}, nil
}

// ValidateToken validates a JWT token and returns user information
func (c *Client) ValidateToken(ctx context.Context, accessToken string) (*UserInfo, error) {
	logger.Logger.Info("Validating JWT token with Keycloak")

	// Introspect token
	rptResult, err := c.client.RetrospectToken(ctx, accessToken, c.config.ClientID, c.config.ClientSecret, c.config.Realm)
	if err != nil {
		logger.Logger.Error("Failed to introspect token", logger.Error(err))
		return nil, fmt.Errorf("token introspection failed: %w", err)
	}

	if !*rptResult.Active {
		return nil, fmt.Errorf("token is not active")
	}

	// Get user info
	userInfo, err := c.client.GetUserInfo(ctx, accessToken, c.config.Realm)
	if err != nil {
		logger.Logger.Error("Failed to get user info", logger.Error(err))
		return nil, fmt.Errorf("failed to get user info: %w", err)
	}

	// gocloak.UserInfo is a struct; roles come from realm token claims separately
	roles := make([]string, 0)
	tenantID := ""

	userID := ""
	if userInfo.Sub != nil {
		userID = *userInfo.Sub
	}
	username := ""
	if userInfo.PreferredUsername != nil {
		username = *userInfo.PreferredUsername
	}
	email := ""
	if userInfo.Email != nil {
		email = *userInfo.Email
	}

	return &UserInfo{
		UserID:   userID,
		Username: username,
		Email:    email,
		Roles:    roles,
		TenantID: tenantID,
	}, nil
}

// CheckPermission checks if a user has a specific role
func (c *Client) CheckPermission(ctx context.Context, userID string, role string) (bool, error) {
	logger.Logger.Info("Checking user permission",
		logger.String("user_id", userID),
		logger.String("role", role),
	)

	// Get user roles
	roles, err := c.client.GetRealmRolesByUserID(ctx, c.token.AccessToken, c.config.Realm, userID)
	if err != nil {
		logger.Logger.Error("Failed to get user roles", logger.Error(err))
		return false, fmt.Errorf("failed to get user roles: %w", err)
	}

	// Check if user has the required role
	for _, r := range roles {
		if *r.Name == role {
			return true, nil
		}
	}

	return false, nil
}

// CreateUser creates a new user in Keycloak
func (c *Client) CreateUser(ctx context.Context, username, email, password string) (string, error) {
	logger.Logger.Info("Creating user in Keycloak",
		logger.String("username", username),
		logger.String("email", email),
	)

	enabled := true
	user := gocloak.User{
		Username:      &username,
		Email:         &email,
		Enabled:       &enabled,
		EmailVerified: &enabled,
	}

	userID, err := c.client.CreateUser(ctx, c.token.AccessToken, c.config.Realm, user)
	if err != nil {
		logger.Logger.Error("Failed to create user", logger.Error(err))
		return "", fmt.Errorf("failed to create user: %w", err)
	}

	// Set password
	err = c.client.SetPassword(ctx, c.token.AccessToken, userID, c.config.Realm, password, false)
	if err != nil {
		logger.Logger.Error("Failed to set password", logger.Error(err))
		return "", fmt.Errorf("failed to set password: %w", err)
	}

	logger.Logger.Info("User created successfully", logger.String("user_id", userID))
	return userID, nil
}

// AssignRole assigns a role to a user
func (c *Client) AssignRole(ctx context.Context, userID, roleName string) error {
	logger.Logger.Info("Assigning role to user",
		logger.String("user_id", userID),
		logger.String("role", roleName),
	)

	// Get role
	role, err := c.client.GetRealmRole(ctx, c.token.AccessToken, c.config.Realm, roleName)
	if err != nil {
		logger.Logger.Error("Failed to get role", logger.Error(err))
		return fmt.Errorf("failed to get role: %w", err)
	}

	// Assign role to user
	err = c.client.AddRealmRoleToUser(ctx, c.token.AccessToken, c.config.Realm, userID, []gocloak.Role{*role})
	if err != nil {
		logger.Logger.Error("Failed to assign role", logger.Error(err))
		return fmt.Errorf("failed to assign role: %w", err)
	}

	logger.Logger.Info("Role assigned successfully")
	return nil
}

// RefreshToken refreshes the admin access token
func (c *Client) RefreshToken(ctx context.Context) error {
	token, err := c.client.RefreshToken(ctx, c.token.RefreshToken, c.config.ClientID, c.config.ClientSecret, c.config.Realm)
	if err != nil {
		return fmt.Errorf("failed to refresh token: %w", err)
	}

	c.token = token
	return nil
}

// Close closes the Keycloak client
func (c *Client) Close() error {
	// Logout admin session
	err := c.client.LogoutPublicClient(context.Background(), c.config.ClientID, c.config.Realm, c.token.AccessToken, c.token.RefreshToken)
	if err != nil {
		logger.Logger.Warn("Failed to logout from Keycloak", logger.Error(err))
	}
	return nil
}

