# Builds & Releases

## Automatic publishing

The **Android CI/CD** workflow tests and builds pushes to `main`. **Reviewed PR validation** runs the full suite for eligible PRs targeting `main`. Each successfully tested merge to `main` publishes a stable GitHub Release with its signed APK, Native core AAR, public release notes and SHA-256 checksums, then triggers Milkbeat's core update. Routine PRs need no version bump or manual release command.

### Fork releases

The same `main` workflow publishes to the repository that runs it, including a fork, because release creation uses `GITHUB_REPOSITORY`. A successful merge to the fork's `main` therefore creates a GitHub Release after build, preset and documentation checks pass. Configure the fork's `SIGNING_KEYSTORE_BASE64`, `SIGNING_STORE_PASSWORD`, `SIGNING_KEY_ALIAS` and `SIGNING_KEY_PASSWORD` Actions secrets first; release builds intentionally fail rather than publish APKs signed with a temporary debug key. F-Droid submission sync and Milkbeat dispatch run only in the canonical `johnneerdael/ProjectM-Android` repository.

| Trigger | Result |
|---|---|
| Feature-branch push, or PR targeting another branch | No builds |
| PR targeting `main`, awaiting current review or unresolved findings | Lightweight review gate only; full builds wait |
| Reviewed, ready PR targeting `main`, with all findings resolved | Release tooling, native/JVM, Preset Lab and documentation checks; APK and one Native core AAR artifact with a `-ci.<run>` version suffix |
| Successful merge/push to `main` | Stable TV and touchscreen APKs/Native core AAR, GitHub Release, PR notes, current download details, checksums and Milkbeat dispatch |
| Manual run on `main` | Publishes an unreleased commit or verifies an already complete release; the same commit keeps its version |

Main publishing runs queue instead of canceling previous builds. Obsolete PR validation runs are canceled when a new revision arrives or review eligibility is lost. Versions are tied to source history rather than workflow order: the first first-parent commit after `baseVersionCommit` maps to `baseVersionName`/`baseVersionCode`, and each later commit advances both. The historical 2.1 line started at **2.1.5 / code 37**, and the 2.2 line at **2.2.0 / code 38**. The user-planned Native checkpoint starts the **2.3.0 / code 49** line, anchored to `8b70620339018cfaf5ac05acdb4ea8104dc2eb59` (main before this checkpoint). The first first-parent commit after that anchor receives the base triple; later commits advance it. This is a deliberate minor-release-line change, not a routine PR version bump. Direct pushes containing several commits can leave version gaps; failed builds leave their version unpublished.

CI fetches full tag history and rejects conflicting tags, inconsistent retry metadata and invalid Android codes. An older retry does not replace a newer release as latest. Missing release signing fails a publishing build; PR artifacts may use a temporary debug key.

## Review gate

A ready, mergeable PR targeting `main` needs a clean completed review for its **latest full head SHA** from Claude, Codex or a qualified non-author human. Run Claude and Codex on the initial ready PR. After follow-up pushes, choose one provider with exactly `@claude review` or `@codex review`; a clean final-head signoff from either suffices. Both providers' findings still need disposition, and switching providers never clears unresolved threads or a changes-requested decision. Self-review, elapsed time and a request acknowledgement cannot replace signoff.

### Reviewer setup and triggers

**Claude Code Review** (`.github/workflows/claude-code-review.yml`) uses `anthropics/claude-code-action@v1` and the repository Actions secret `CLAUDE_CODE_OAUTH_TOKEN`. Configure that secret and enable the workflow before relying on Claude reviews. In the repository's **Settings → Actions → General → Workflow permissions**, enable **Allow GitHub Actions to create and approve pull requests** (`can_approve_pull_request_reviews=true`); the trusted publication step uses `github.token` to submit native approval. Keep default workflow permissions read-only (`default_workflow_permissions=read`). This publisher permission does not bypass the required `Reviewed PR builds` status or resolved-thread rules. Automatic review runs on `pull_request_target` `opened` or `ready_for_review` for an initial ready same-repository PR by an actor with repository write, maintain or admin permission, targeting `main`; the preparation script skips drafts and PRs with a prior Claude review. Subsequent pushes do not trigger Claude. External/fork PRs require a trusted on-demand request.

Post a PR comment containing exactly `@claude review` to request a fresh Claude review; comment creation and edits are supported. The requesting actor must have repository write, maintain or admin permission. The workflow and gate share this permission check; PR authorship alone cannot select Claude. Alternatively, run **Claude Code Review** with `pr_number` from the Actions UI on `main`; the same authorization and PR eligibility checks apply. A dispatch from another branch cannot run the reviewer. A trusted-main manual dispatch selects Claude when its authenticated `RUNNING` receipt is published, using the verified workflow run's creation time. It supersedes older Codex code requests; a later authorized comment can select Codex again. Separate Codex security requests remain required.

Codex's automatic opening review is configured in the Codex repository integration, outside Actions. Keep automatic opening review enabled for the initial two-provider cadence. For fully manual mode, turn off automatic review in that integration and request each review with `@codex review` or `@claude review`.

The dedicated Claude reviewer checks out trusted `main` tooling and reads the required PR revision through a constrained GitHub command wrapper. The wrapper permits source reads without exposing API writes; separately allowed GitHub tools publish findings. It does not check out or execute PR code. Its review job has `contents: read`, `pull-requests: write`, `issues: read` and `id-token: write`; its action-issued App token likewise limits content access to read, with PR write and issues read. The action uses that App token for inspection and inline feedback, then revokes it normally. The later trusted publication step uses `github.token`; it does not reuse the revoked App token. It records a current-head `COMMENT` review with a `RUNNING` receipt before invoking Claude, keeping the review gate pending while that run is active. The controller authenticates the receipt against the default-branch Claude workflow run, its event and branch. Completed or canceled runs without a terminal receipt stop the running block without supplying approval; trusted preflight and final reporting receive `actions: read` for this check. The trusted publication step validates the structured `reviewed_commit` (full SHA), `approved` decision and nonempty `summary`, checks the live head, and publishes a native `APPROVED` review only for a successful clean result. Findings produce a `COMMENT` review with a `FINDINGS` receipt and inline threads. The gate requires a subsequent clean current-head code review from Claude or Codex after the findings receipt, plus resolution of all threads. Empty, failed, malformed or stale results cannot sign off.

**Claude Code** (`.github/workflows/claude.yml`) remains the interactive assistant for general mentions and fixes. It retains content, PR and issue write permissions and Actions read access. Exact PR `@claude review` commands route only to the dedicated reviewer; general issue mentions continue through the interactive workflow. The interactive assistant can check out and edit PR code for fixes requested by an authenticated repository writer; the reviewer, controller and status reporter keep their separate trusted-main boundary.

### Completed review signals

Claude qualifies through the trusted publisher's native `APPROVED` review for the full current head SHA, normally posted by `github-actions[bot]`. Reserved Claude/App and Actions bot receipts qualify only with authenticated provenance from the dedicated successful default-branch reviewer workflow: matching path, ref, event, run lifetime, start receipt and reviewed head. General bot approvals, free-form comments and manually written approval markers cannot qualify.

For Codex, the validator is the connector's **thumbs-up (`+1`) reaction on the PR
itself**, not a completion comment or a reaction on a review comment. A completed
summary or submitted code/security review supplies the reviewed revision and its
completion time; it does not approve anything without the PR reaction. The reaction
must be at or after that current review's completion. A missing/removed reaction,
a stale reaction after a push, running review, or incomplete review metadata keeps
the gate closed.

Codex normally writes seven-character summary IDs and ten-character footer IDs.
The controller resolves authenticated 7–40-character identifiers through GitHub
and compares the result with the full current head. It rejects failed or ambiguous
resolution, responses with a different prefix, and hex-named branches/tags that
could shadow SHA lookup. A submitted review's full API `commit_id` must agree with
any written marker. Human-authored comments, lookalike accounts and empty bot
review replies cannot qualify. GitHub's reactions endpoint can label the connector
as `User` while its comments identify it as `Bot`; reaction authentication uses
its reserved `chatgpt-codex-connector[bot]` login, never the generic user-type field.
The Codex connector, reserved Claude bot and Actions bot cannot use the qualified-human-review fallback. The trusted controller,
preflight and final reporter receive `issues: read` to read PR-body reactions
through GitHub’s issues reactions endpoint; PR build jobs receive no added
write permission.

An approving/comment-only review from another repository owner, member or
collaborator remains a separate qualification path. Author self-reviews and stale
or dismissed reviews do not qualify. Full 40-character head/base/test-merge IDs
remain mandatory in validation dispatch, preflight and final status reporting.
Inspect current eligibility without writing statuses or dispatching jobs:

```sh
python3 .github/scripts/review_gate.py inspect --repo johnneerdael/ProjectM-TV --pr NUMBER
```


All review threads, including outdated threads, must be resolved. Outstanding GitHub review requests, any pending review exposed by the API, active Claude `RUNNING` markers, outstanding changes-requested decisions and unfulfilled authorized manual requests block builds.

The latest authorized **code-review** request or authenticated manual Claude dispatch selects the provider: `@claude review` supersedes earlier `@codex review` requests, and vice versa. This selection replaces only earlier manual code-provider obligations; it never clears findings, GitHub reviewer requests or changes-requested decisions. `@codex security review` is a separate scope and must receive its own current-head Codex security completion. An explicit request requires a completion for the current head from the selected provider, even when a human has reviewed it. After a push, the retained selected request and any separate security request require new current-head completions.

Commands use the comment's latest update time (creation time only if no update time is available), so editing an old comment into a review command requires a new completion after that edit. Codex summary rows must provide their own completion datetime; edits to the enclosing comment never supply a review completion time. Completion must be strictly later at whole-second precision; equal-second timestamps remain pending because GitHub request timestamps do not prove their order. A comment-only follow-up does not clear a changes-requested decision: the reviewer must approve or the decision must be explicitly dismissed. Express blocking findings as review threads or a changes-requested review; free-form issue comments do not have a GitHub resolution state.

GitHub hides another reviewer's private draft review and its unpublished comments from the controller. The gate cannot detect arbitrary unrequested private drafts. Request the reviewer on the PR to keep the gate closed until submission; published unresolved threads and changes-requested decisions remain blocking signals.

The **PR review gate** workflow reads trusted `main` code and dispatches **Reviewed PR validation** on `main`. An unprivileged **PR review signal** relays review events through `workflow_run`; PR/comment/main-push events prompt trusted-main rechecks; a five-minute schedule also checks thread resolution and provider comment updates because thread resolution has no native Actions trigger. Scheduled runs can be delayed by GitHub. The gate records a `Reviewed PR builds` status on the PR head, remaining pending until eligibility and the full suite pass. Configure the `main` ruleset to require this status from GitHub Actions, retain resolved-thread enforcement, and require the branch to be up to date. The completed-review minimum is enforced by the gate; the separate GitHub approving-review count remains zero so a qualifying provider completion can satisfy this policy.

Validation builds an immutable test merge of the reviewed head and current `main`. The controller reads the live main ref and verifies both merge parents rather than trusting a cached PR base SHA. It rechecks review eligibility and both revisions before starting and after all jobs finish. Android/native tests, Preset Lab and the documentation build must actually succeed; skipped jobs cannot produce a passing status. A new main revision requires a new test merge and validation. PR code receives no signing/publishing secrets or write-capable repository token, and cannot access build caches (`cache-mode: none`, enforced by GitHub's scoped cache token). APK/AAR publishing runs only in the main pipeline after all builds pass. Pages publication runs after the main suite, or after a successful manually dispatched User guide build on `main`.

When all builds succeed but the final review check becomes ineligible, the status stays pending. Once review eligibility recovers for the same revision, the controller automatically starts fresh validation; scheduled rechecks do not mark those successful builds as failed. A preflight error that starts no build jobs also keeps the gate pending and retryable; the next eligible controller check dispatches fresh validation. Skipped jobs following a successful preflight remain a failure, and this retry path cannot report success without actual builds. Preflight changes a prior passing gate status to pending before any new build starts. A final reporter API error after successful builds also leaves the gate pending and the run retryable; it cannot report a passing status without a verified snapshot and successful status write. Actual failed validation is not automatically retried every five minutes. Fix the PR and obtain a new review, rerun its failed validation workflow, or run **PR review gate** manually with `pr_number` and `retry_build=true`. A manual validation dispatch still has to pass preflight; selecting a feature branch in the manual build workflows skips the builds.

The lightweight **PR release notes** validator continues to check PR text before review. It does not compile or publish artifacts.

## User guide publishing

The main Android pipeline and manually dispatched **User guide** workflow both call `pages-deploy.yml`. Their deployment jobs share the `projectm-tv-pages` concurrency queue with cancellation disabled; this does not serialize or cancel documentation builds. Once a deployment holds the queue, it checks that its immutable workflow SHA still equals the current `main` SHA. An older queued/manual run skips publication rather than replacing a newer site, and an API lookup failure stops publication.

The read-only `docs-build.yml` reusable workflow supplies the Pages artifact for main, manual and reviewed-PR builds. PR validation never calls the deployer or receives Pages/ID-token write permissions. Run **User guide** manually on `main` to build and publish the guide without publishing another APK/AAR. A manual run on another branch skips the build and deployment.

The release-tooling job installs `tools/fdroid/requirements.txt` (the
fdroidserver commit and ruamel.yaml version used by fdroiddata's merge request
CI) in a temporary Python virtual environment before running its tests.
Reviewed PR validation uses trusted workflow definitions from `main`, even
when its source checkout is a PR merge commit. Land prerequisite test-tooling
setup before a follow-up PR depends on it; changing a workflow in that follow-up
cannot change the trusted workflow used to validate itself.

## Writing PR release notes

Use `.github/pull_request_template.md` and `AGENTS.md`. Include a substantive `## Release notes` section describing concrete changes, their effects and material limits for app users. Keep it aligned with the final diff. Put tests and implementation process in `## Validation`, outside public notes.

For changes with no user-visible effect, use an `Internal` subsection and explain the change. A bare “No user-visible changes”, `N/A`, empty bullets or `TODO` placeholders fail validation. The **PR release notes** check runs again when the PR body is edited. CI checks structure; reviewers check factual accuracy and writing quality.

The workflow collects merged PR sections since the previous reachable version tag. Historical PRs before this automation use their existing change descriptions without validation/checklist/badge sections. Direct commits use their actual descriptions. The generator does not invent claims or use an external AI service.

CI appends install/download information. The canonical TV and Android Downloader codes come from their separate install blockquotes in `README.md`; update the matching blockquote when a code changes. For versions before 2.3.38, a historical README may omit the Android block. From 2.3.38 onward, generation requires that block and fails if it is missing or malformed. Notes include stable/latest and versioned APK/core URLs, checksums, the user guide and the comparison link. `RELEASE_NOTES.md` remains a human-readable archive rather than being copied into unrelated releases.

## Versions and tagged builds

`app/build.gradle` holds literal `baseVersionName`, `baseVersionCode` and `baseVersionCommit` values. Keep them unchanged for routine PRs. For a planned major/minor line change, update all three together: the desired first version, a code above the latest released code, and the current `main` commit before that change. Tests verify the sequence.

CI passes `PROJECTM_RELEASE_VERSION` and `PROJECTM_RELEASE_VERSION_CODE` to Gradle. Local builds default to the baseline.

Release tags do not point at the `main` commit itself. After allocating the version, the build job creates a release commit on top of it whose only change appends `projectmReleaseVersion` and `projectmReleaseVersionCode` to the root `gradle.properties`, checks it out and builds every artifact from it (`.github/scripts/release_commit.py`). The commit is deterministic: fixed identity, the source commit's timestamp, a `Release v<version>` message with `Version-Code` and `Source-Commit` trailers. The release job rebuilds it from `main`, requires the same SHA as the build, and pushes it only as the `v<version>` tag, never to a branch, so `main`'s first-parent numbering is unchanged. An existing tag is reused only when it already points at that commit. Version allocation and release notes map such tags back to their source commit; older tags pointing directly at `main` commits still work. `release-version.json` and the GitHub Release record the tagged commit. GitHub shows that commit as not belonging to a branch; never delete release tags, because F-Droid builds from them.

A tag created this way builds with its own version after checkout: `./gradlew assembleRelease`. To reproduce an older tag's version metadata after checking it out and fetching tags:

```bash
python3 .github/scripts/release_version.py --repo . --sha HEAD \
  --event workflow_dispatch --ref refs/heads/main --run-number 1 \
  --output /tmp/projectmtv-version-output --env /tmp/projectmtv-version-env
set -a
. /tmp/projectmtv-version-env
set +a
./gradlew assembleRelease
```

Signing still requires the configured release key; locally debug-signed builds cannot update an installed stable release.

## Downloads and core library

The platform-specific Downloader codes and fixed APK URLs serve the newest stable build:

- TV: Downloader **4821216**, [latest TV APK](https://github.com/johnneerdael/ProjectM-Android/releases/latest/download/projectM-TV.apk)
- Phone/tablet: Downloader **6565691**, [latest Android APK](https://github.com/johnneerdael/ProjectM-Android/releases/latest/download/projectM-Android.apk). Install [Downloader from Google Play](https://play.google.com/store/apps/details?id=com.esaba.downloader&hl=en).
- [Latest Native core AAR](https://github.com/johnneerdael/ProjectM-Android/releases/latest/download/projectM-TV-core.aar) (canonical integration download)

New releases attach `projectM-TV-<version>.apk`, `projectM-Android-<version>.apk`, `projectM-Android-<version>-mapping.txt`, `projectM-TV-core-<version>.aar`, `projectM-TV-<version>-mapping.txt` and `checksums.txt`, plus the fixed APK/core names above and `projectM-Android.apk`. The touchscreen APK uses app ID `nl.neerdael.projectm` and the same signing key/version as the TV APK; each updater downloads its own platform asset. The reusable build workflow stages TV before building with `-PandroidTouchscreen=true`, because APK/mapping output paths are shared. Release publication uses `--with-touchscreen` to require both APKs, both mappings and matching stable aliases before publishing. Historical release retries without that flag retain the old artifact schema. The canonical versioned and fixed-name core files contain the same Native-capable AAR built with the APK. It contains the public Java/JNI API, native ARMv7/ARM64 libraries and presets, and shares the app version. There is one `:core` module and one published core artifact; separate capped and `core-native` artifacts are retired for new releases.

New publication also requires both F-Droid editions: `projectM-TV-FDroid-<version>.apk` and `projectM-Android-FDroid-<version>.apk`, their stable aliases and separate R8 mappings, the deterministic `cream-of-the-crop-<version>.zip`, and `release-version.json`. Use `--with-touchscreen --with-fdroid`; earlier release retries retain their historical schema. APK descriptors must match the published archive's hash, size and collection identity, and the starter selection must carry completed runtime qualification. All four APKs share the source/version/code/signing key. The canonical full core AAR is staged before F-Droid builds overwrite local core output; CI checks its 9,606 presets and 74 textures.

`release-version.json` records the stable version, Android code, the tagged release commit, tag and collection identity. F-Droid uses `UpdateCheckMode: Tags` with `AutoUpdateMode: Version` and reads the version/code from each tag's `gradle.properties`, so new release lines need no recipe change. The recipe builds the tagged source unchanged and selects the matching slim flavor. Store metadata is separated under `src/fdroidTv/fastlane/` and `src/fdroidAndroid/fastlane/`.

After successful publication, the independent F-Droid synchronization job updates the pending TV submission and one separate phone submission; a failure does not block Milkbeat dispatch. Trusted-main scheduled/manual recovery revalidates the latest complete stable release. Configure `FDROID_GITLAB_TOKEN` with API and repository push access to the fdroiddata fork. The workflow's `validate_only` input checks the token with a temporary branch probe. See [F-Droid tooling](../tools/fdroid/README.md) for ownership, conflict and credential rules. Accepted listings retain F-Droid-managed build history. Local/mock checks are separate from live GitLab pipeline results and maintainer acceptance.

The app uses Standard Native trails and Auto resolution by default up to the detected panel size. Advanced › Resolution additionally offers supported fixed sizes and Native. Explicit modes bypass FPS adaptation and slow-preset skipping but retain live memory protection; the manual RAM limiter remains removed. The additive `QualityController.setResolutionMode` API enables opt-in selection without changing the deprecated Auto-normalizing APIs used by existing hosts. GPU, memory and picture limits still apply; publication does not establish universal device performance or fidelity acceptance.

Build with `./gradlew :core:assembleRelease`; the optional legacy spelling `-PprojectmCoreRenderingPolicy=native` remains accepted. `-PprojectmCoreRenderingPolicy=capped` now fails with a migration message, as does `-DPROJECTMTV_RENDERING_POLICY=capped` for direct CMake configuration. `RenderingPolicy.NAME` remains `native` and `RenderingPolicy.NATIVE_ENABLED` remains `true` for consumers. The release workflow stages `core/build/outputs/aar/core-release.aar` once under the canonical filename and records a checksum for every published APK, AAR and mapping filename.

Historical published releases and tags remain immutable, including releases with a capped canonical core and separate Native aliases. A retry verifies completeness, tag ownership and versioned/alias digest agreement where GitHub provides digests, then returns without replacing assets or checksums. Retired local Native aliases are not required for that retry. A pre-existing draft containing retired `core-native` assets is rejected for maintainer reconciliation rather than published with a mixed schema.

Release APKs are shrunk, optimized and obfuscated by R8, so Java stack traces show short names. Each edition has its own mapping: `projectM-TV-<version>-mapping.txt`, `projectM-Android-<version>-mapping.txt` and the corresponding `projectM-TV-FDroid-<version>-mapping.txt` / `projectM-Android-FDroid-<version>-mapping.txt`. Use the matching edition's mapping for an F-Droid rebuild. CI retains them in the `mapping` artifact. Restore names with the SDK's `retrace` tool:

```sh
retrace projectM-TV-<version>-mapping.txt crash.txt
```

`retrace` is in the Android SDK command-line tools (`cmdline-tools/latest/bin`). Native crashes (`Fatal signal`) are not affected.

Publication pushes the release tag, creates or resumes a draft, uploads every artifact, then publishes it. A retry verifies the tag points to the expected release commit and leaves a complete published release unchanged.

## Milkbeat follows each core release

[Milkbeat](https://github.com/johnneerdael/Milkbeat) follows the latest stable Native-capable core through the unchanged canonical artifact name `projectM-TV-core-<version>.aar`. Its workflow pins the resolved version and names it in Milkbeat's release notes. ProjectM-TV sends a `projectm-core-release` dispatch after publication. A core already named by Milkbeat's latest release does not trigger a duplicate rebuild.

`MILKBEAT_TOKEN` must be a fine-grained token with Contents read/write on `johnneerdael/Milkbeat`, stored as a ProjectM-TV Actions secret. It was configured on 2026-10-02. A missing token fails the update job visibly; rerun a failed update job after fixing its configuration.

For an unreleased Milkbeat-compatible core, build `./gradlew :core:assembleRelease`, copy the AAR to `<dir>/download/v<version>/projectM-TV-core-<version>.aar`, and build Milkbeat with `-PprojectmCoreRepo=<dir> -PprojectmCoreVersion=<version>`.
