# F-Droid distribution tooling

The TV and phone/tablet recipes select `fdroidTv` and `fdroidAndroid` from the
same source commit. These editions include 20 starter presets, an explicitly
requested collection download and no app updater. The full GitHub APKs and
canonical Native core AAR retain the complete collection.

`metadata/` contains local validation recipes. Synchronization generates the
actual submission recipes from a complete, published GitHub release's
`release-version.json`, including its exact source SHA and Android version code.
Do not manually update version floors in `app/build.gradle` to match a release.

Prepare a task-specific environment from the repository root:

```sh
python3 -m venv .venv-fdroid
.venv-fdroid/bin/pip install -r tools/fdroid/requirements.txt
.venv-fdroid/bin/python -m unittest discover -s .github/scripts/tests -v
```

Run `../../.venv-fdroid/bin/fdroid lint -f nl.neerdael.projectmtv
nl.neerdael.projectm` from this directory. `config/categories.yml` is the minimal
local lint fixture for these two recipes; it does not replace upstream's
category configuration. Real source builds also run F-Droid's scanner. The
recipe removes archived research evidence from the build checkout, retaining
the actual app/engine sources, build tools and license notices.

Generate recipes without credentials or writes to GitLab:

```sh
.venv-fdroid/bin/python .github/scripts/fdroid_sync.py check \
  --release-json build/release-version.json --output build/fdroid-metadata
```

The HTTP discovery configuration supports subsequent release lines. F-Droid's
automatic updater appends future builds using `Version v%v`; the recipe
substitutes their version name and code into root Gradle properties. The pinned
2.4.5 source parser cannot resolve this app's conditional Gradle package/label,
so `UpdateCheckName: Ignore` preserves the explicit per-edition name. Packaged
application IDs and version identities are verified separately in Android CI.

## GitHub Actions setup

Set the repository Actions secret `FDROID_GITLAB_TOKEN` with a GitLab personal
access token that has `api` scope and repository push access to
`johnneerdael/fdroiddata`. The workflow uses both the REST API and Git over HTTPS;
an API-only fine-grained token is insufficient if it cannot authenticate Git
pushes. The token owner needs Developer or higher access to the fork and
permission to create/update its upstream merge requests. Keep credentials out
of workflow inputs, repository URLs, source files and chat.

The trusted-main `fdroid-sync.yml` workflow runs immediately after successful
publication, every six hours for recovery, or manually. Its `validate_only`
option checks scope and creates/deletes a uniquely named temporary branch.
The synchronization job fails explicitly for missing or insufficient credentials;
it does not block the separate full-core Milkbeat dispatch after publication.

Synchronization reuses the TV submission and creates one separate phone
submission. It replaces only the verified metadata-only branch diff, with an
atomic `--force-with-lease` against its previously observed head, and starts
from current upstream `master`. Unmanaged maintainer fields survive; changes
to managed fields, unknown unsupported fields, unexpected files, conflicting
heads and delayed releases stop the run. No discussion comments are posted.
`metadata-legacy/` is the immutable initial TV submission baseline used to
detect maintainer edits on the first adoption; subsequent managed commits
carry a normalized metadata fingerprint.

After F-Droid accepts a listing, synchronization checks distribution/discovery
compatibility and leaves F-Droid's build history to its own auto updater.
Upstream acceptance, pipeline results and the first public collection delivery
must be verified separately from local/mock tests.
