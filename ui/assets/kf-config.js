/* Where the analyst's actions are kept. Leave null to keep them in this browser.
   To use Supabase, run supabase/schema.sql in the project, then set:
     window.KF_SUPABASE = { url: 'https://<project>.supabase.co', anonKey: '<anon public key>' };
   The anon key is public by design: row level security lets it read and insert only.
   Never put the service role key here; this folder is published. */
window.KF_SUPABASE = null;
