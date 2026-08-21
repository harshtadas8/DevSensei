import { NextRequest, NextResponse } from "next/server";

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const path = searchParams.get("path");

  if (!path) {
    return NextResponse.json({ error: "Path parameter is required" }, { status: 400 });
  }

  const apiUrl = process.env.BACKEND_API_URL || "http://localhost:8000";

  try {
    const res = await fetch(`${apiUrl}/file?path=${encodeURIComponent(path)}`);
    
    if (!res.ok) {
      return NextResponse.json({ error: "File not found or access denied on backend" }, { status: res.status });
    }

    const data = await res.json();
    return NextResponse.json(data);
  } catch (error: any) {
    return NextResponse.json({ error: `Proxy Error: ${error.message}` }, { status: 500 });
  }
}

