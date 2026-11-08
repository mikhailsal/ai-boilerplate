"""Materialize the serial PHPUnit RL00b/c corpus; experimental only."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

from defusedxml import ElementTree

from tests.acceptance.rl00bc.rl00bc_errors import invalid

SMALL = ("ordinary", "setup", "teardown", "child")
LARGE = (
    *SMALL,
    "allocation",
    "retained",
    "parameterCheap",
    "parameterHeavy",
    "slow",
    "justified",
    "cheap01",
    "cheap02",
    "cheap03",
    "cheap04",
    "cheap05",
    "cheap06",
)
PHP = r"""<?php
use PHPUnit\Framework\TestCase;
use PHPUnit\Framework\Attributes\DataProvider;
final class SubjectTest extends TestCase {
    private static string $retained = '';
    private string $value = '';
    private function label(): string {
        $name = substr($this->name(), 4);
        return $name === 'parameter' ? (string)$this->dataName() : $name;
    }
    private function active(string $label): bool {
        return getenv('RL00_MODE') === 'correctness' && getenv('RL00_TARGET') === $label;
    }
    private static function event(string $label, string $phase): void {
        if (getenv('RL00_INSTRUMENT') !== '1') { return; }
        $stamp = hrtime(true);
        $file = getenv('RL00_EVENT_DIR') . '/' . getmypid() . '-' . $stamp . '.json';
        file_put_contents($file, json_encode([
            'label' => $label, 'variant' => $label, 'phase' => $phase,
            'pid' => getmypid(), 'monotonic_ns' => $stamp,
        ], JSON_THROW_ON_ERROR));
    }
    private static function mib(string $name, int $minimum, int $maximum): int {
        $raw = getenv($name);
        if ($raw === false || !preg_match('/^(0|[1-9][0-9]*)$/D', $raw) || strlen($raw) > 4) {
            throw new RuntimeException('invalid allocation input');
        }
        $value = (int)$raw;
        if ($value < $minimum || $value > $maximum) {
            throw new RuntimeException('allocation outside experiment bound');
        }
        return $value;
    }
    private function allocate(string $label): string {
        if (!$this->active($label)) { return str_repeat('x', 4096); }
        $mib = self::mib('RL00_ALLOC_MIB', 1, 1536);
        return str_repeat('x', $mib * 1048576);
    }
    public static function setUpBeforeClass(): void {
        self::event('retained', 'class-setup-start');
        $shared = self::mib('RL00_SHARED_MIB', 0, 128);
        if (getenv('RL00_MODE') === 'correctness' && getenv('RL00_TARGET') === 'retained') {
            $mib = self::mib('RL00_ALLOC_MIB', 1, 1536);
            self::$retained = str_repeat('x', $mib * 1048576);
        } else { self::$retained = str_repeat('x', $shared * 1048576); }
        self::event('retained', 'class-setup-end');
    }
    public static function tearDownAfterClass(): void {
        self::event('retained', 'class-teardown-start');
        self::$retained = '';
        self::event('retained', 'class-teardown-end');
    }
    protected function setUp(): void {
        $label = $this->label(); self::event($label, 'setup-start');
        $this->value = $this->allocate($label === 'setup' ? $label : 'none');
        self::event($label, 'setup-end');
    }
    protected function tearDown(): void {
        $label = $this->label(); self::event($label, 'teardown-start');
        if ($label === 'teardown') { $this->value = $this->allocate($label); }
        self::event($label, 'teardown-end');
    }
    private function subject(string $label): void {
        self::event($label, 'call-start');
        if (in_array($label, ['allocation', 'parameterHeavy', 'justified'], true)) {
            $this->value = $this->allocate($label);
        }
        if ($label === 'child' && $this->active($label)) {
            $mib = self::mib('RL00_ALLOC_MIB', 1, 1536);
            $spec = [1 => ['pipe', 'w'], 2 => ['pipe', 'w']];
            $proc = proc_open([getenv('RL00_CHILD_PYTHON'), '-c',
                'import sys; x=bytearray(int(sys.argv[1])*1048576); print(len(x))', (string)$mib
            ], $spec, $pipes);
            if (!is_resource($proc)) { throw new RuntimeException('child failed to start'); }
            stream_get_contents($pipes[1]); fclose($pipes[1]);
            stream_get_contents($pipes[2]); fclose($pipes[2]);
            self::assertSame(0, proc_close($proc));
        }
        if ($label === 'slow' && $this->active($label)) {
            $delay = (float)getenv('RL00_SLOW_SECONDS');
            if ($delay < 0 || $delay > 30) {
                throw new RuntimeException('delay outside experiment bound');
            }
            usleep((int)($delay * 1000000));
        }
        self::assertSame(1, rl00_value()); self::assertNotSame('', $this->value);
        self::event($label, 'call-end');
    }
    public static function parameters(): array {
        return ['parameterCheap' => ['parameterCheap'], 'parameterHeavy' => ['parameterHeavy']];
    }
    #[DataProvider('parameters')]
    public function testparameter(string $label): void { $this->subject($label); }
__METHODS__
}
"""


def _path(name: str) -> Path:
    path = Path(os.environ[name])
    if not path.is_absolute() or not path.is_file():
        invalid(f"{name} must name an absolute bootstrapped file")
    return path


def prepare(root: Path, repo: Path, profile: str) -> None:
    """Write the fixture; the caller supplies the bootstrapped tool paths."""
    if profile != "php":
        invalid("expected php profile")
    for name in ("RL00_PHP", "RL00_PHPUNIT", "RL00_PHP_AUTOLOAD"):
        _path(name)
    root.mkdir(parents=True, exist_ok=True)
    names = LARGE if os.environ.get("RL00_SIZE") == "large" else SMALL
    methods = "\n".join(
        f"    public function test{name}(): void {{ $this->subject('{name}'); }}"
        for name in names
        if not name.startswith("parameter")
    )
    if len(names) == len(SMALL):
        # Small corpus has exactly four native cases; omit the provider method.
        start = PHP.index("    public static function parameters(): array {")
        end = PHP.index("__METHODS__", start)
        fixture = PHP[:start] + PHP[end:]
    else:
        fixture = PHP
    (root / "SubjectTest.php").write_text(fixture.replace("__METHODS__", methods), encoding="utf-8")
    (root / "subject.php").write_text(
        "<?php\nfunction rl00_value(): int { return 1; }\n", encoding="utf-8"
    )
    (root / "scenarios.toml").write_text(
        'schema_version = 1\ncomponent = "rl00bc"\n[[scenarios]]\n'
        'id = "subject-value"\nsummary = "The subject produces its expected value"\n'
        'capability = "library"\nlevel = "unit"\nstage = "commit"\n'
        'tests = ["SubjectTest::testordinary"]\n',
        encoding="utf-8",
    )


def _validate_command(profile: str, workers: int, selected: str | None) -> None:
    if profile != "php" or workers != 1:
        invalid("PHP fixture supports only one worker")
    if selected is not None and selected not in LARGE:
        invalid("invalid selected identity")


def _config(root: Path, output: Path, coverage: bool) -> Path:
    autoload = str(_path("RL00_PHP_AUTOLOAD")).replace("\\", "\\\\").replace("'", "\\'")
    bootstrap = output / "bootstrap.php"
    bootstrap.write_text(
        f"<?php\nrequire_once '{autoload}';\nrequire_once '{root / 'subject.php'}';\n",
        encoding="utf-8",
    )
    source = ""
    if coverage:
        source = (
            f'<source><include><file>{escape(str(root / "subject.php"))}</file></include></source>'
            '<coverage includeUncoveredFiles="true" branchCoverage="true" '
            'disableCodeCoverageIgnore="true" ignoreDeprecatedCodeUnits="false"/>'
        )
    xml = (
        f'<?xml version="1.0"?><phpunit bootstrap={quoteattr(str(bootstrap))} '
        f'cacheDirectory={quoteattr(str(output / "cache"))} '
        'colors="false" recordTestRunHistory="false"><testsuites><testsuite name="unit">'
        f'<file>{escape(str(root / "SubjectTest.php"))}</file></testsuite></testsuites>'
        f'{source}</phpunit>'
    )
    config = output / "phpunit.xml"
    config.write_text(xml, encoding="utf-8")
    return config


def command(
    root: Path,
    repo: Path,
    output: Path,
    selected: str | None,
    *,
    profile: str,
    workers: int,
    coverage: bool,
) -> list[str]:
    """Build the adapter-style command; PHPUnit here supports serial execution only."""
    _validate_command(profile, workers, selected)
    output.mkdir(parents=True, exist_ok=True)
    (output / "selection.json").write_text(json.dumps({"selected": selected}), encoding="utf-8")
    config = _config(root, output, coverage)
    # Disabling PHP's own limit is valid only under the parent's finite cgroup.
    argv = [str(_path("RL00_PHP")), "-d", "display_errors=stderr", "-d", "memory_limit=-1"]
    if coverage and os.environ.get("RL00_XDEBUG_LOADED") != "1":
        argv += ["-d", "zend_extension=xdebug"]
    argv += [
        str(_path("RL00_PHPUNIT")),
        f"--configuration={config}",
        f"--log-junit={output / 'junit.xml'}",
        "--no-progress",
    ]
    if coverage:
        argv += [
            f"--coverage-clover={output / 'clover.xml'}",
            f"--coverage-jsonl={output / 'coverage-jsonl'}",
        ]
    if selected is not None:
        # The parser validates the exact native result after this coarse filter.
        pattern = selected if selected.startswith("parameter") else f"test{selected}"
        argv += ["--filter", pattern]
    return argv


def _variant(name: str) -> str:
    if not name.startswith("testparameter"):
        return name.removeprefix("test")
    match = re.search(r"parameter(?:Cheap|Heavy)", name)
    if match is None:
        invalid(f"unrecognized native PHPUnit data-set identity: {name}")
    return match.group(0)


def _check_identities(cases: list[dict[str, object]], selected: object) -> None:
    ids = [str(case["id"]) for case in cases]
    if not cases or len(ids) != len(set(ids)):
        invalid("native result identity mismatch")
    if selected is not None and (len(cases) != 1 or cases[0]["variant"] != selected):
        invalid("native result identity mismatch")


def results(root: Path, output: Path, *, profile: str) -> list[dict[str, object]]:
    """Parse PHPUnit identities and reject a filtered multi-match or absent case."""
    if profile != "php":
        invalid("expected php profile")
    cases: list[dict[str, object]] = []
    for case in ElementTree.parse(output / "junit.xml").iter("testcase"):
        name = case.get("name", "")
        identity = f"{case.get('classname', '')}::{name}"
        outcome = next(
            (tag for tag in ("error", "failure", "skipped") if case.find(tag) is not None), "passed"
        )
        cases.append(
            {
                "id": identity,
                "variant": _variant(name),
                "outcome": outcome,
                "coverage": str(output / "clover.xml")
                if (output / "clover.xml").is_file()
                else None,
                "coverage_jsonl": str(output / "coverage-jsonl")
                if (output / "coverage-jsonl").is_dir()
                else None,
            }
        )
    selected = json.loads((output / "selection.json").read_text(encoding="utf-8"))["selected"]
    _check_identities(cases, selected)
    return cases
