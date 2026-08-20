import { NextResponse } from 'next/server';

export async function POST(req: Request) {
  try {
    const body = await req.json();
    
    // In Docker, the frontend container reaches the orchestrator via http://orchestrator:8000
    // Locally, it's http://127.0.0.1:8000
    const apiUrl = process.env.BACKEND_API_URL || "http://orchestrator:8000";
    
    const response = await fetch(`${apiUrl}/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    
    if (!response.ok) {
      return NextResponse.json({ error: "Backend error", status: response.status }, { status: response.status });
    }
    
    // Pass the SSE stream directly back to the client!
    return new Response(response.body, {
      headers: {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
      },
    });
  } catch (error) {
    console.error("Analysis API Error:", error);
    return NextResponse.json({ error: "Failed to connect to orchestrator" }, { status: 500 });
  }
}
