import { useState } from "react";
import type { FormEvent } from "react";

interface LoginPageProps {
  onLogin: (user: { name: string; email: string; role: string }, token: string) => void;
}

export default function LoginPage({ onLogin }: LoginPageProps) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
        credentials: "include",
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.error || "Login failed");
        setLoading(false);
        return;
      }
      localStorage.setItem("access_token", data.accessToken);
      localStorage.setItem("refresh_token", data.refreshToken);
      onLogin(data.user, data.accessToken);
    } catch {
      setError("Network error — please try again");
    }
    setLoading(false);
  }

  return (
    <div style={{
      minHeight: "100vh",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      background: "linear-gradient(135deg, #0a1628 0%, #1a2744 50%, #0d1f3c 100%)",
      fontFamily: "'Inter', -apple-system, sans-serif",
    }}>
      <div style={{
        width: 420,
        padding: 40,
        background: "rgba(255,255,255,0.05)",
        borderRadius: 16,
        border: "1px solid rgba(255,255,255,0.1)",
        backdropFilter: "blur(20px)",
      }}>
        {/* Logo */}
        <div style={{ textAlign: "center", marginBottom: 32 }}>
          <div style={{
            display: "inline-flex",
            alignItems: "center",
            justifyContent: "center",
            width: 64,
            height: 64,
            borderRadius: 16,
            background: "linear-gradient(135deg, #2563eb, #7c3aed)",
            marginBottom: 16,
            fontSize: 28,
            fontWeight: 800,
            color: "#fff",
          }}>54</div>
          <h1 style={{ color: "#fff", fontSize: 24, margin: "0 0 4px", fontWeight: 700 }}>54link-dev Platform</h1>
          <p style={{ color: "rgba(255,255,255,0.5)", fontSize: 14, margin: 0 }}>Core Banking Administration</p>
        </div>

        {error && (
          <div style={{
            padding: "10px 14px",
            background: "rgba(239,68,68,0.15)",
            border: "1px solid rgba(239,68,68,0.3)",
            borderRadius: 8,
            color: "#fca5a5",
            fontSize: 13,
            marginBottom: 20,
          }}>{error}</div>
        )}

        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: 16 }}>
            <label style={{ display: "block", color: "rgba(255,255,255,0.7)", fontSize: 13, marginBottom: 6, fontWeight: 500 }}>
              Email Address
            </label>
            <input
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              placeholder="admin@54link-dev.ng"
              required
              style={{
                width: "100%",
                padding: "10px 14px",
                background: "rgba(255,255,255,0.08)",
                border: "1px solid rgba(255,255,255,0.15)",
                borderRadius: 8,
                color: "#fff",
                fontSize: 14,
                outline: "none",
                boxSizing: "border-box",
              }}
            />
          </div>

          <div style={{ marginBottom: 24 }}>
            <label style={{ display: "block", color: "rgba(255,255,255,0.7)", fontSize: 13, marginBottom: 6, fontWeight: 500 }}>
              Password
            </label>
            <input
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              placeholder="Enter password"
              required
              style={{
                width: "100%",
                padding: "10px 14px",
                background: "rgba(255,255,255,0.08)",
                border: "1px solid rgba(255,255,255,0.15)",
                borderRadius: 8,
                color: "#fff",
                fontSize: 14,
                outline: "none",
                boxSizing: "border-box",
              }}
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            style={{
              width: "100%",
              padding: "12px",
              background: loading ? "#4b5563" : "linear-gradient(135deg, #2563eb, #7c3aed)",
              border: "none",
              borderRadius: 8,
              color: "#fff",
              fontSize: 15,
              fontWeight: 600,
              cursor: loading ? "wait" : "pointer",
              transition: "opacity 0.2s",
            }}
          >
            {loading ? "Signing in..." : "Sign In"}
          </button>
        </form>

        {/* Demo credentials */}
        <div style={{
          marginTop: 24,
          padding: 16,
          background: "rgba(255,255,255,0.03)",
          borderRadius: 8,
          border: "1px solid rgba(255,255,255,0.06)",
        }}>
          <p style={{ color: "rgba(255,255,255,0.4)", fontSize: 11, margin: "0 0 8px", textTransform: "uppercase", letterSpacing: 1 }}>
            Demo Credentials
          </p>
          <div style={{ display: "grid", gap: 4, fontSize: 12, color: "rgba(255,255,255,0.6)" }}>
            <div><b style={{ color: "rgba(255,255,255,0.8)" }}>Admin:</b> admin@54link-dev.ng / admin</div>
            <div><b style={{ color: "rgba(255,255,255,0.8)" }}>Operations:</b> ops@54link-dev.ng / ops123</div>
            <div><b style={{ color: "rgba(255,255,255,0.8)" }}>Compliance:</b> compliance@54link-dev.ng / comp123</div>
            <div><b style={{ color: "rgba(255,255,255,0.8)" }}>Treasury:</b> treasury@54link-dev.ng / treas123</div>
            <div><b style={{ color: "rgba(255,255,255,0.8)" }}>Branch:</b> branch@54link-dev.ng / branch123</div>
          </div>
        </div>

        <p style={{ textAlign: "center", color: "rgba(255,255,255,0.3)", fontSize: 11, marginTop: 24 }}>
          54link-dev Platform v2.0 — Africa-First Core Banking
        </p>
      </div>
    </div>
  );
}
