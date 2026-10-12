# Task 5 report
Implemented: source_files includes preset-attributes; starter_files filters attributes.tsv to the 20 starters, copies facets.json, recomputes manifest (preset_count, measured_count via luminance column, option_counts, attributes_sha256, presets_idx_sha256).
TDD: new test test_starter_filters_preset_attributes_to_selected_presets in tools/test_preset_distribution.py; RED (AssertionError, attributes.tsv missing from source_files), GREEN after implementation (10/10).
Lock: `lock-archive --root . --output tools/preset-distribution/official-archive.json`; one-line file, only archive_sha256, collection_id, compressed_bytes, expanded_bytes changed (preset_count 9606, texture_count 74 unchanged).
Starter generation: `./gradlew -PprojectmDistribution=fdroid :core:generateStarterPresets` succeeded; core/build/generated/preset-distribution/starter-assets/preset-attributes has 20 data rows, manifest preset_count 20, measured_count 20, attributes_sha256 matches shasum of the file.
CI: test_preset_distribution was not in CI; added to the "Test mood facets" step (run: | block); actionlint clean.
Release tooling tests: 232 run, 20 errors, all ModuleNotFoundError fdroidserver (environment), no other failures.
Concern: running gradle modified tracked build/reports/problems/problems-report.html; reverted, not committed.

## Fix round 1
- OfficialPresetPack.java: allowlist now includes exactly preset-attributes/{facets.json,attributes.tsv,manifest.json}.
- OfficialPresetPackTest: new presetAttributesAreAcceptedOnlyUnderExactNames (accepts the three, rejects other.bin). RED: `./gradlew -PprojectmDistribution=fdroid :app:testFdroidTvDebugUnitTest --tests '*OfficialPresetPackTest'` -> 8 tests, 1 failed (IOException Unexpected collection metadata). GREEN: same command, BUILD SUCCESSFUL.
- tools/test_preset_distribution.py: one unmeasured row (empty options, `-` x8); asserts preset_count 20, measured_count 19, option_counts no_strobe 19, header lines identical. 10/10 pass.
- Reverted build/reports changes.
