# Triage Labels

The skills speak in terms of five canonical triage roles. This file maps those roles to the actual label strings used
in this workspace's Forgejo tracker, `<owner>/<repo>`.

| Label in mattpocock/skills | Label in our tracker | Meaning                                  |
| -------------------------- | -------------------- | ---------------------------------------- |
| `needs-triage`             | `needs-triage`       | Maintainer needs to evaluate this issue  |
| `needs-info`               | `needs-info`         | Waiting on reporter for more information |
| `ready-for-agent`          | `ready-for-agent`    | Fully specified, ready for an AFK agent  |
| `ready-for-human`          | `ready-for-human`    | Requires human implementation            |
| `wontfix`                  | `wontfix`            | Will not be actioned                     |

When a skill mentions a role (e.g. "apply the AFK-ready triage label"), use the corresponding label string from this
table.

Edit the "Label in our tracker" column to match whatever vocabulary you actually use.

## `ready-for-agent` starts a build here

Bryan's `loop-issue` builds, unattended, any issue in this repository that carries the literal label
`ready-for-agent`. `/to-spec` and `/to-tickets` put the `ready-for-agent` role on everything they publish, and
`/triage` puts it on every issue it judges ready. So with the row above as it stands, publishing a spec or tickets,
or triaging an issue to ready, is approval to build it.

That mapping is a choice. Keep it where Bryan wants issues built automatically. Anywhere else, map the role to
another label (for example `agent-ready`): the skills then apply that, and nothing picks the issues up.

## Category labels

`/triage` also gives every issue one of two category roles. They aren't configurable in his setup; they're listed
here so they get created with the rest.

| Role          | Label in our tracker | Meaning                       |
| ------------- | -------------------- | ----------------------------- |
| `bug`         | `bug`                | Something is broken           |
| `enhancement` | `enhancement`        | New feature or improvement    |

## Creating the labels

A new Forgejo repository has none of these labels, and `tea issues edit --add-labels` with a missing name adds nothing
and still exits 0. Create each missing one once, before the first `/to-spec`, `/to-tickets` or `/triage`:

```sh
R="--repo <owner>/<repo> --login <host>"
tea labels list $R --output json | jq -r '.[].name'
tea labels create $R --name "<label>" --color <rrggbb> --description "<meaning>"
```

List first and create only the names that are missing: creating a name that already exists makes a duplicate label.
