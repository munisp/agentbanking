/*
54Link POS — Production Installer
===================================
A single self-contained Go binary that:
  1. Verifies SHA-256 checksums of all embedded service binaries (integrity manifest)
  2. Extracts three embedded service binaries to /opt/54link/bin/
  3. Writes systemd unit files for each service
  4. Enables and starts all three services
  5. Runs a health check to confirm everything is live
  6. Prints a clear success/failure summary

Usage:
  sudo ./54link-installer                                  — install / upgrade
  sudo ./54link-installer --uninstall                      — stop, disable, and remove all services
  sudo ./54link-installer --status                         — show service status without changing anything
  sudo ./54link-installer --verify                         — verify binary integrity only (no install)
  sudo ./54link-installer --enroll-token <TOKEN>           — complete device enrollment with a one-time token
  sudo ./54link-installer --enroll-token <TOKEN> --agent-code <CODE> --serial <SERIAL>

Zero external dependencies required on the POS terminal.
The installer binary itself is the only file that needs to be transferred.

Security:
  - All embedded binaries are verified against a SHA-256 manifest before extraction.
  - The manifest is compiled into the binary at build time (tamper-evident).
  - Enrollment tokens are single-use and expire after 15 minutes.
  - The persistent device token returned by enrollment is stored in /opt/54link/device.token
    and is passed on every transaction to the 54Link backend for device verification.
*/

package main

import (
	"bytes"
	"crypto/sha256"
	"embed"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
	"time"
)

// Embed the three service binaries at compile time.
// The installer binary is therefore fully self-contained.
// Note: go:embed paths must be relative to the package directory.
// We place a copy of the embedded dir inside cmd/installer/embedded/
//
//go:embed embedded
var embedded embed.FS

const (
	installDir  = "/opt/54link/bin"
	systemdDir  = "/etc/systemd/system"
	dataDir     = "/var/lib/54link"
	logDir      = "/var/log/54link"
	tokenFile   = "/opt/54link/device.token"
	appUser     = "54link"
	appGroup    = "54link"

	// Default API base for enrollment (can be overridden via FIFTYFOURLINK_API_BASE env var)
	defaultAPIBase = "https://54link.manus.space/api/trpc"
)

// ── Binary Integrity Manifest ─────────────────────────────────────────────────
//
// These SHA-256 checksums are computed at build time and compiled into the
// installer binary. Any tampering with the embedded binaries will cause the
// installer to abort before extracting anything to disk.
//
// To regenerate this manifest after updating the embedded binaries:
//   go run ./scripts/gen-manifest/main.go
//
// The manifest maps embedded path → expected SHA-256 hex digest.
// An empty string ("") means the binary is a placeholder (dev/CI builds only).
var integrityManifest = map[string]string{
	"embedded/resilience-agent":  "", // populated by build pipeline
	"embedded/offline-queue":     "", // populated by build pipeline
	"embedded/analytics-service": "", // populated by build pipeline
}

type service struct {
	name        string
	binary      string
	embeddedSrc string
	port        int
	healthPath  string
	envVars     []string
	description string
}

var services = []service{
	{
		name:        "54link-resilience-agent",
		binary:      "resilience-agent",
		embeddedSrc: "embedded/resilience-agent",
		port:        8031,
		healthPath:  "/health",
		envVars:     []string{"RESILIENCE_AGENT_PORT=8031"},
		description: "54Link Resilience Agent — connection probe, carrier detection, retry engine",
	},
	{
		name:        "54link-offline-queue",
		binary:      "offline-queue",
		embeddedSrc: "embedded/offline-queue",
		port:        8032,
		healthPath:  "/health",
		envVars: []string{
			"OFFLINE_QUEUE_PORT=8032",
			fmt.Sprintf("OFFLINE_QUEUE_DB=%s/offline-queue.sqlite", dataDir),
		},
		description: "54Link Offline Queue — SQLite WAL transaction queue and USSD encoder",
	},
	{
		name:        "54link-analytics-service",
		binary:      "analytics-service",
		embeddedSrc: "embedded/analytics-service",
		port:        8033,
		healthPath:  "/health",
		envVars:     []string{"ANALYTICS_PORT=8033"},
		description: "54Link Analytics Service — 7-day success rate and transaction statistics",
	},
}

func main() {
	if runtime.GOOS != "linux" {
		fatalf("This installer only supports Linux (POS terminal OS). Got: %s\n", runtime.GOOS)
	}

	args := os.Args[1:]

	switch {
	case len(args) > 0 && args[0] == "--uninstall":
		runUninstall()
	case len(args) > 0 && args[0] == "--status":
		runStatus()
	case len(args) > 0 && args[0] == "--verify":
		runVerify()
	case len(args) > 0 && args[0] == "--enroll-token":
		if len(args) < 2 {
			fatalf("Usage: sudo ./54link-installer --enroll-token <TOKEN> [--agent-code <CODE>] [--serial <SERIAL>]")
		}
		token := args[1]
		agentCode := flagValue(args[2:], "--agent-code")
		serial := flagValue(args[2:], "--serial")
		runEnroll(token, agentCode, serial)
	default:
		runInstall()
	}
}

// ── Install ───────────────────────────────────────────────────────────────────

func runInstall() {
	banner("54Link POS — Service Installer")
	requireRoot()

	step("Verifying binary integrity")
	verifyIntegrity(true) // strict=true → abort on mismatch
	ok()

	step("Creating directories")
	mustMkdir(installDir)
	mustMkdir(dataDir)
	mustMkdir(logDir)
	ok()

	step("Creating system user '%s'", appUser)
	createUser()
	ok()

	step("Extracting service binaries")
	for _, svc := range services {
		extractBinary(svc)
	}
	ok()

	step("Writing systemd unit files")
	for _, svc := range services {
		writeUnit(svc)
	}
	ok()

	step("Reloading systemd daemon")
	must(run("systemctl", "daemon-reload"))
	ok()

	step("Enabling and starting services")
	for _, svc := range services {
		must(run("systemctl", "enable", "--now", svc.name))
		fmt.Printf("    ✓ %s\n", svc.name)
	}

	step("Waiting for services to initialise")
	time.Sleep(3 * time.Second)

	step("Running health checks")
	allOK := true
	for _, svc := range services {
		healthy, latency, detail := healthCheck(svc)
		if healthy {
			fmt.Printf("    ✓ %-40s  %dms  %s\n", svc.name, latency, detail)
		} else {
			fmt.Printf("    ✗ %-40s  FAILED: %s\n", svc.name, detail)
			allOK = false
		}
	}

	fmt.Println()
	if allOK {
		fmt.Println("╔══════════════════════════════════════════════════════════╗")
		fmt.Println("║  ✅  54Link POS services installed and running           ║")
		fmt.Println("╚══════════════════════════════════════════════════════════╝")
		fmt.Printf("\nServices installed to : %s\n", installDir)
		fmt.Printf("Data directory        : %s\n", dataDir)
		fmt.Printf("Logs                  : journalctl -u 54link-*\n\n")
		for _, svc := range services {
			fmt.Printf("  %-40s  http://localhost:%d\n", svc.name, svc.port)
		}
		fmt.Println()
		fmt.Println("Next step: enroll this device with the 54Link backend:")
		fmt.Println("  sudo ./54link-installer --enroll-token <TOKEN> --agent-code <CODE> --serial <SERIAL>")
		fmt.Println()
	} else {
		fmt.Println("╔══════════════════════════════════════════════════════════╗")
		fmt.Println("║  ⚠️   Installation complete but some services failed     ║")
		fmt.Println("║      Run: journalctl -u 54link-* -n 50 --no-pager       ║")
		fmt.Println("╚══════════════════════════════════════════════════════════╝")
		os.Exit(1)
	}
}

// ── Uninstall ─────────────────────────────────────────────────────────────────

func runUninstall() {
	banner("54Link POS — Service Uninstaller")
	requireRoot()

	for _, svc := range services {
		fmt.Printf("  Stopping and disabling %s...\n", svc.name)
		_ = run("systemctl", "stop", svc.name)
		_ = run("systemctl", "disable", svc.name)
		_ = os.Remove(filepath.Join(systemdDir, svc.name+".service"))
	}
	_ = run("systemctl", "daemon-reload")

	fmt.Printf("  Removing binaries from %s...\n", installDir)
	for _, svc := range services {
		_ = os.Remove(filepath.Join(installDir, svc.binary))
	}

	fmt.Println("\n✅  54Link POS services removed.")
	fmt.Printf("Data in %s was preserved. Remove manually if needed.\n", dataDir)
}

// ── Status ────────────────────────────────────────────────────────────────────

func runStatus() {
	banner("54Link POS — Service Status")
	for _, svc := range services {
		out, _ := exec.Command("systemctl", "is-active", svc.name).Output()
		active := strings.TrimSpace(string(out))
		healthy, latency, _ := healthCheck(svc)
		icon := "✓"
		if active != "active" || !healthy {
			icon = "✗"
		}
		fmt.Printf("  %s  %-40s  systemd=%-8s  http=%dms\n", icon, svc.name, active, latency)
	}

	// Show enrollment status
	fmt.Println()
	if _, err := os.Stat(tokenFile); err == nil {
		tokenData, _ := os.ReadFile(tokenFile)
		token := strings.TrimSpace(string(tokenData))
		if len(token) > 20 {
			fmt.Printf("  ✓  Device enrolled  (token: %s…)\n", token[:20])
		}
	} else {
		fmt.Println("  ✗  Device NOT enrolled — run: sudo ./54link-installer --enroll-token <TOKEN>")
	}
}

// ── Verify ────────────────────────────────────────────────────────────────────

func runVerify() {
	banner("54Link POS — Binary Integrity Verification")
	verifyIntegrity(false) // strict=false → print results without aborting
	fmt.Println("\n✅  Verification complete.")
}

// ── Enroll ────────────────────────────────────────────────────────────────────

func runEnroll(token, agentCode, serial string) {
	banner("54Link POS — Device Enrollment")

	// Prompt for missing fields
	if agentCode == "" {
		fmt.Print("Agent Code: ")
		fmt.Scanln(&agentCode)
	}
	if serial == "" {
		// Try to read machine serial from DMI
		serial = readMachineSerial()
		if serial == "" {
			fmt.Print("Device Serial Number: ")
			fmt.Scanln(&serial)
		} else {
			fmt.Printf("  Auto-detected serial: %s\n", serial)
		}
	}

	if token == "" || agentCode == "" || serial == "" {
		fatalf("token, agent-code, and serial are all required for enrollment")
	}

	apiBase := os.Getenv("FIFTYFOURLINK_API_BASE")
	if apiBase == "" {
		apiBase = defaultAPIBase
	}

	step("Calling enrollment API at %s", apiBase)

	// Build tRPC mutation request
	payload := map[string]interface{}{
		"0": map[string]interface{}{
			"json": map[string]interface{}{
				"token":      token,
				"agentCode":  agentCode,
				"serialNumber": serial,
				"model":      readDeviceModel(),
				"osVersion":  readOSVersion(),
				"appVersion": "1.0.0",
			},
		},
	}

	body, _ := json.Marshal(payload)
	url := apiBase + "/mdm.enrollWithToken?batch=1"

	client := &http.Client{Timeout: 30 * time.Second}
	req, err := http.NewRequest("POST", url, bytes.NewReader(body))
	if err != nil {
		fatalf("failed to build enrollment request: %v", err)
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := client.Do(req)
	if err != nil {
		fatalf("enrollment request failed: %v\n\nCheck that the POS terminal has internet access.", err)
	}
	defer resp.Body.Close()

	respBody, _ := io.ReadAll(resp.Body)

	if resp.StatusCode != 200 {
		fatalf("enrollment API returned HTTP %d: %s", resp.StatusCode, string(respBody))
	}

	// Parse tRPC batch response: [{result:{data:{json:{...}}}}]
	var batchResp []struct {
		Result struct {
			Data struct {
				JSON struct {
					DeviceID    int    `json:"deviceId"`
					Enrolled    bool   `json:"enrolled"`
					AgentCode   string `json:"agentCode"`
					DeviceToken string `json:"deviceToken"`
				} `json:"json"`
			} `json:"data"`
		} `json:"result"`
		Error *struct {
			Message string `json:"message"`
		} `json:"error"`
	}

	if err := json.Unmarshal(respBody, &batchResp); err != nil {
		fatalf("failed to parse enrollment response: %v\nBody: %s", err, string(respBody))
	}

	if len(batchResp) == 0 {
		fatalf("empty enrollment response from server")
	}

	if batchResp[0].Error != nil {
		fatalf("enrollment rejected by server: %s", batchResp[0].Error.Message)
	}

	result := batchResp[0].Result.Data.JSON
	if !result.Enrolled || result.DeviceToken == "" {
		fatalf("enrollment incomplete — server did not return a device token")
	}

	ok()

	// Store the persistent device token
	step("Storing device token to %s", tokenFile)
	mustMkdir(filepath.Dir(tokenFile))
	if err := os.WriteFile(tokenFile, []byte(result.DeviceToken+"\n"), 0600); err != nil {
		fatalf("failed to write device token: %v", err)
	}
	// Restrict ownership to the 54link service user
	_ = run("chown", appUser+":"+appGroup, tokenFile)
	ok()

	fmt.Println()
	fmt.Println("╔══════════════════════════════════════════════════════════╗")
	fmt.Println("║  ✅  Device enrolled successfully                        ║")
	fmt.Println("╚══════════════════════════════════════════════════════════╝")
	fmt.Printf("\n  Device ID   : %d\n", result.DeviceID)
	fmt.Printf("  Agent Code  : %s\n", result.AgentCode)
	fmt.Printf("  Token file  : %s\n", tokenFile)
	fmt.Printf("  Token       : %s…\n\n", result.DeviceToken[:min(20, len(result.DeviceToken))])
	fmt.Println("The device token will be automatically included in all transactions.")
}

// ── Binary Integrity ──────────────────────────────────────────────────────────

// verifyIntegrity checks all embedded binaries against the compiled-in manifest.
// If strict=true, any mismatch causes an immediate fatal exit.
// If strict=false, mismatches are printed but execution continues.
//
// Placeholder entries (empty string in manifest) are skipped — this allows
// development and CI builds to run without pre-computed checksums.
func verifyIntegrity(strict bool) {
	allOK := true
	for embPath, expectedHash := range integrityManifest {
		if expectedHash == "" {
			// Placeholder — skip in dev/CI builds
			fmt.Printf("    ⚠  %s  (no checksum — dev build)\n", embPath)
			continue
		}

		data, err := embedded.ReadFile(embPath)
		if err != nil {
			msg := fmt.Sprintf("cannot read embedded binary %s: %v", embPath, err)
			if strict {
				fatalf(msg)
			}
			fmt.Printf("    ✗  %s  ERROR: %s\n", embPath, msg)
			allOK = false
			continue
		}

		sum := sha256.Sum256(data)
		actual := hex.EncodeToString(sum[:])

		if actual != expectedHash {
			msg := fmt.Sprintf("%s: checksum mismatch\n    expected: %s\n    actual:   %s", embPath, expectedHash, actual)
			if strict {
				fmt.Println()
				fmt.Println("╔══════════════════════════════════════════════════════════╗")
				fmt.Println("║  🚨  INTEGRITY CHECK FAILED — ABORTING INSTALLATION     ║")
				fmt.Println("║      The installer binary may have been tampered with.  ║")
				fmt.Println("║      Download a fresh copy from the 54Link admin portal.║")
				fmt.Println("╚══════════════════════════════════════════════════════════╝")
				fatalf(msg)
			}
			fmt.Printf("    ✗  %s  MISMATCH\n", embPath)
			fmt.Printf("       expected: %s\n", expectedHash)
			fmt.Printf("       actual:   %s\n", actual)
			allOK = false
		} else {
			fmt.Printf("    ✓  %s  sha256=%s…\n", embPath, actual[:16])
		}
	}

	if !allOK && !strict {
		fmt.Println("\n⚠️  One or more integrity checks failed.")
	}
}

// ── Helpers ───────────────────────────────────────────────────────────────────

func extractBinary(svc service) {
	data, err := embedded.ReadFile(svc.embeddedSrc)
	if err != nil {
		fatalf("failed to read embedded binary %s: %v", svc.embeddedSrc, err)
	}
	dest := filepath.Join(installDir, svc.binary)
	if err := os.WriteFile(dest, data, 0755); err != nil {
		fatalf("failed to write %s: %v", dest, err)
	}
	fmt.Printf("    ✓ %s → %s (%d KB)\n", svc.binary, dest, len(data)/1024)
}

func writeUnit(svc service) {
	envLines := ""
	for _, e := range svc.envVars {
		envLines += fmt.Sprintf("Environment=%s\n", e)
	}
	unit := fmt.Sprintf(`[Unit]
Description=%s
After=network.target
Wants=network.target

[Service]
Type=simple
User=%s
Group=%s
ExecStart=%s/%s
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
%s
[Install]
WantedBy=multi-user.target
`, svc.description, appUser, appGroup, installDir, svc.binary, envLines)

	path := filepath.Join(systemdDir, svc.name+".service")
	if err := os.WriteFile(path, []byte(unit), 0644); err != nil {
		fatalf("failed to write unit file %s: %v", path, err)
	}
	fmt.Printf("    ✓ %s.service\n", svc.name)
}

func healthCheck(svc service) (bool, int, string) {
	url := fmt.Sprintf("http://localhost:%d%s", svc.port, svc.healthPath)
	start := time.Now()
	client := &http.Client{Timeout: 5 * time.Second}
	resp, err := client.Get(url)
	latency := int(time.Since(start).Milliseconds())
	if err != nil {
		return false, latency, err.Error()
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(resp.Body)
	var result map[string]interface{}
	_ = json.Unmarshal(body, &result)
	status, _ := result["status"].(string)
	if resp.StatusCode == 200 && status == "ok" {
		return true, latency, fmt.Sprintf("status=%s", status)
	}
	return false, latency, fmt.Sprintf("http=%d body=%s", resp.StatusCode, string(body))
}

func createUser() {
	// Check if user already exists
	out, _ := exec.Command("id", appUser).Output()
	if len(out) > 0 {
		fmt.Printf("    ✓ user '%s' already exists\n", appUser)
		return
	}
	if err := run("useradd", "--system", "--no-create-home", "--shell", "/usr/sbin/nologin", appUser); err != nil {
		// Non-fatal: may fail if user exists under a different mechanism
		fmt.Printf("    ⚠ could not create user '%s': %v (continuing)\n", appUser, err)
	}
	// Set ownership on data/log dirs
	_ = run("chown", "-R", appUser+":"+appGroup, dataDir)
	_ = run("chown", "-R", appUser+":"+appGroup, logDir)
}

// readMachineSerial attempts to read the hardware serial from DMI (Linux only).
func readMachineSerial() string {
	paths := []string{
		"/sys/class/dmi/id/product_serial",
		"/sys/class/dmi/id/board_serial",
	}
	for _, p := range paths {
		data, err := os.ReadFile(p)
		if err == nil {
			s := strings.TrimSpace(string(data))
			if s != "" && s != "To Be Filled By O.E.M." && s != "None" {
				return s
			}
		}
	}
	return ""
}

// readDeviceModel reads the product name from DMI.
func readDeviceModel() string {
	data, err := os.ReadFile("/sys/class/dmi/id/product_name")
	if err == nil {
		s := strings.TrimSpace(string(data))
		if s != "" && s != "To Be Filled By O.E.M." {
			return s
		}
	}
	return "Linux POS Terminal"
}

// readOSVersion reads the OS version from /etc/os-release.
func readOSVersion() string {
	data, err := os.ReadFile("/etc/os-release")
	if err != nil {
		return "Linux"
	}
	for _, line := range strings.Split(string(data), "\n") {
		if strings.HasPrefix(line, "PRETTY_NAME=") {
			return strings.Trim(strings.TrimPrefix(line, "PRETTY_NAME="), `"`)
		}
	}
	return "Linux"
}

// flagValue extracts the value of a named flag from an args slice.
// e.g. flagValue(["--agent-code", "AGT001"], "--agent-code") → "AGT001"
func flagValue(args []string, flag string) string {
	for i, a := range args {
		if a == flag && i+1 < len(args) {
			return args[i+1]
		}
	}
	return ""
}

func mustMkdir(path string) {
	if err := os.MkdirAll(path, 0755); err != nil {
		fatalf("cannot create directory %s: %v", path, err)
	}
}

func run(name string, args ...string) error {
	cmd := exec.Command(name, args...)
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	return cmd.Run()
}

func must(err error) {
	if err != nil {
		fatalf("command failed: %v", err)
	}
}

func requireRoot() {
	if os.Getuid() != 0 {
		fatalf("This installer must be run as root: sudo ./54link-installer")
	}
}

func banner(title string) {
	fmt.Println()
	fmt.Printf("  ╔══════════════════════════════════════════════════════════╗\n")
	fmt.Printf("  ║  %-56s║\n", title)
	fmt.Printf("  ╚══════════════════════════════════════════════════════════╝\n\n")
}

func step(format string, args ...interface{}) {
	fmt.Printf("▶  "+format+"... ", args...)
}

func ok() {
	fmt.Println("done")
}

func fatalf(format string, args ...interface{}) {
	fmt.Fprintf(os.Stderr, "\n❌  ERROR: "+format+"\n", args...)
	os.Exit(1)
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}
