import { createClient } from "@supabase/supabase-js";

let serviceClient;

/**
 * Returns a Supabase client authenticated with the service-role key.
 * This client bypasses Row Level Security and should only be used in
 * server-side contexts (Next.js API routes, Server Actions, etc.).
 *
 * NOTE: NEXT_PUBLIC_SUPABASE_SERVICE_KEY is exposed to the browser because
 * of the NEXT_PUBLIC_ prefix. Avoid calling this function in client components.
 */
export function getSupabaseServiceClient() {
  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const serviceKey = process.env.NEXT_PUBLIC_SUPABASE_SERVICE_KEY;

  if (!supabaseUrl || !serviceKey) {
    return null;
  }

  if (!serviceClient) {
    serviceClient = createClient(supabaseUrl, serviceKey, {
      auth: {
        autoRefreshToken: false,
        persistSession: false,
      },
    });
  }

  return serviceClient;
}
