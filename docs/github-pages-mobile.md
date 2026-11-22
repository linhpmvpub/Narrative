# GitHub Pages mobile entry point

Published URL: https://linhpmvpub.github.io/Narrative/

Only the allowlisted mobile-site directory is published by the mobile-pages
workflow. It contains a responsive entry page, styles/script, icon/manifest and a
public connection origin. No database, captures, tokens, account email or private
feed snapshots are included. Public pages have no credential form. Feed/map links
navigate to the email-restricted Cloudflare gateway, where the app additionally
requires its member token. This preserves same-origin API/auth; no permissive CORS
or browser credential proxy is added. The public page cannot check backend health
through Cloudflare Access and states that explicitly.

This is a stable entry URL, not Python/database hosting. PC, API8888, gateway8890
and protected tunnel must remain running. Cloudflare quick-tunnel hostnames change
on restart. After starting the existing documented tunnel with --allowed-mail,
update mobile-site/connection.json to its HTTPS origin and push main. The Pages
workflow redeploys only this directory. Never remove the email gate or put an app
token in this public config. Stable always-on data access requires an always-on
backend plus stable hostname; not provisioned by GitHub Pages.

Validation: local mobile390px and desktop1440px had no overflow/JS errors; public
artifact scanned against local tokens; remote unauthenticated navigation reached
Cloudflare Access sign-in and did not expose the feed. No private-session login was
performed remotely. See reports/github-pages-preview.json.

Official references:
- https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages
- https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/

Published-site verification passed: HTTP200, mobile links/layout, and click through to Cloudflare Access email gate. Pages workflow45021788424 succeeded. Receipt: reports/github-pages-published.json.
