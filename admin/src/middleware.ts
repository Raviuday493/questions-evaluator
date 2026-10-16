import { NextResponse, type NextRequest } from "next/server";

// Cheap presence check so unauthenticated visitors land on /login without a flash of the shell.
// The backend validates the session on every request; the API client handles expiry.
export function middleware(request: NextRequest) {
  const { pathname, search } = request.nextUrl;
  const hasSession = request.cookies.has("qpi_admin_session");
  if (!hasSession && pathname !== "/login") {
    const target = pathname === "/" ? "/login" : `/login?next=${encodeURIComponent(pathname + search)}`;
    // Build the redirect from the Host the browser actually used: `nextUrl` can report the server's
    // bind host (e.g. "localhost" for 127.0.0.1), which would lose the cookie jar or the proxy domain.
    const host = request.headers.get("host") ?? request.nextUrl.host;
    const proto = request.headers.get("x-forwarded-proto") ?? request.nextUrl.protocol.replace(":", "");
    return NextResponse.redirect(new URL(target, `${proto}://${host}`));
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico|icon.svg).*)"],
};
