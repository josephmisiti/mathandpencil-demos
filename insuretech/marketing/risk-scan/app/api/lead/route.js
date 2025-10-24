export async function POST(request) {
  const data = await request.json();
  // In a real implementation, persist to a DB or send to a webhook/CRM.
  // For now, just echo back the payload.
  return new Response(JSON.stringify({ ok: true, received: data }), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

