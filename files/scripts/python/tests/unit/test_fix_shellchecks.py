from pathlib import Path
from unittest.mock import patch

import pytest

from fix_shellchecks import (
    DEFAULT_ISSUES_LOG_PATH,
    DEFAULT_SC2086_SKIP_VARS,
    EditSpan,
    RuleHandlerRegistry,
    ShellCheckFinding,
    apply_edits_to_content,
    build_disable_edits_for_findings,
    build_effective_skip_vars,
    collect_edits_from_findings,
    create_default_registry,
    format_parsed_findings_summary,
    main,
    make_sc1091_handler,
    make_sc2004_handler,
    make_sc2034_handler,
    make_sc2046_handler,
    make_sc2061_handler,
    make_sc2155_handler,
    make_sc2181_handler,
    make_sc2268_handler,
    make_sc2317_handler,
    make_sc2329_handler,
    parse_shellcheck_findings,
    parse_shellcheck_output,
    process_edits,
    prompt_generate_log,
    strip_ansi,
)

# ---------------------------------------------------------------------------
# Test Data Fixtures
# ---------------------------------------------------------------------------

SAMPLE_SC2086_LOG_ANSI = (
    "\x1b[1mIn files/scripts/sample.sh line 3:\x1b[0m\n"
    "\x1b[0m    if [ $LOG_LEVEL -ge $LOG_ERROR ]; then\x1b[0m\n"
    "\x1b[32m         ^--------^ SC2086 (info): Double quote to prevent globbing and word splitting.\x1b[0m\n"
    "\x1b[1mDid you mean: \x1b[0m\n"
    '    if [ "$LOG_LEVEL" -ge $LOG_ERROR ]; then\n'
    "\n"
    "\x1b[1mIn files/scripts/sample.sh line 5:\x1b[0m\n"
    "\x1b[0m    docker cp ${CONTAINER_NAME}:${HTTPD_LOG_FILE} ${FETCHED_LOG_FILE}\x1b[0m\n"
    "\x1b[32m              ^---------------^ SC2086 (info): Double quote to prevent globbing and word splitting.\x1b[0m\n"
    "\x1b[32m                                ^---------------^ SC2086 (info): Double quote to prevent globbing and word splitting.\x1b[0m\n"
    "\x1b[32m                                                  ^-----------------^ SC2086 (info): Double quote to prevent globbing and word splitting.\x1b[0m\n"
)

MIXED_RULES_LOG = (
    "In files/scripts/sample.sh line 3:\n"
    "    if [ $LOG_LEVEL -ge $LOG_ERROR ]; then\n"
    "         ^--------^ SC2086 (info): Double quote to prevent globbing and word splitting.\n"
    "\n"
    "In files/scripts/sample.sh line 4:\n"
    "    local foo=$(bar)\n"
    "          ^-^ SC2155 (warning): Declare and assign separately to avoid masking return values.\n"
)

SAMPLE_SCRIPT_CONTENT = (
    "#!/usr/bin/env bash\n"
    "LOG_LEVEL=1\n"
    "    if [ $LOG_LEVEL -ge $LOG_ERROR ]; then\n"
    '        echo "error"\n'
    "    docker cp ${CONTAINER_NAME}:${HTTPD_LOG_FILE} ${FETCHED_LOG_FILE}\n"
    "    ${cmd} 2>&1 | tee -a ${LOG_FILE}\n"
    "    fi\n"
)


# ---------------------------------------------------------------------------
# 1. Tests for Parsing, Registry & Extensible Rule Dispatch
# ---------------------------------------------------------------------------


class TestRegistryAndParsing:
    def test_strip_ansi_removes_escape_codes(self):
        """Tests that ANSI formatting sequences are cleanly stripped."""
        cleaned = strip_ansi(SAMPLE_SC2086_LOG_ANSI)
        assert "\x1b[" not in cleaned
        assert "In files/scripts/sample.sh line 3:" in cleaned

    def test_parse_findings_captures_rules_and_carets(self):
        """Tests that findings across multiple ShellCheck rules are parsed cleanly."""
        findings = parse_shellcheck_findings(MIXED_RULES_LOG)
        assert len(findings) == 2
        assert findings[0].rule == "SC2086"
        assert findings[0].lineno == 3
        assert findings[1].rule == "SC2155"
        assert findings[1].lineno == 4

    def test_default_registry_includes_all_registered_handlers(self):
        """Tests that default registry registers all implemented handlers."""
        registry = create_default_registry()
        assert registry.supported_rules() == [
            "SC1091",
            "SC2001",
            "SC2004",
            "SC2034",
            "SC2046",
            "SC2061",
            "SC2086",
            "SC2155",
            "SC2181",
            "SC2268",
            "SC2317",
            "SC2329",
        ]

    def test_custom_rule_handler_registration_and_dispatch(self):
        """Tests that a custom handler for a future rule can be registered and invoked."""
        registry = create_default_registry(rules=["SC2086"])
        assert registry.supported_rules() == ["SC2086"]

        def _fake_sc9999_handler(finding: ShellCheckFinding):
            return [
                EditSpan(
                    lineno=finding.lineno,
                    start=0,
                    end=3,
                    replacement="NEW",
                    rule=finding.rule,
                    expected_original="OLD",
                )
            ]

        custom_registry = RuleHandlerRegistry()
        custom_registry.register("SC9999", _fake_sc9999_handler)

        finding = ShellCheckFinding(
            filepath="demo.sh",
            lineno=1,
            src_line="OLD=1",
            caret_offset=0,
            caret_len=3,
            rule="SC9999",
            message="custom rule",
        )
        edits = collect_edits_from_findings([finding], custom_registry)
        assert edits == {
            "demo.sh": [
                EditSpan(
                    lineno=1,
                    start=0,
                    end=3,
                    replacement="NEW",
                    rule="SC9999",
                    expected_original="OLD",
                )
            ]
        }

    def test_format_parsed_findings_summary_reports_handled_and_unhandled_rules(self):
        findings = parse_shellcheck_findings(MIXED_RULES_LOG)
        edits_by_file = {
            "files/scripts/sample.sh": [
                EditSpan(
                    lineno=3,
                    start=9,
                    end=19,
                    replacement='"$LOG_LEVEL"',
                    rule="SC2086",
                    expected_original="$LOG_LEVEL",
                ),
                EditSpan(
                    lineno=3,
                    start=23,
                    end=33,
                    replacement='"$LOG_ERROR"',
                    rule="SC2086",
                    expected_original="$LOG_ERROR",
                ),
            ]
        }
        summary = format_parsed_findings_summary(
            findings=findings,
            handled_rules=["SC2001", "SC2086"],
            candidate_edits_by_file=edits_by_file,
        )
        assert "Parsed 2 ShellCheck finding(s) across 1 file(s):" in summary
        assert "SC2086" in summary and "handled, 2 candidate edit(s)" in summary
        assert "SC2155" in summary and "unhandled" in summary


# ---------------------------------------------------------------------------
# 2. Tests for SC2061 and SC2086 Handler Behavior
# ---------------------------------------------------------------------------


class TestSc2004Sc2268AndSc2046Handlers:
    def test_sc2004_strips_braced_vars_inside_arithmetic_expansion(self):
        """Tests that ${VAR} inside $((...)) is rewritten to VAR."""
        handler = make_sc2004_handler()
        line = "  idx=$((${idx} + ${offset}))\n"
        finding = ShellCheckFinding(
            filepath="script.sh",
            lineno=1,
            src_line=line,
            caret_offset=9,
            caret_len=6,
            rule="SC2004",
            message="$ / ${} is unnecessary on arithmetic variables.",
        )

        updated, count = apply_edits_to_content(line, handler(finding))
        assert count == 2
        assert updated == "  idx=$((idx + offset))\n"

    def test_sc2268_rewrites_x_prefixed_comparison(self):
        """Tests that "x$var" != "x" is rewritten to "$var" != ""."""
        handler = make_sc2268_handler()
        line = '  if [ "x$var" != "x" ]; then\n'
        finding = ShellCheckFinding(
            filepath="script.sh",
            lineno=1,
            src_line=line,
            caret_offset=7,
            caret_len=6,
            rule="SC2268",
            message="Avoid x-prefix in comparisons as it no longer serves a purpose.",
        )

        updated, count = apply_edits_to_content(line, handler(finding))
        assert count == 1
        assert updated == '  if [ "$var" != "" ]; then\n'

    def test_sc2046_quotes_unquoted_command_substitutions(self):
        """Tests that unquoted $(...) is quoted while already-quoted or nested forms stay clean."""
        handler = make_sc2046_handler()
        line = "  dir=$(dirname $(readlink -f $0))\n"
        finding = ShellCheckFinding(
            filepath="script.sh",
            lineno=1,
            src_line=line,
            caret_offset=8,
            caret_len=27,
            rule="SC2046",
            message="Quote this to prevent word splitting.",
        )

        updated, count = apply_edits_to_content(line, handler(finding))
        assert count == 1
        assert updated == '  dir="$(dirname $(readlink -f $0))"\n'

        already_quoted = '  dir="$(dirname "$0")"\n'
        finding_quoted = ShellCheckFinding(
            filepath="script.sh",
            lineno=1,
            src_line=already_quoted,
            caret_offset=8,
            caret_len=21,
            rule="SC2046",
            message="Quote this to prevent word splitting.",
        )
        assert handler(finding_quoted) == []


class TestSc2061Handler:
    def test_quotes_unquoted_find_name_patterns(self):
        """Tests quoting unquoted -name patterns with and without nested variable quotes."""
        handler = make_sc2061_handler()

        line_var = 'ROOT_CERT=$(find "${CACERTS_SRC}"/ -name cert*."${CACERT_TRUST_FORMAT}" | sort -nr | head -1)\n'
        f_var = ShellCheckFinding(
            filepath="install-cacerts.sh",
            lineno=1,
            src_line=line_var,
            caret_offset=40,
            caret_len=28,
            rule="SC2061",
            message="Quote the parameter to -name so the shell won't interpret it.",
        )
        updated_var, count_var = apply_edits_to_content(line_var, handler(f_var))
        assert count_var == 1
        assert (
            updated_var
            == 'ROOT_CERT=$(find "${CACERTS_SRC}"/ -name "cert*.${CACERT_TRUST_FORMAT}" | sort -nr | head -1)\n'
        )

        line_pem = 'ROOT_CERT=$(find "${CACERTS_SRC}"/ -name cert*.pem | sort -nr | head -1)\n'
        f_pem = ShellCheckFinding(
            filepath="install-cacerts.sh",
            lineno=1,
            src_line=line_pem,
            caret_offset=40,
            caret_len=9,
            rule="SC2061",
            message="Quote the parameter to -name so the shell won't interpret it.",
        )
        updated_pem, count_pem = apply_edits_to_content(line_pem, handler(f_pem))
        assert count_pem == 1
        assert (
            updated_pem
            == 'ROOT_CERT=$(find "${CACERTS_SRC}"/ -name "cert*.pem" | sort -nr | head -1)\n'
        )


class TestSc2086Handler:
    def test_parse_single_and_multiple_spans_per_line(self):
        """Tests default quote-all-on-line behavior across lines with single or multiple findings."""
        edits_by_file = parse_shellcheck_output(SAMPLE_SC2086_LOG_ANSI)

        assert "files/scripts/sample.sh" in edits_by_file
        unique_spans = list(dict.fromkeys(edits_by_file["files/scripts/sample.sh"]))
        assert len(unique_spans) == 5

        line3_spans = [s for s in unique_spans if s.lineno == 3]
        assert [s.replacement for s in line3_spans] == ['"$LOG_LEVEL"', '"$LOG_ERROR"']

        line5_spans = [s for s in unique_spans if s.lineno == 5]
        assert [s.replacement for s in line5_spans] == [
            '"${CONTAINER_NAME}"',
            '"${HTTPD_LOG_FILE}"',
            '"${FETCHED_LOG_FILE}"',
        ]

    def test_fallback_caret_only_mode(self):
        """Tests quote_all_on_line=False fallback quotes only the caret-targeted variable."""
        edits_by_file = parse_shellcheck_output(
            SAMPLE_SC2086_LOG_ANSI,
            quote_all_on_line=False,
        )

        spans = edits_by_file["files/scripts/sample.sh"]
        line3_spans = [s for s in spans if s.lineno == 3]
        assert [s.replacement for s in line3_spans] == ['"$LOG_LEVEL"']

    def test_skip_vars_filtering(self):
        """Tests that variables in skip_vars are excluded while unquoted companion vars are quoted."""
        log_text = (
            "In files/scripts/sample.sh line 6:\n"
            "    ${cmd} 2>&1 | tee -a ${LOG_FILE}\n"
            "    ^----^ SC2086 (info): Double quote to prevent globbing and word splitting.\n"
            "                         ^---------^ SC2086 (info): Double quote to prevent globbing and word splitting.\n"
        )
        edits = parse_shellcheck_output(log_text, skip_vars={"cmd"})
        unique_spans = list(dict.fromkeys(edits["files/scripts/sample.sh"]))
        assert len(unique_spans) == 1
        assert unique_spans[0].replacement == '"${LOG_FILE}"'

    def test_already_quoted_tokens_are_ignored(self):
        """Tests that tokens already inside double quotes or standalone quotes are skipped."""
        log_text = (
            "In files/scripts/sample.sh line 2:\n"
            '    echo "$ALREADY_QUOTED" "$PREFIX_${INNER}/path" $UNQUOTED\n'
            "          ^-------------^ SC2086 (info): Double quote to prevent globbing and word splitting.\n"
        )
        edits = parse_shellcheck_output(log_text)
        spans = edits["files/scripts/sample.sh"]
        assert [s.replacement for s in spans] == ['"$UNQUOTED"']

    def test_ignores_unhandled_rules_in_mixed_log(self):
        """Tests that rules without a registered handler are safely ignored."""
        edits = parse_shellcheck_output(MIXED_RULES_LOG, rules=["SC2086"])
        assert "files/scripts/sample.sh" in edits
        spans = edits["files/scripts/sample.sh"]
        assert len(spans) == 2
        assert all(s.lineno == 3 for s in spans)
        assert [s.replacement for s in spans] == ['"$LOG_LEVEL"', '"$LOG_ERROR"']


# ---------------------------------------------------------------------------
# 3. Tests for SC2155, SC2181 and SC1091 Handlers
# ---------------------------------------------------------------------------


class TestSc2155Handler:
    def test_splits_local_and_readonly_declarations_cleanly(self):
        """Tests splitting single-variable local and readonly assignments."""
        handler = make_sc2155_handler()

        f_local = ShellCheckFinding(
            filepath="script.sh",
            lineno=1,
            src_line="    local DATE=$(date +%Y%m%d)\n",
            caret_offset=10,
            caret_len=4,
            rule="SC2155",
            message="Declare and assign separately to avoid masking return values.",
        )
        updated_local, count_local = apply_edits_to_content(
            f_local.src_line, handler(f_local)
        )
        assert count_local == 2
        assert updated_local == "    local DATE\n    DATE=$(date +%Y%m%d)\n"

        f_readonly = ShellCheckFinding(
            filepath="render.sh",
            lineno=1,
            src_line='  readonly content="$(cat "$template")"\n',
            caret_offset=11,
            caret_len=7,
            rule="SC2155",
            message="Declare and assign separately to avoid masking return values.",
        )
        updated_ro, count_ro = apply_edits_to_content(
            f_readonly.src_line, handler(f_readonly)
        )
        assert count_ro == 2
        assert (
            updated_ro
            == '  readonly content\n  content="$(cat "$template")"\n'
        )

    def test_skips_multi_assignment_lines_safely(self, caplog):
        """Tests that multi-assignment lines like `local a=$(x) b=$(y)` are skipped."""
        handler = make_sc2155_handler()
        caplog.set_level("DEBUG")

        finding = ShellCheckFinding(
            filepath="script.sh",
            lineno=10,
            src_line="    local a=$(x) b=$(y)\n",
            caret_offset=10,
            caret_len=1,
            rule="SC2155",
            message="Declare and assign separately to avoid masking return values.",
        )
        assert handler(finding) == []
        assert "multiple variable assignments on line" in caplog.text


class TestSc2181AndSc1091Handlers:
    def test_sc2181_handler_skips_safely_without_guessing_command(self, caplog):
        """Tests that SC2181 logs and returns no edits for standalone and compound $? checks."""
        handler = make_sc2181_handler()
        caplog.set_level("DEBUG")

        f_simple = ShellCheckFinding(
            filepath="script.sh",
            lineno=13,
            src_line="if [ $? -ne 0 ]; then",
            caret_offset=5,
            caret_len=2,
            rule="SC2181",
            message="Check exit code directly with e.g. 'if mycmd;', not indirectly with $?.",
        )
        f_compound = ShellCheckFinding(
            filepath="script.sh",
            lineno=129,
            src_line="if [ $? -eq 0 ] && [ -s init.txt ]; then",
            caret_offset=16,
            caret_len=2,
            rule="SC2181",
            message="Check exit code directly with e.g. 'if mycmd;', not indirectly with $?.",
        )

        assert handler(f_simple) == []
        assert handler(f_compound) == []
        assert "preceding command context is outside the line" in caplog.text
        assert "compound condition with &&/|| requires manual review" in caplog.text

    def test_sc1091_handler_inserts_directive_for_dynamic_and_static_sources(
        self, tmp_path: Path
    ):
        """Tests that SC1091 converts '.' to 'source' and inserts # shellcheck source=... above statements."""
        handler = make_sc1091_handler(base_dir=tmp_path)

        f_dyn = ShellCheckFinding(
            filepath="files/scripts/git/sync.sh",
            lineno=510,
            src_line='        . "${REPO_DIR}/.rsync-post-sync"',
            caret_offset=10,
            caret_len=28,
            rule="SC1091",
            message="Not following: ./.rsync-post-sync was not specified as input",
        )
        edits_dyn = handler(f_dyn)
        assert len(edits_dyn) == 2
        assert edits_dyn[0].replacement == "source"
        assert edits_dyn[1].lineno == 510
        assert edits_dyn[1].start == 0
        assert edits_dyn[1].end == 0
        assert edits_dyn[1].replacement == "        # shellcheck source=/dev/null\n"

        f_rel = ShellCheckFinding(
            filepath="files/scripts/rename/rename-wrapper.sh",
            lineno=19,
            src_line=". ../utils.sh",
            caret_offset=2,
            caret_len=9,
            rule="SC1091",
            message="Not following: ../utils.sh was not specified as input",
        )
        edits_rel = handler(f_rel)
        assert len(edits_rel) == 2
        assert edits_rel[0].replacement == "source"
        assert edits_rel[1].replacement == "# shellcheck source=../utils.sh\n"

    def test_sc1091_end_to_end_apply_to_file(self, tmp_path: Path):
        """Tests applying an SC1091 directive and source conversion cleanly to a script file."""
        script_path = tmp_path / "files/scripts/rename/rename-wrapper.sh"
        script_path.parent.mkdir(parents=True)
        script_path.write_text("#!/usr/bin/env bash\n. ../utils.sh\necho ok\n", encoding="utf-8")

        log_text = (
            "In files/scripts/rename/rename-wrapper.sh line 2:\n"
            ". ../utils.sh\n"
            "  ^---------^ SC1091 (info): Not following: ../utils.sh was not specified as input\n"
        )
        registry = create_default_registry(rules=["SC1091"], base_dir=tmp_path)
        edits = parse_shellcheck_output(log_text, registry=registry)
        files_changed, total_edits = process_edits(edits, write=True, base_dir=tmp_path)

        assert files_changed == 1
        assert total_edits == 2
        assert (
            script_path.read_text(encoding="utf-8")
            == "#!/usr/bin/env bash\n# shellcheck source=../utils.sh\nsource ../utils.sh\necho ok\n"
        )


# ---------------------------------------------------------------------------
# 4. Tests for Applying Edits & File Operations
# ---------------------------------------------------------------------------


class TestApplyEdits:
    def test_apply_multiple_edits_on_same_line_preserves_offsets(self):
        """Tests right-to-left replacement when multiple spans exist on one line."""
        src = "    docker cp ${CONTAINER_NAME}:${HTTPD_LOG_FILE} ${FETCHED_LOG_FILE}\n"
        spans = [
            EditSpan(
                lineno=1,
                start=14,
                end=31,
                replacement='"${CONTAINER_NAME}"',
                rule="SC2086",
                expected_original="${CONTAINER_NAME}",
            ),
            EditSpan(
                lineno=1,
                start=32,
                end=49,
                replacement='"${HTTPD_LOG_FILE}"',
                rule="SC2086",
                expected_original="${HTTPD_LOG_FILE}",
            ),
            EditSpan(
                lineno=1,
                start=50,
                end=69,
                replacement='"${FETCHED_LOG_FILE}"',
                rule="SC2086",
                expected_original="${FETCHED_LOG_FILE}",
            ),
        ]

        updated, count = apply_edits_to_content(src, spans)
        assert count == 3
        assert (
            updated
            == '    docker cp "${CONTAINER_NAME}":"${HTTPD_LOG_FILE}" "${FETCHED_LOG_FILE}"\n'
        )

    def test_deduplicates_identical_spans(self):
        """Tests that duplicate EditSpan entries do not apply a replacement twice."""
        src = "rm $f\n"
        spans = [
            EditSpan(
                lineno=1,
                start=3,
                end=5,
                replacement='"$f"',
                rule="SC2086",
                expected_original="$f",
            ),
            EditSpan(
                lineno=1,
                start=3,
                end=5,
                replacement='"$f"',
                rule="SC2086",
                expected_original="$f",
            ),
        ]

        updated, count = apply_edits_to_content(src, spans)
        assert count == 1
        assert updated == 'rm "$f"\n'

    def test_out_of_range_and_mismatched_tokens_skipped_safely(self):
        """Tests graceful handling when line numbers or column offsets do not match source."""
        src = "echo $FOO\n"
        spans = [
            EditSpan(
                lineno=99,
                start=0,
                end=4,
                replacement='"$FOO"',
                rule="SC2086",
                expected_original="$FOO",
            ),
            EditSpan(
                lineno=1,
                start=5,
                end=9,
                replacement='"$BAR"',
                rule="SC2086",
                expected_original="$BAR",
            ),
        ]

        updated, count = apply_edits_to_content(src, spans)
        assert count == 0
        assert updated == src

    def test_process_edits_dry_run_vs_write(self, tmp_path: Path):
        """Tests that dry-run leaves files untouched while write=True updates them in place."""
        script_rel = Path("files/scripts/sample.sh")
        script_abs = tmp_path / script_rel
        script_abs.parent.mkdir(parents=True)
        script_abs.write_text(SAMPLE_SCRIPT_CONTENT, encoding="utf-8")

        registry = create_default_registry(
            rules=["SC2086"], skip_vars=DEFAULT_SC2086_SKIP_VARS
        )
        edits = parse_shellcheck_output(SAMPLE_SC2086_LOG_ANSI, registry=registry)

        files_changed, total_edits = process_edits(edits, write=False, base_dir=tmp_path)
        assert files_changed == 1
        assert total_edits == 5
        assert script_abs.read_text(encoding="utf-8") == SAMPLE_SCRIPT_CONTENT

        files_changed, total_edits = process_edits(edits, write=True, base_dir=tmp_path)
        assert files_changed == 1
        assert total_edits == 5

        new_content = script_abs.read_text(encoding="utf-8")
        assert 'if [ "$LOG_LEVEL" -ge "$LOG_ERROR" ]; then' in new_content
        assert (
            'docker cp "${CONTAINER_NAME}":"${HTTPD_LOG_FILE}" "${FETCHED_LOG_FILE}"'
            in new_content
        )
        assert "${cmd}" in new_content


# ---------------------------------------------------------------------------
# 5. Tests for Skip-List Configuration, Log Generation & CLI Entrypoint
# ---------------------------------------------------------------------------


class TestCliAndSkipConfiguration:
    def test_build_effective_skip_vars(self):
        """Tests combining --skip-vars, --include-vars, and --no-default-skip."""
        default_plus = build_effective_skip_vars(
            no_default_skip=False,
            extra_skip=["EXTRA_FLAGS"],
            include_vars=["cmd"],
        )
        assert "EXTRA_FLAGS" in default_plus
        assert "cmd" not in default_plus
        assert "EXCLUDES" in default_plus

        cleared = build_effective_skip_vars(
            no_default_skip=True,
            extra_skip=["ONLY_THIS"],
            include_vars=[],
        )
        assert cleared == {"ONLY_THIS"}

    def test_prompt_generate_log_interactive_and_flags(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        monkeypatch.setattr("builtins.input", lambda _: "y")
        assert prompt_generate_log(DEFAULT_ISSUES_LOG_PATH) is True

        monkeypatch.setattr("builtins.input", lambda _: "n")
        assert prompt_generate_log(DEFAULT_ISSUES_LOG_PATH) is False

        assert prompt_generate_log(DEFAULT_ISSUES_LOG_PATH, assume_yes=True) is True
        assert (
            prompt_generate_log(DEFAULT_ISSUES_LOG_PATH, assume_yes=True, no_prompt=True)
            is False
        )

    def test_cli_main_generates_missing_log_when_confirmed(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.chdir(tmp_path)

        script_path = tmp_path / "files/scripts/sample.sh"
        script_path.parent.mkdir(parents=True)
        script_path.write_text(SAMPLE_SCRIPT_CONTENT, encoding="utf-8")

        missing_log = tmp_path / ".shellcheck-issues.txt"

        class FakeCompletedProcess:
            returncode = 1
            stdout = SAMPLE_SC2086_LOG_ANSI
            stderr = ""

        with (
            patch("fix_shellchecks.prompt_generate_log", return_value=True) as mock_prompt,
            patch(
                "fix_shellchecks.subprocess.run", return_value=FakeCompletedProcess()
            ) as mock_run,
        ):
            exit_code = main(
                [str(missing_log), "--scan-paths", "files/scripts/sample.sh", "-w"]
            )

        assert exit_code == 0
        mock_prompt.assert_called_once()
        mock_run.assert_called_once()
        assert missing_log.is_file()
        assert 'if [ "$LOG_LEVEL" -ge "$LOG_ERROR" ]; then' in script_path.read_text(
            encoding="utf-8"
        )

    def test_cli_main_generates_missing_log_with_handled_rules_enabled(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """Tests that generating a missing log omits --enable by default and respects --enable-rule / --use-rc."""
        monkeypatch.chdir(tmp_path)

        script_path = tmp_path / "files/scripts/sample.sh"
        script_path.parent.mkdir(parents=True)
        script_path.write_text(SAMPLE_SCRIPT_CONTENT, encoding="utf-8")

        missing_log = tmp_path / ".shellcheck-issues.txt"
        captured_cmds = []

        class FakeCompletedProcess:
            returncode = 1
            stdout = SAMPLE_SC2086_LOG_ANSI
            stderr = ""

        def _fake_run(cmd, capture_output, text, check):
            captured_cmds.append(cmd)
            return FakeCompletedProcess()

        with (
            patch("fix_shellchecks.prompt_generate_log", return_value=True),
            patch("fix_shellchecks.subprocess.run", side_effect=_fake_run),
        ):
            exit_code = main(
                [str(missing_log), "--scan-paths", "files/scripts/sample.sh"]
            )

        assert exit_code == 0
        assert len(captured_cmds) == 1
        assert "--norc" in captured_cmds[0]
        assert "--enable" not in captured_cmds[0]

        captured_cmds.clear()
        missing_log.unlink()

        with (
            patch("fix_shellchecks.prompt_generate_log", return_value=True),
            patch("fix_shellchecks.subprocess.run", side_effect=_fake_run),
        ):
            exit_code = main(
                [
                    str(missing_log),
                    "--scan-paths",
                    "files/scripts/sample.sh",
                    "--enable-rule",
                    "SC2086",
                    "--use-rc",
                ]
            )

        assert exit_code == 0
        assert len(captured_cmds) == 1
        assert "--norc" not in captured_cmds[0]
        assert "--enable" in captured_cmds[0]
        enable_idx = captured_cmds[0].index("--enable")
        assert captured_cmds[0][enable_idx + 1] == "SC2086"

    def test_cli_main_end_to_end_with_log_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """Tests full CLI execution reading a ShellCheck log and writing fixes."""
        monkeypatch.chdir(tmp_path)

        script_path = tmp_path / "files/scripts/sample.sh"
        script_path.parent.mkdir(parents=True)
        script_path.write_text(SAMPLE_SCRIPT_CONTENT, encoding="utf-8")

        log_path = tmp_path / ".shellcheck-issues.txt"
        log_path.write_text(SAMPLE_SC2086_LOG_ANSI, encoding="utf-8")

        # Pass positional target before variadic --rules so --rules doesn't swallow log_path
        exit_code = main([str(log_path), "-w", "--rules", "SC2086"])
        assert exit_code == 0

        updated = script_path.read_text(encoding="utf-8")
        assert 'if [ "$LOG_LEVEL" -ge "$LOG_ERROR" ]; then' in updated
        assert (
            'docker cp "${CONTAINER_NAME}":"${HTTPD_LOG_FILE}" "${FETCHED_LOG_FILE}"'
            in updated
        )

    def test_cli_main_no_quote_all_on_line_flag(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """Tests --no-quote-all-on-line falls back to single-variable quoting."""
        monkeypatch.chdir(tmp_path)

        script_path = tmp_path / "files/scripts/sample.sh"
        script_path.parent.mkdir(parents=True)
        script_path.write_text(SAMPLE_SCRIPT_CONTENT, encoding="utf-8")

        log_path = tmp_path / ".shellcheck-issues.txt"
        log_path.write_text(SAMPLE_SC2086_LOG_ANSI, encoding="utf-8")

        exit_code = main(
            [str(log_path), "-w", "--no-quote-all-on-line", "--rules", "SC2086"]
        )
        assert exit_code == 0

        updated = script_path.read_text(encoding="utf-8")
        assert 'if [ "$LOG_LEVEL" -ge $LOG_ERROR ]; then' in updated

    def test_cli_main_missing_log_declined_returns_error(self, tmp_path: Path):
        """Tests that passing a non-existent log path exits with code 1."""
        missing = tmp_path / ".shellcheck-issues.txt"
        with patch("fix_shellchecks.prompt_generate_log", return_value=False):
            exit_code = main([str(missing)])
        assert exit_code == 1

    def test_cli_main_run_shellcheck_mode(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """Tests --run-shellcheck mode using mocked subprocess output."""
        monkeypatch.chdir(tmp_path)

        script_path = tmp_path / "files/scripts/sample.sh"
        script_path.parent.mkdir(parents=True)
        script_path.write_text(SAMPLE_SCRIPT_CONTENT, encoding="utf-8")

        class FakeCompletedProcess:
            returncode = 1
            stdout = SAMPLE_SC2086_LOG_ANSI
            stderr = ""

        with patch(
            "fix_shellchecks.subprocess.run", return_value=FakeCompletedProcess()
        ) as mock_run:
            exit_code = main(["files/scripts/sample.sh", "--run-shellcheck", "-w"])

        assert exit_code == 0
        mock_run.assert_called_once()
        assert 'if [ "$LOG_LEVEL" -ge "$LOG_ERROR" ]; then' in script_path.read_text(
            encoding="utf-8"
        )


class TestDotSourceAndDisableDirectives:
    def test_sc1091_converts_dot_to_source_and_adds_directive(self, tmp_path: Path):
        script_path = tmp_path / "files/scripts/rename/rename-wrapper.sh"
        script_path.parent.mkdir(parents=True)
        script_path.write_text(
            "#!/usr/bin/env bash\n. ../utils.sh\necho ok\n", encoding="utf-8"
        )

        log_text = (
            "In files/scripts/rename/rename-wrapper.sh line 2:\n"
            ". ../utils.sh\n"
            "  ^---------^ SC1091 (info): Not following: ../utils.sh was not specified as input\n"
        )
        registry = create_default_registry(rules=["SC1091"], base_dir=tmp_path)
        edits = parse_shellcheck_output(log_text, registry=registry)
        files_changed, total_edits = process_edits(edits, write=True, base_dir=tmp_path)

        assert files_changed == 1
        assert total_edits == 2
        assert (
            script_path.read_text(encoding="utf-8")
            == "#!/usr/bin/env bash\n# shellcheck source=../utils.sh\nsource ../utils.sh\necho ok\n"
        )

    def test_disable_directives_inserted_and_merged_for_skipped_and_unhandled(self):
        content = (
            "#!/usr/bin/env bash\n"
            "# shellcheck disable=SC2086\n"
            "if [ $? -ne 0 ]; then\n"
            "  echo fail\n"
            "fi\n"
            "local foo=$(bar)\n"
        )
        findings = [
            ShellCheckFinding(
                filepath="demo.sh",
                lineno=3,
                src_line="if [ $? -ne 0 ]; then",
                caret_offset=5,
                caret_len=2,
                rule="SC2181",
                message="Check exit code directly",
            ),
            ShellCheckFinding(
                filepath="demo.sh",
                lineno=6,
                src_line="local foo=$(bar)",
                caret_offset=10,
                caret_len=3,
                rule="SC2155",
                message="Declare and assign separately",
            ),
        ]

        disable_edits = build_disable_edits_for_findings(
            findings, {"demo.sh": content}
        )
        updated, count = apply_edits_to_content(content, disable_edits["demo.sh"])

        assert count == 2
        assert "# shellcheck disable=SC2086,SC2181\n" in updated
        assert "# shellcheck disable=SC2155\nlocal foo=$(bar)\n" in updated

    def test_cli_disable_unhandled_flag_in_dry_run_and_write(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.chdir(tmp_path)
        script_path = tmp_path / "files/scripts/sample.sh"
        script_path.parent.mkdir(parents=True)
        script_path.write_text(
            "#!/usr/bin/env bash\nif [ $? -ne 0 ]; then\n  true\nfi\n",
            encoding="utf-8",
        )
        log_path = tmp_path / ".shellcheck-issues.txt"
        log_path.write_text(
            "In files/scripts/sample.sh line 2:\n"
            "if [ $? -ne 0 ]; then\n"
            "     ^-^ SC2181 (style): Check exit code directly.\n",
            encoding="utf-8",
        )

        # Dry-run leaves file untouched
        assert main([str(log_path), "--disable-unhandled"]) == 0
        assert "# shellcheck disable=SC2181" not in script_path.read_text(
            encoding="utf-8"
        )

        # Write mode applies directive
        assert main([str(log_path), "--disable-unhandled", "-w"]) == 0
        assert "# shellcheck disable=SC2181\nif [ $? -ne 0 ]; then" in script_path.read_text(
            encoding="utf-8"
        )


class TestUsageAndReachabilityHandlers:
    def test_sc2329_sc2317_sc2034_handlers_skip_safely(self, caplog):
        """Tests that high-risk usage/reachability rules log and return no edits."""
        caplog.set_level("DEBUG")

        h2329 = make_sc2329_handler()
        h2317 = make_sc2317_handler()
        h2034 = make_sc2034_handler()

        f2329 = ShellCheckFinding(
            filepath="files/scripts/mac_os/macos_setup_codesign.sh",
            lineno=13,
            src_line="function cleanup {",
            caret_offset=0,
            caret_len=3,
            rule="SC2329",
            message="This function is never invoked.",
        )
        f2317 = ShellCheckFinding(
            filepath="files/scripts/docker/docker-image-pull-curl.sh",
            lineno=614,
            src_line='        echo "after fail"',
            caret_offset=8,
            caret_len=15,
            rule="SC2317",
            message="Command appears to be unreachable.",
        )
        f2034 = ShellCheckFinding(
            filepath="files/scripts/sync-bashenv.sh",
            lineno=3,
            src_line='DATE="$(date +%Y%m%d%H%M%S)"',
            caret_offset=0,
            caret_len=4,
            rule="SC2034",
            message="DATE appears unused.",
        )

        assert h2329(f2329) == []
        assert h2317(f2317) == []
        assert h2034(f2034) == []
        assert "Skipping SC2329" in caplog.text
        assert "Skipping SC2317" in caplog.text
        assert "Skipping SC2034" in caplog.text

    def test_suppress_rules_filters_disable_directives_to_sc2034(self):
        content = (
            "#!/usr/bin/env bash\n"
            'DATE="$(date +%Y%m%d%H%M%S)"\n'
            "if [ $? -ne 0 ]; then\n"
            "  true\n"
            "fi\n"
        )
        findings = [
            ShellCheckFinding(
                filepath="demo.sh",
                lineno=2,
                src_line='DATE="$(date +%Y%m%d%H%M%S)"',
                caret_offset=0,
                caret_len=4,
                rule="SC2034",
                message="DATE appears unused.",
            ),
            ShellCheckFinding(
                filepath="demo.sh",
                lineno=3,
                src_line="if [ $? -ne 0 ]; then",
                caret_offset=5,
                caret_len=2,
                rule="SC2181",
                message="Check exit code directly.",
            ),
        ]

        disable_edits = build_disable_edits_for_findings(
            findings, {"demo.sh": content}, suppress_rules=["SC2034"]
        )
        updated, count = apply_edits_to_content(content, disable_edits["demo.sh"])

        assert count == 1
        assert '# shellcheck disable=SC2034\nDATE="$(date +%Y%m%d%H%M%S)"' in updated
        assert "# shellcheck disable=SC2181" not in updated
