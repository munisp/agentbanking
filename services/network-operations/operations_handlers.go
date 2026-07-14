package main

// File: services/network-operations/operations_handlers.go
// NOTE: All operations handlers have been integrated into main.go
// This file is kept for reference but all functionality is now in main.go:
// - CanaryRelease, ABTest, Incident, IncidentUpdate models
// - GetCanaryReleases, CreateCanaryRelease handlers
// - GetABTests, CreateABTest handlers
// - GetIncidents, CreateIncident, AddIncidentUpdate, UpdateIncident, HandleIncidentOptions handlers
//
// The handlers are registered in the main() function's v1 router setup.
// Database migrations are automatically applied on startup.
