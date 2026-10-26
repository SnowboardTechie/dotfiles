# Design Preview Handoffs

## Exploration versus implementation

Exploration intentionally shows competing directions. Implementation needs one approved direction. Before dispatch:

1. Keep the comparison gallery for design history.
2. Create a dedicated page containing only the selected design.
3. Retain controls that demonstrate required adaptability, such as terminal theme or host identity.
4. Remove unsupported visual flourishes so the preview reflects the real renderer's capabilities.
5. Label the page as design intent, not an implementation prescription.

## Remote reachability

A localhost URL or a file path is not a remote preview. Bryan reviews from his laptop and other devices. Before telling
him a preview exists, the parent serves it behind a tailnet URL with the `sgg-preview` workbench, as described under
"Files prepared for Bryan" in `agent-collaboration-previews`. The workbench publishes a tailnet-only HTTPS Serve route for
the artifact folder. The parent probes that exact URL and leads the handoff with it. Don't bind a server to the
Tailscale IP by hand unless the workbench can't start.

Keep the preview only while it's needed (`sgg-preview extend` or `down`). Stop it after the direction is accepted.

## Visual verification

Render the dedicated page at a representative terminal width. Confirm:

- one design only;
- no clipping or status overlap;
- required Nerd Font glyphs render without tofu;
- the chosen theme and host controls change only intended variables; and
- the preview does not imply styling the target renderer cannot produce.

## Web option previews: parent-captured screenshots

A worker's sandbox may be unable to launch the repository's approved browser. Don't send it back for that. The parent
captures the screenshots itself, using its own browser session against the `file://` pages:

- a 2×2 per option: desktop (1280×900) and phone (390×844, `mobile=true`), each in light and dark
  (`Emulation.setDeviceMetricsOverride` plus `Emulation.setEmulatedMedia` `prefers-color-scheme`);
- for each capture, record whether `scrollWidth > clientWidth` (page-wide horizontal overflow);
- save to `screenshots/option-<x>-<device>-<scheme>.png` beside the options, and look at at least one phone-dark and
  one desktop image yourself.

Note in the options README what the parent verified and what stays open for the implementation stage (keyboard tab
order, real-browser checks). Then commit the options folder and comment on the issue: where to open it, a one-line
summary per option, the worker's recommendation, and any new copy that needs approval together with the choice.
