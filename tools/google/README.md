# tools/google — vendored Google Workspace OAuth helper

**Why this directory exists.** The `google-workspace` skill lives at
`~/.hermes/skills/.archive/productivity/google-workspace/` (quarantined under the
context-opt policy). Rather than reactivate it in the shared skills tree — which
belongs to the default profile, not this one — the two files needed for read-only
Gmail auth were **vendored here**, unmodified except for the scope list.

**Provenance**

- `setup.py` — verbatim copy of
  `~/.hermes/skills/.archive/productivity/google-workspace/scripts/setup.py`
  (514 lines, upstream author: Nous Research, MIT). **One deliberate change**,
  documented in the file itself: `SCOPES` narrowed from 8 scopes to
  `gmail.readonly` alone (see below).
- `_hermes_home.py` — verbatim copy of the sibling module it imports, so the
  script runs standalone. Unmodified.
- `gws.sh`, `check_scopes.py` — written for this project.

**The scope change (do not revert without owner sign-off)**

Upstream requests eight scopes: `gmail.readonly`, `gmail.send`, `gmail.modify`,
`calendar`, `drive`, `contacts.readonly`, `spreadsheets`, `documents`. The owner
rule is *"Gmail: read-only. `gmail.readonly` only."* Reading LinkedIn job-alert
emails needs exactly one of those eight. Requesting the rest would exceed the
authorisation given — `gmail.send` alone is the ability to mail as the owner, and
`gmail.modify` includes delete.

**The token lives with the project, not with a Hermes profile**

`setup.py` stores the token at `$HERMES_HOME/google_token.json`. Inside a Hermes
session `HERMES_HOME` is a *profile* directory, so running `setup.py` raw would
couple the Gmail token to whichever of the five interchangeable lanes ran it.
`gws.sh` pins:

```
HERMES_HOME=~/hermes-workspace/jobsearch/var/gws-home
```

so the token is lane-independent **and** inside `jobsearch/.gitignore`'s `*`
guard — it can never reach the public repo this workspace sits inside.

**Always use the wrapper.** Never run `setup.py` directly.

```bash
cd ~/hermes-workspace/jobsearch

tools/google/gws.sh --check                        # AUTHENTICATED / NOT_AUTHENTICATED
tools/google/gws.sh --client-secret /path/to/client_secret.json
tools/google/gws.sh --auth-url                     # prints the consent URL
tools/google/gws.sh --auth-code "URL_OR_CODE"      # completes the exchange
tools/google/check_scopes.py                       # PROVES read-only, fails on any over-grant
tools/google/gws.sh --revoke                       # revoke and delete
```

**Dependencies are NOT installed by this script here.** Its pins
(`google-api-python-client==2.194.0`, `google-auth==2.55.1`,
`google-auth-oauthlib==1.3.1`, `google-auth-httplib2==0.3.1`, `httplib2==0.32.0`,
`pyasn1==0.6.4`) all match the Hermes venv exactly — verified 2026-10-13 — so
`_ensure_deps()` is a no-op and no pip install occurs.

**Known limitation, verified 2026-10-13:** while the Google Cloud project's OAuth
consent screen is in **Testing** status, Google expires refresh tokens after
**7 days** (`invalid_grant` on refresh). `gmail.readonly` is a restricted scope,
so it is not covered by the exemption for openid/email/profile. A daily cron
would therefore break roughly weekly unless the app is published. See HANDOFF
section 13.
