// ~/.finicky.js — managed via dotfiles (dot-finicky.js, stowed)
//
// Precedence (first match wins):
//   1. native-app handoffs       2. Safari URL pins
//   3. Google + Mail/Messages    (personal-source overrides for ambiguous Google URLs)
//   4. Vivaldi work URL pins     5. Vivaldi work GitHub orgs
//   6. Mail.app → Safari         7. work-leaning source apps → Vivaldi
//   default → Zen

const BUNDLE = {
  zen:     "app.zen-browser.zen",
  vivaldi: "com.vivaldi.Vivaldi",
  safari:  "com.apple.Safari",
  music:   "com.apple.Music",
  zoom:    "us.zoom.xos",
  slack:   "com.tinyspeck.slackmacgap",
};

const WORK_SOURCE_BUNDLES = [
  "com.tinyspeck.slackmacgap",      // Slack
  "com.anthropic.claudefordesktop", // Claude desktop
  "us.zoom.xos",                    // Zoom
  "org.alacritty",                  // Alacritty
  "com.apple.Terminal",
  "com.googlecode.iterm2",
  "com.mitchellh.ghostty",
];

// Google is the one work-leaning domain you also use personally, so we honor
// source-app context for it. Other work domains (grants.gov, agile6.com, ...) stay
// pinned to Vivaldi regardless of source.
const isGoogleHost = (host) =>
  /(^|\.)(google\.com|gmail\.com|googleusercontent\.com)$/.test(host || "");

export default {
  defaultBrowser: BUNDLE.zen,

  handlers: [
    // 1. Native-app handoffs ────────────────────────────────────────────
    {
      match: ["*.zoom.us/j/*", "zoom.us/j/*", "*.zoom.us/my/*", "*.zoom.us/s/*"],
      browser: BUNDLE.zoom,
    },
    { match: "music.apple.com/*", browser: BUNDLE.music },
    {
      match: ["*.slack.com/archives/*", "app.slack.com/client/*", "*.slack.com/files/*"],
      browser: BUNDLE.slack,
    },

    // 2. Safari URL pins: banking + Apple ecosystem ────────────────────
    {
      match: [
        "usaa.com/*",              "*.usaa.com/*",
        "penfed.org/*",            "*.penfed.org/*",
        "chase.com/*",             "*.chase.com/*",
        "nfcu.org/*",              "*.nfcu.org/*",
        "navyfederal.org/*",       "*.navyfederal.org/*",
        "edfinancial.com/*",       "*.edfinancial.com/*",
        "midstateelectric.coop/*", "*.midstateelectric.coop/*",
      ],
      browser: BUNDLE.safari,
    },
    {
      match: ["icloud.com/*", "*.icloud.com/*", "apple.com/*", "*.apple.com/*"],
      browser: BUNDLE.safari,
    },

    // 3. Personal-source override for Google URLs ───────────────────────
    //    Google from Mail.app → Safari (matches your Mail-is-Apple-ecosystem habit)
    {
      match: (url, { opener }) =>
        opener?.bundleId === "com.apple.mail" && isGoogleHost(url.host),
      browser: BUNDLE.safari,
    },
    //    Google from Messages → Zen (personal context wins for chat-shared links)
    {
      match: (url, { opener }) =>
        opener?.bundleId === "com.apple.MobileSMS" && isGoogleHost(url.host),
      browser: BUNDLE.zen,
    },

    // 4. Vivaldi URL pins: work domains ─────────────────────────────────
    {
      match: [
        // grants / federal customer
        "grants.gov/*",                  "*.grants.gov/*",
        "commongrants.org/*",            "*.commongrants.org/*",
        "commongrants.fider.io/*",
        "simplergrants.fider.io/*",
        "philanthropydatacommons.org/*", "*.philanthropydatacommons.org/*",
        "cms.gov/*",                     "*.cms.gov/*",
        // Agile6 + partners + tools
        "agile6.com/*",                  "*.agile6.com/*",
        "unanet.biz/*",                  "*.unanet.biz/*",
        "navasage.atlassian.net/*",
        // Google (all)
        "google.com/*",                  "*.google.com/*",
        "gmail.com/*",                   "*.gmail.com/*",
        "*.googleusercontent.com/*",
        // AWS
        "signin.aws.amazon.com/*",       "*.signin.aws.amazon.com/*",
        "console.aws.amazon.com/*",      "*.console.aws.amazon.com/*",
      ],
      browser: BUNDLE.vivaldi,
    },

    // 5. Vivaldi URL pins: work GitHub orgs ─────────────────────────────
    {
      match: [
        "github.com/agile6",                          "github.com/agile6/*",
        "github.com/agile-six",                       "github.com/agile-six/*",
        "github.com/HHS",                             "github.com/HHS/*",
        "github.com/navapbc",                         "github.com/navapbc/*",
      ],
      browser: BUNDLE.vivaldi,
    },

    // 6. Source-app: Mail.app → Safari ──────────────────────────────────
    {
      match: (_url, { opener }) => opener?.bundleId === "com.apple.mail",
      browser: BUNDLE.safari,
    },

    // 7. Source-app: work-leaning apps → Vivaldi ────────────────────────
    {
      match: (_url, { opener }) => WORK_SOURCE_BUNDLES.includes(opener?.bundleId ?? ""),
      browser: BUNDLE.vivaldi,
    },
  ],
};
