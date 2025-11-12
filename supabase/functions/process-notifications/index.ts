import { serve } from "https://deno.land/std@0.177.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
console.log("FUNCTION_SECRET =", Deno.env.get("FUNCTION_SECRET"));

serve(async (req) => {
  try {
    // --- Authorization check ---
    const authHeader = req.headers.get("Authorization");
    const FUNCTION_SECRET = Deno.env.get("FUNCTION_SECRET");
    if (!authHeader || authHeader !== `Bearer ${FUNCTION_SECRET}`) {
      return new Response(JSON.stringify({ error: "Unauthorized" }), { status: 401 });
    }

    // --- Setup Supabase client ---
    const PROJECT_URL = Deno.env.get("PROJECT_URL")!;
    const SERVICE_ROLE_KEY = Deno.env.get("SERVICE_ROLE_KEY")!;
    const supabase = createClient(PROJECT_URL, SERVICE_ROLE_KEY, { db: { schema: "public" } });

    // --- Setup SendGrid ---
    const SENDGRID_API_KEY = Deno.env.get("SENDGRID_API_KEY")!;
    const FROM_EMAIL = Deno.env.get("FROM_EMAIL")!;
    const FROM_NAME = Deno.env.get("FROM_NAME") || "Salon Booking App";

    console.log("Checking for pending notifications...");

    // --- Fetch pending notifications ---
    const { data: pending, error: fetchErr } = await supabase
      .from("notifications")
      .select("*")
      .eq("status", "pending")
      .lte("scheduled_for", new Date().toISOString());

    if (fetchErr) {
      console.error("Error fetching notifications:", fetchErr);
      return new Response(JSON.stringify({ error: fetchErr.message }), { status: 500 });
    }

    if (!pending || pending.length === 0) {
      console.log("No pending notifications to process.");
      return new Response(JSON.stringify({ success: true, count: 0 }), { status: 200 });
    }

    console.log("Found " + pending.length + " notifications to process.");

    let sentCount = 0;
    let failedCount = 0;

    // --- Process each notification ---
    for (const notif of pending) {
      try {
        console.log("Processing notification ID: " + notif.id);

        // --- Get user email from users_details ---
        const { data: userEmail, error: emailErr } = await supabase
          .from("user_details")
          .select("email")
          .eq("id", notif.user_id)
          .single();

        console.log("Checking user_id:", notif.user_id);
        if (emailErr) console.error("Email lookup error:", emailErr);
        else console.log("Email lookup result:", userEmail);

        if (emailErr) {
          console.error("Failed to get email for user " + notif.user_id + ":", emailErr);
          failedCount++;
          continue;
        }

        if (!userEmail?.email) {
          console.error("No email found in users_details for " + notif.user_id);
          failedCount++;
          continue;
        }

        // --- Send email through SendGrid ---
        const payload = {
          personalizations: [{ to: [{ email: userEmail.email }] }],
          from: { email: FROM_EMAIL, name: FROM_NAME },
          subject: notif.title || "Notification from Salon App",
          content: [{ type: "text/plain", value: notif.message || "" }],
        };

        const emailRes = await fetch("https://api.sendgrid.com/v3/mail/send", {
          method: "POST",
          headers: {
            "Authorization": `Bearer ${SENDGRID_API_KEY}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify(payload),
        });

        if (!emailRes.ok) {
          const errText = await emailRes.text();
          console.error("SendGrid error for notif " + notif.id + ":", errText);
          failedCount++;
          continue;
        }

        console.log("Email sent to " + userEmail.email);

        // --- Update notification status to sent ---
        const { error: updateErr } = await supabase
          .from("notifications")
          .update({
            status: "sent",
            sent_at: new Date().toISOString(),
          })
          .eq("id", notif.id);

        if (updateErr) {
          console.error("Failed to update status for " + notif.id + ":", updateErr);
          failedCount++;
          continue;
        }

        console.log("Notification " + notif.id + " marked as sent.");
        sentCount++;

      } catch (innerErr) {
        console.error("Unexpected error for notif " + notif.id + ":", innerErr);
        failedCount++;
      }
    }

    console.log("Summary: " + sentCount + " sent, " + failedCount + " failed.");

    return new Response(
      JSON.stringify({
        success: true,
        processed: pending.length,
        sent: sentCount,
        failed: failedCount,
      }),
      { status: 200 },
    );

  } catch (e) {
    console.error("Fatal error:", e);
    return new Response(JSON.stringify({ error: e.message }), { status: 500 });
  }
});

