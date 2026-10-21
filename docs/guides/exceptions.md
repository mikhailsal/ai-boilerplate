# Exceptions

An exception lets one finding stand when fixing it would make the code
worse. It is a reviewed entry in [`quality.toml`](../../quality.toml), never
a marker in the code, a skipped test, or a lowered threshold. The rules are
in [decision 0007](../decisions/0007-common-gates.md#exceptions-and-inline-suppressions).

## Fix first

Run `./quality explain <rule-id>` for what the rule protects and how to fix
it. Most findings have a direct fix: split the long function, move the
module, cover the branch, or pin the dependency. An exception is justified
only when the finding is a deliberate trade-off that a reviewer would accept
again, such as a last-resort handler that must catch every exception.

## Declaring one

Add an `[[exceptions]]` entry that matches exactly one finding:

```toml
[[exceptions]]
rule = "structure.parameters"
path = "services/api/src/api/handlers.py"
symbol = "create_order"
reason = "Mirrors the public HTTP form fields one to one; a parameter object would hide them."
owner = "api maintainers"
expires = 2027-01-31
```

- `rule` is the finding's rule ID, and `path` is the exact file.
- `symbol` narrows it to one function, class, or other named thing; for an
  inline marker, it is the marker text from the marker to the end of the
  comment.
- `reason` says why the trade-off is right, and `owner` who answers for it.
- `expires` makes it temporary: after that date the exception fails and no
  longer applies. Use `review` instead for a permanent exception; after that
  date it still applies but warns until someone reviews it and moves the date.

The change to `quality.toml` is a control-file change, so code owners
review it ([protection guide](protection.md)).

## What cannot be excepted

Rules about the policy, Git, discovery, secrets, tests, coverage, scenarios,
quarantine, and exceptions themselves cannot be excepted, and neither can
usage or environment errors. A flaky test is quarantined instead, with its
own owner and expiry
([decision 0014](../decisions/0014-behavioral-scenarios.md#quarantine)).

## Retiring one

An exception that matches nothing fails the check once its rule has run over
the whole candidate, so an entry disappears together with the code it
covered. When you fix the finding, delete the entry in the same commit.
