# F-Droid TV and Android distribution

Date: 2026-10-11. Status: user-approved architecture spec; implementation planning follows. Product implementation has not started.

## Purpose and approved direction

Provide useful, substantially smaller F-Droid APKs for Android TV and touchscreen Android without maintaining divergent application code. Keep the full Cream of the Crop collection and a default-enabled updater in the GitHub editions. Offer the full collection as an explicit optional download in F-Droid editions. Generate and synchronize both F-Droid recipes from every successfully published upstream release.

The user approved this direction with “lets do it.” This document specifies the implementation boundaries that the previous outline did not resolve.

## Release baseline and constraints

The inspected baseline is main `8238b86b9dfdc2f2f80bc494671798e2ac1a8ad0`, published as `v2.3.38`. Preserve the current application IDs: TV `nl.neerdael.projectmtv`; touchscreen Android `nl.neerdael.projectm`. Do not add distribution-specific ID suffixes. There are two F-Droid listings and recipes, one for each application ID.

Keep the default TV Gradle tasks and paths. Continue selecting touchscreen builds with `-PandroidTouchscreen=true`. Add one distribution selector, `-PprojectmDistribution=github|fdroid`, defaulting to `github`; reject other values. Keep framework Views, Java, GLES 3 and existing dependencies. Add no AndroidX dependency, renderer repair, corpus rescoring or routine version-floor bump.

| Artifact | Presets | App update mechanism |
|---|---|---|
| GitHub TV | Full collection | Built-in updater, On when no preference is stored |
| GitHub Android | Full collection | Built-in updater, On when no preference is stored |
| F-Droid TV | 20 starters; full collection optional | F-Droid client |
| F-Droid Android | 20 starters; full collection optional | F-Droid client |

TV audio capture, remote controls and device requirements stay supported. Both phone editions retain microphone input, playback capture, touch gestures, system consent and lifecycle cleanup. The application remains a visualizer, not a music player.

## Packaging and core integration

Presets, textures and collection indexes currently belong to `:core`, which is also published for Milkbeat. Generate a separate asset directory for F-Droid builds containing exactly the selected starter presets, their required textures, the subset preset index and subset mood metadata. Select this directory in `core/build.gradle` for F-Droid builds without deleting or editing the full source corpus. Preserve native preset weights and the existing beta mood classifications; do not rerank the subset.

The default `:core:assembleRelease` and canonical published AAR must still contain all 9,606 presets and 74 textures. Stage that full AAR before building F-Droid variants, and verify its contents before publication. A starter-only internal core build must never become `projectM-TV-core.aar` or the Milkbeat dispatch payload. New official-library support is additive; existing `ProjectMCore.init` and custom-pack APIs retain their behavior for existing consumers.

Generate the starter assets deterministically from a checked-in selection manifest. Validate names, source hashes, index membership and texture dependencies. Include every required image; a random-texture preset would require its eligible random-image pool. Do not retain all 74 images merely to simplify the small build. The build must perform no online preset lookup.

## Starter selection

The companion [candidate manifest](2026-10-11-fdroid-starter-candidates.json) records 20 existing corpus files, SHA-256 hashes, byte sizes, mood memberships and immutable curation-source links. Sixteen occur in Butterchurn's `minimal.js`; four additions occur in `nonMinimal.js`. The curation snapshot is `c10e2616762f262de898e5d4c1f162a3e01340c1`. These are researched candidates, not a measured worldwide popularity ranking.

The candidates total 221,494 uncompressed preset bytes. They have seven Chill, ten Normal and two Intense memberships, with overlaps; two are All-only under the existing beta classifications. The existing static audio/texture checker passes with an empty external-image set, and no `randNN` sampler was found. Runtime qualification must confirm this analysis and usable visual variety before the selection becomes a shipping manifest. Replace a failing candidate with another source-backed, compatible corpus preset and record the reason.

The current third-party document distinguishes the project's CC0 curation rights from rights held by individual authors and notes missing upstream texture licenses. Preserve that distinction. Record provenance for the chosen files; selection by another project is not a new license grant. Optional distribution of the full collection does not resolve an underlying licensing gap or guarantee F-Droid inclusion. Retain and verify all existing notices rather than broadening the CC0 claim.

## Built-in updater separation

Move the existing updater implementation and install provider into the GitHub source selection. Supply an F-Droid implementation with the small interface needed by the shared activity, reporting updates through F-Droid and performing no APK checks, downloads or installer calls. The F-Droid APK must contain no GitHub APK updater implementation, update FileProvider registration or `REQUEST_INSTALL_PACKAGES` permission. Keep `INTERNET` for the explicitly requested collection download and custom-pack LAN upload.

The update setting in F-Droid displays “Updates via F-Droid”; it cannot enable the GitHub updater even when sideloaded or when an old `auto_update=true` preference exists. In GitHub builds, default the preference to On but honor an explicitly stored Off value. Preserve existing signed-package validation and Android's install confirmation; default-enabled updates do not mean unattended installation.

## Official collection download

Only the F-Droid edition presents a one-time startup offer while still making the starter library available. Use “Download Cream of the Crop — recommended” and “Continue with starter presets”, with both actions visible and equally easy to activate by touch or D-pad. Show actual download and installed sizes, and explain that the collection is hosted on GitHub and distributed outside F-Droid's build checks. Declining makes no request and does not prompt again on each launch. Provide download, progress, cancel, retry and remove actions later in Settings.

Publish a deterministic ZIP of this repository's complete shipping collection, textures, preset weights, mood indexes and notices. Do not download a changing third-party pack or add unrelated presets. Include a file manifest and collection identity. Bundle a descriptor containing the exact HTTPS release-asset URL, ZIP SHA-256, compressed size, expanded size, format version and expected counts in the matching F-Droid APK. Compare downloaded bytes against that trusted descriptor before extraction. Permit only HTTPS redirects, including GitHub's asset hosting; bound timeouts, bytes, expanded data and entries.

Reuse the platform `HttpURLConnection`, `ZipFile`, bounded extraction and generation-storage patterns already present in `Updater` and `CustomPresetPack`; do not introduce a new ZIP parser or copy the updater into the F-Droid edition. Factor reusable archive handling only where needed. Official metadata needs stricter validation than the existing user ZIP format.

Use a dedicated official-collection store in no-backup app storage, separate from custom packs. Download and stage on one background worker, publish progress on the UI thread, and commit the pointer only after digest, extraction, metadata and native indexing succeed. A failed or canceled operation retains the previously usable library. Partial files are cleaned up. On pause, cancel unfinished work; retain completed installation state and allow an explicit retry on return. No foreground service or new permission is required for downloading presets.

Retain verified installed content across launches and compatible app updates. A collection identity is content-based, independent of an app release containing only documentation or code changes; do not force another download for every new APK. Offer a newer collection explicitly when its identity changes. Missing or invalid installation metadata falls back to the starter library without a startup crash. Removal restores starters and defers directory deletion until all native readers release their leases.

## Native library integration

Add an official-base-library input beside the existing custom-pack input in `PresetLibrary` and JNI. Do not load the official collection as a user custom pack. An installed official collection replaces the bundled starter base; it supplies the full All, Chill, Normal and Intense catalogs and original memory weights. Keep canonical preset names and skip-list identities. The full All catalog contains 9,606 official presets without duplicating the 20 starters, plus any custom presets under the existing custom-pack rules.

Resolve each official preset's data and texture paths from one immutable generation. Preserve starter fallback, custom search-path isolation, GL-thread ownership, background indexing, prepared publication and active/outgoing/loading/prewarm reader leases. Independent official and custom requests cannot overwrite each other's prepared state or expose mixed metadata. Retired metadata and files are reclaimed off the GL thread after all readers retire. No changes to authored shader semantics, visual quality policy or engine patch files are intended.

## Release artifacts and version discovery

Keep `projectM-TV-<version>.apk`, `projectM-Android-<version>.apk` and their stable aliases unchanged. Add `projectM-TV-FDroid-<version>.apk` and `projectM-Android-FDroid-<version>.apk`, separate R8 mappings and stable F-Droid aliases. Add the versioned collection ZIP and a release-version JSON asset. Include every artifact in checksums and the complete-release publication validation. Historical releases retain their existing schemas and immutability.

Build all four APKs from one source SHA with the same calculated version name/code. Normal CI must test both device targets in both distributions and verify packaged contents and manifests. The complete release cannot publish when a required edition or asset fails its build or checks.

The Gradle file holds the `2.3.0`/49 release-line floors, while `.github/scripts/release_version.py` derives the actual version from first-parent history. Publish those calculated values, tag and source SHA in the release JSON. Use F-Droid's HTTP `UpdateCheckData` against the latest release JSON and `AutoUpdateMode: Version v%v`, with recipes that pass the discovered version/code to Gradle through explicit supported properties. The new Gradle property overrides must coexist with the existing CI environment overrides and reject invalid values. Do not calculate versions from F-Droid's possibly shallow checkout.

Configure each recipe's `Binaries` verification URL to its matching F-Droid APK, not the larger GitHub edition. Retain the upstream signing-key/reproducible-build approach and pinned JDK/NDK/CMake toolchain. Verify both recipes with fdroidserver, including update detection beyond 2.2 and matching package/version identity.

Provide separate upstream store titles, descriptions and screenshots for TV and phones. The phone listing describes touch, microphone and playback capture; both F-Droid listings describe the starter bundle and optional collection rather than claiming the full collection is bundled. Preserve the existing upstream Fastlane listing until the two-listing importer is verified. F-Droid documents limitations for multiple apps in one source repository, so successful local import of the correct metadata for each application ID is an acceptance check, not an assumption based on APK build success.

## GitHub Actions synchronization

After successful release publication, generate, lint and synchronize two canonical recipes: `metadata/nl.neerdael.projectmtv.yml` and `metadata/nl.neerdael.projectm.yml`. Use the release JSON and immutable tag/source identity as inputs. Keep only the latest build in each unmerged new-app submission, matching the maintainer checklist. Once a listing is accepted, allow F-Droid's automatic update process to generate routine builds; our action continues checking discovery and recipe compatibility rather than overwriting F-Droid-maintained history.

The initial TV submission uses the existing fork branch `nl.neerdael.projectmtv` and MR !50236. Maintain that branch for TV. Prepare a separate phone branch and new-app MR, with one app per MR. Update from current fdroiddata master so stale upstream history does not accumulate. Restrict each branch change to its app's metadata, preserve intentional maintainer edits, and fail for conflicting unmanaged changes. Avoid duplicate MRs and newer-to-older rollbacks. A successful repeat run is a no-op. Do not post discussion comments automatically.

Run authenticated synchronization only from trusted main-release or scheduled recovery workflows, never PR code. Use a dedicated GitLab credential stored as the GitHub Actions secret `FDROID_GITLAB_TOKEN`, scoped to the user's fork/API operations. The inspected GitHub secret inventory has no GitLab sync credential, so external synchronization cannot be activated until that credential is configured. Provide a token-free generation/check mode for PRs and local validation; do not print credentials or embed them in remote URLs. Scheduled recovery retries failed synchronization against the latest successfully published release, with serialization to prevent competing branch updates.

Missing credentials or a GitLab error must produce a visible failed synchronization result, rather than a successful “in sync” claim. They do not roll back an already published GitHub release or suppress the existing Milkbeat update. F-Droid review, build and publication queues remain external; automation keeps release metadata current but cannot guarantee simultaneous store availability.

## Verification and acceptance

- Four release APKs build and report the expected IDs and identical release versions/codes. GitHub APKs and the published AAR contain the full collection; F-Droid APKs contain exactly 20 starters and no unused full-corpus indexes/textures.
- Inspect F-Droid DEX/manifest for absence of the real APK updater, its provider and install permission. Confirm the stub cannot enable network update checks when sideloaded or when old preferences enable updates. Check GitHub default-On and explicit-Off behavior.
- Run all 20 starters with audio on task-owned phone and TV emulators, retain captures and preset identities, and qualify actual texture behavior. Do not infer whole-corpus or physical-TV certification from these focused checks.
- Exercise download/decline/retry/cancel, offline startup, corrupt digest/archive/metadata, insufficient storage, cold restart, collection removal and app upgrade. Preserve usable starter/previous content for each failure.
- Test All/mood counts, weights, duplicate elimination, custom-pack coexistence, replacement races and active/outgoing/prewarm leases. Build the canonical full AAR and verify consumer compatibility for additive core API changes.
- Run release-tooling unit tests, required app/core JVM and native checks, `actionlint`, strict MkDocs and `git diff --check`. Measure actual APK/download/installed sizes before publishing figures.
- Validate both F-Droid recipes, reproduced APK identity, update discovery for successive releases, idempotent synchronization, conflicts, missing credentials, out-of-order jobs and recovery after a failed GitLab update.

## Work status

- [x] Inspect current packaging, updater, custom-pack/native boundaries and release/version workflow.
- [x] Research starter-selection sources and identify 20 corpus candidates with static checks.
- [x] Write and self-review the architecture spec in an isolated feature worktree.
- [x] User reviews the written spec (approved 2026-10-11).
- [x] Write and self-review the [implementation plan](../plans/2026-10-11-fdroid-distribution.md).
- [ ] User reviews the implementation plan and selects execution method.
- [ ] Implement and run the acceptance checks.
- [ ] Prepare the implementation PR with factual release notes and current-head review.
- [ ] Configure GitLab synchronization credentials and verify the external submission path.

## Source references

- [F-Droid discussion !50236](https://gitlab.com/fdroid/fdroiddata/-/merge_requests/50236): reviewed from the user's pasted discussion; live page/API access failed. Maintainers requested minification/resource shrinking and questioned update discovery restricted to 2.2. They did not promise inclusion after an asset-size change.
- [F-Droid build metadata reference](https://f-droid.org/en/docs/Build_Metadata_Reference/): `gradleprops`, version substitution in build commands, HTTP update discovery, automatic build generation and binary verification.
- [F-Droid store metadata](https://f-droid.org/en/docs/All_About_Descriptions_Graphics_and_Screenshots/): supported upstream metadata locations and limitations for multiple apps/flavors in one repository.
- [F-Droid inclusion policy](https://f-droid.org/docs/Inclusion_Policy/): asset rights, build transparency and explicit consent for downloads of executable binaries. MilkDrop presets contain interpreted expressions/shaders; present the external download clearly rather than claiming its classification is settled.
- [Butterchurn preset repository](https://github.com/jberg/butterchurn-presets/tree/c10e2616762f262de898e5d4c1f162a3e01340c1): selection-source snapshot; existing local preset files, not converted JSON, supply shipping candidates.
- [Ryan Geiss's favorites](https://www.geisswerks.com/about_milkdrop.html): primary evidence for personal curation, not worldwide popularity. The ZIP could not be retrieved in this environment and supplies no candidate-file evidence here.
- [GitHub Actions secrets](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets): credential configuration for authenticated external synchronization.
- Local inspected sources: `app/build.gradle`, `core/build.gradle`, `CustomPresetPack.java`, `Updater.java`, `MainActivity.java`, `ProjectMCore.java`, `ProjectMJNI.java`, `native-lib.cpp`, `.github/workflows/android*.yml`, `.github/scripts/{release_version,publish_release}.py` and `docs/THIRD_PARTY.md`.
