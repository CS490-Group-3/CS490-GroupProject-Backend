// supabase/functions/send-email/index.ts
import { serve } from "https://deno.land/std@0.177.0/http/server.ts";

serve(async (req) => {
  try {
    // Authorization check 
    const authHeader = req.headers.get("Authorization");
    const FUNCTION_SECRET = Deno.env.get("FUNCTION_SECRET");

    if (!authHeader || authHeader !== `Bearer ${FUNCTION_SECRET}`) {
      return new Response(JSON.stringify({ error: "Unauthorized" }), { status: 401 });
    }

    const { to, subject, body } = await req.json();

    if (!to || !subject || !body) {
      return new Response(JSON.stringify({ error: "Missing 'to', 'subject', or 'body'" }), { status: 400 });
    }

    // Send email via SendGrid
    const SENDGRID_API_KEY = Deno.env.get("SENDGRID_API_KEY");
    const FROM_EMAIL = Deno.env.get("FROM_EMAIL") || "no-reply@sendgrid.net";
    const FROM_NAME = Deno.env.get("FROM_NAME") || "Salon Booking App";

    const response = await fetch("https://api.sendgrid.com/v3/mail/send", {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${SENDGRID_API_KEY}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        personalizations: [{ to: [{ email: to }] }],
        from: { email: FROM_EMAIL, name: FROM_NAME },
        subject,
        content: [{ type: "text/plain", value: body }],
      }),
    });

    if (!response.ok) {
      const err = await response.text();
      console.error("SendGrid error:", err);
      return new Response(JSON.stringify({ error: err }), { status: response.status });
    }

    return new Response(JSON.stringify({ success: true }), { status: 200 });
  } catch (e) {
    console.error("Edge function error:", e);
    return new Response(JSON.stringify({ error: e.message }), { status: 500 });
  }
});

