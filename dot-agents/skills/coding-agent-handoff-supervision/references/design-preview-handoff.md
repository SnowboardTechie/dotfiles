# Design Preview Handoffs

## Exploration versus implementation

Exploration intentionally shows competing directions. Implementation needs one approved direction. Before dispatch:

1. Keep the comparison gallery for design history.
2. Create a dedicated page containing only the selected design.
3. Retain controls that demonstrate required adaptability, such as terminal theme or host identity.
4. Remove unsupported visual flourishes so the preview reflects the real renderer's capabilities.
5. Label the page as design intent, not an implementation prescription.

## Remote reachability

A localhost URL is not a remote preview. For Bryan's Studio-hosted disposable previews:

- bind the preview server to Studio's direct Tailscale IP;
- use an unambiguous unused port;
- provide the direct `http://<tailscale-ip>:<port>/...` URL;
- do not substitute a MagicDNS hostname when it triggers HTTPS/SSL handling for a plain HTTP server; and
- fetch the exact remote URL before sharing it.

Keep the server only while the preview is needed. Stop it after implementation is accepted.

## Visual verification

Render the dedicated page at a representative terminal width. Confirm:

- one design only;
- no clipping or status overlap;
- required Nerd Font glyphs render without tofu;
- the chosen theme and host controls change only intended variables; and
- the preview does not imply styling the target renderer cannot produce.
