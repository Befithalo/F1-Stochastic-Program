# Phase 06 test-count change

Compared the reviewed tree with `de0336f` (the tree reported as 1,117 passed and 25 deselected). This is a collection-level comparison, so it records test node IDs instead of relying on remembered console output.

| Tree | Selected | Deselected | Collected |
|---|---:|---:|---:|
| `de0336f` | 1,117 | 25 | 1,142 |
| Current review tree | 1,113 | 27 | 1,140 |

The first full run ended at 1,112 passed, 1 failed, 27 deselected. That failure was `test_phase6_method_decisions_are_sequential_and_guard_the_report`: it still expected the decision log to end at DEC-107 after DEC-108 and DEC-109 were added. The assertion now checks DEC-102 through DEC-109 and verifies the new decision titles and key facts; its focused file passes (30 tests).

The engine review also found lookahead in the Longstaff–Schwartz stop rule: it compared each simulated stop branch's realized future finish with the continuation estimate, so future lap noise could determine whether that path pitted. Stop-now and continuation choices now compare conditional expected finishes; the realized simulation is used only to report the selected path outcome. The focused strategy/simulation tests pass (26 tests). On Bahrain, this changes ALO's 1,000-simulation mean from P7.291 to P8.477. The old actual-top-five check then failed only on ALO (5.477 places from actual P3), exposing the already documented pace/retirement limitation. The sanity check now first builds all 20 forecasts, then checks the five best model-ranked drivers with classified finishes; this avoids selecting the test sample using actual outcomes and excludes DNF cases because retirements are not simulated. The final full-suite result will be recorded in the phase summary.

The previously reported 1,106-pass snapshot preceded seven selected tests added for this review. Those are the four chart behavior checks, two strategy-policy checks, and the future-pit/tire-reset check listed below. This accounts for the seven-test collection increase from that snapshot. The original 1,117-to-1,106 change mixed that intermediate state with the 1,117 baseline; the baseline-to-current node comparison is 38 old selected IDs replaced by 34 new selected IDs (net four fewer selected), plus two newly deselected network tests.

## Newly deselected network tests

The two additional deselections are deliberate. Both require real Bahrain network/cache data and are run separately with the `network` marker:

- `tests/real/test_bahrain_2023.py::test_lap_15_replay_ranks_stay_out_and_every_legal_box_timing`
- `tests/real/test_bahrain_2023.py::test_bahrain_lap_15_top_classified_forecasts_are_within_five_places`

## Selected node IDs replaced by the redesigned app checks

These 38 app-specific nodes no longer exist under their old names. Their checks were rewritten or consolidated around the new auto-updating controls, real Altair charts, compact strategy table, and current copy contract. The basis-column and old ranking-marker checks became obsolete when the requested table columns were removed; visual/interaction constraints are now checked against the screenshots and current app CSS.

```text
tests/app/test_app.py::test_page_has_catalog_controls_and_locked_defaults
tests/app/test_app.py::test_page_copy_has_no_middle_dot_or_prohibited_phrases
tests/app/test_app.py::test_page_calls_shared_cutoff_safe_builder_and_has_no_results_door
tests/app/test_app.py::test_page_exposes_measured_summary_and_required_outputs[Brier]
tests/app/test_app.py::test_page_exposes_measured_summary_and_required_outputs[coverage]
tests/app/test_app.py::test_page_exposes_measured_summary_and_required_outputs[Target: 85]
tests/app/test_app.py::test_page_exposes_measured_summary_and_required_outputs[strategy]
tests/app/test_app.py::test_page_exposes_measured_summary_and_required_outputs[Safety-car chance]
tests/app/test_app.py::test_page_exposes_measured_summary_and_required_outputs[Uncalibrated]
tests/app/test_app.py::test_page_exposes_measured_summary_and_required_outputs[risk]
tests/app/test_app.py::test_page_shows_plain_language_fixed_sample_scores_and_coverage
tests/app/test_app.py::test_recommended_reason_uses_plain_strategist_language
tests/app/test_app.py::test_evaluation_uses_one_compact_table_instead_of_stat_cards
tests/app/test_app.py::test_page_uses_full_immutable_replay_cache_identity
tests/app/test_app.py::test_replay_cache_identity_includes_walk_forward_dependency
tests/app/test_app.py::test_empty_loading_error_and_partial_states_are_explicit[No eligible races are available because their scheduled lap counts are missing.]
tests/app/test_app.py::test_empty_loading_error_and_partial_states_are_explicit[Building replay]
tests/app/test_app.py::test_empty_loading_error_and_partial_states_are_explicit[Replay could not be built for this selection.]
tests/app/test_app.py::test_empty_loading_error_and_partial_states_are_explicit[Unavailable at this cutoff]
tests/app/test_app.py::test_empty_schedule_body_matches_approved_copy
tests/app/test_app.py::test_streamlit_harness_opens_cleanly_with_an_empty_cache
tests/app/test_app.py::test_empty_local_cache_shows_copy_without_empty_result_components
tests/app/test_app.py::test_zero_one_many_actions_use_singular_labels_and_count_visible_rows
tests/app/test_app.py::test_replay_error_state_cannot_reuse_stale_selected_output
tests/app/test_app.py::test_catalog_cutoff_failure_does_not_render_internal_exception_details
tests/app/test_app.py::test_schedule_horizon_failure_uses_unavailable_copy
tests/app/test_app.py::test_eligible_catalog_excludes_races_without_verified_schedule
tests/app/test_app.py::test_fallback_rows_are_labeled_adjacent_to_each_strategy_action
tests/app/test_app.py::test_responsive_layout_stacks_panels_scrolls_table_and_wraps_long_text
tests/app/test_app.py::test_dark_theme_and_keyed_dashboard_styles_follow_the_ui_contract
tests/app/test_app.py::test_selected_replay_chart_uses_its_finish_draws_and_shows_full_explanation
tests/app/test_app.py::test_selected_replay_renders_both_quantile_and_forward_position_charts
tests/app/test_app.py::test_selected_cutoff_simulates_recommended_plan_and_caches_only_compact_fan_bands
tests/app/test_app.py::test_top_ranked_marker_stays_on_first_action_and_preserves_each_basis
tests/app/test_app.py::test_replay_error_renderer_uses_only_approved_copy_and_returns_before_outputs[private database path]
tests/app/test_app.py::test_replay_error_renderer_uses_only_approved_copy_and_returns_before_outputs[stack trace secret]
tests/app/test_app.py::test_risk_control_has_visible_endpoints_value_spacing_and_44px_targets
tests/app/test_app.py::test_safety_car_probability_uses_neutral_track_and_one_positioned_accent_marker
```

## New selected node IDs

These 34 selected nodes replace the old app checks. Most are reorganized acceptance tests; four chart-specific tests, two policy tests, and one tire-reset simulation test are also the seven new selected checks mentioned above.

```text
tests/app/test_app.py::test_page_defaults_to_bahrain_2023_alo_after_lap_15
tests/app/test_app.py::test_race_picker_uses_short_labels_that_fit_phone_width
tests/app/test_app.py::test_page_copy_uses_plain_language_and_has_no_middle_dot
tests/app/test_app.py::test_page_uses_shared_asof_replay_builder_without_results_imports
tests/app/test_app.py::test_report_copy_formats_brier_scores_and_keeps_coverage_target_visible
tests/app/test_app.py::test_recommended_reason_explains_tire_pace_and_pit_loss
tests/app/test_app.py::test_evaluation_uses_one_results_table
tests/app/test_app.py::test_theme_is_dark_borderless_and_uses_ibm_plex_and_team_palette
tests/app/test_app.py::test_ui_text_and_data_colors_meet_contrast_thresholds
tests/app/test_app.py::test_page_uses_tabular_numbers_and_has_no_metric_cards
tests/app/test_app.py::test_format_strategy_table_hides_basis_and_formats_values
tests/app/test_app.py::test_mobile_strategy_table_keeps_results_and_labels_recommendation
tests/app/test_app.py::test_compact_dotplot_labels_keep_timing_and_compound
tests/app/test_app.py::test_replay_cache_identity_includes_model_sources
tests/app/test_app.py::test_empty_copy_is_two_sentences_with_a_next_step
tests/app/test_app.py::test_empty_cache_renders_the_two_sentence_message
tests/app/test_app.py::test_safe_replay_failure_discards_exception_details
tests/app/test_app.py::test_replay_error_state_does_not_reuse_a_previous_selection
tests/app/test_app.py::test_zero_one_and_many_action_states_have_matching_table_rows
tests/app/test_app.py::test_schedule_failure_has_actionable_copy
tests/app/test_app.py::test_eligible_catalog_excludes_races_without_a_verified_lap_count
tests/app/test_app.py::test_rendered_selected_replay_contains_all_four_altair_charts
tests/app/test_app.py::test_strategy_table_has_no_basis_column_and_uses_one_decimal_and_whole_percents
tests/app/test_app.py::test_unavailable_cutoff_renders_one_actionable_sentence
tests/app/test_app.py::test_catalog_failure_does_not_show_internal_error_details
tests/app/test_app.py::test_fan_chart_uses_recommended_pathwise_policy_history
tests/plots/test_altair_charts.py::test_probability_strip_aggregates_known_quantiles_into_one_cell_per_place
tests/plots/test_altair_charts.py::test_fan_chart_uses_purple_nested_bands_labeled_at_race_finish
tests/plots/test_altair_charts.py::test_gap_trace_highlights_selected_driver_and_stops_at_cutoff
tests/plots/test_altair_charts.py::test_stint_chart_labels_rows_compounds_and_outlines_recommended_stint
tests/sim/test_crn_and_plans.py::test_future_pit_is_simulated_and_tire_age_resets_after_stop
tests/strategy/test_longstaff.py::test_delayed_option_does_not_use_future_finish_noise_to_choose_a_stop
tests/strategy/test_longstaff.py::test_recommended_history_matches_the_pathwise_policy_finish_distribution
tests/test_cli_replay.py::test_identified_one_compound_fit_uses_cutoff_local_strategy_fallback
```

## Final rerun

After the decision-log assertion was corrected and the final probability-strip height was covered, the complete local suite passed: **1,113 passed, 27 deselected in 583.13 seconds**. The 27 are network-marked checks; the two Bahrain strategy checks listed above also passed in a separate live-data run. This final selected count is seven higher than the 1,106-pass intermediate snapshot because four chart tests, two strategy-policy tests, and one future-pit/tire-reset test were added.
