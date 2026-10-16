/** @type {import('next').NextConfig} */
// The admin app is its own origin (e.g. admin.example.edu / localhost:3001). Only the backend's
// admin namespace is proxied, so the browser talks to one origin, the httpOnly session cookie stays
// first-party, and application-user endpoints are not reachable through this site.
const apiBase = (process.env.ADMIN_API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");

const securityHeaders = [
  { key: "X-Frame-Options", value: "DENY" },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "same-origin" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
  { key: "X-Robots-Tag", value: "noindex, nofollow" },
];

const nextConfig = {
  poweredByHeader: false,
  async rewrites() {
    return [{ source: "/api/v1/admin/:path*", destination: `${apiBase}/api/v1/admin/:path*` }];
  },
  async headers() {
    return [{ source: "/:path*", headers: securityHeaders }];
  },
};

export default nextConfig;
