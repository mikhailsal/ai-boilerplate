"""R04.7 and R06.9 in a PHP component: declared layers and a loopback-only suite.

The helper resolves class names through the component's PSR-4 prefixes, so an
import between declared modules is an edge; the unit suite runs in a network
namespace where loopback is the only interface (decision 0013).
"""

from dataclasses import replace
from pathlib import Path

from quality.process.isolation import unavailable
from quality.testkit.scratch import Project, create_project, output, php, rules_of

# Two layers: the user interface may import the core, never the reverse.
ARCHITECTURE = """
[components.architecture]
layers = ["ui", "core"]

[[components.architecture.modules]]
name = "ui"
paths = ["src/Ui/**"]

[[components.architecture.modules]]
name = "core"
paths = ["src/Core/**"]
"""
MATH = """\
<?php

declare(strict_types=1);

namespace App\\Core;

final class Math
{
    public static function triple(int $value): int
    {
        return $value * 3;
    }
}
"""
LABEL = """\
<?php

declare(strict_types=1);

namespace App\\Ui;

use App\\Core\\Math;

final class Label
{
    public static function of(int $value): string
    {
        return 'x' . Math::triple($value);
    }
}
"""
LABEL_TEST = """\
<?php

declare(strict_types=1);

namespace App\\Tests;

use App\\Ui\\Label;
use PHPUnit\\Framework\\TestCase;

final class LabelTest extends TestCase
{
    public function testLabel(): void
    {
        self::assertSame('x6', Label::of(2));
    }
}
"""
PREFIX = """\
<?php

declare(strict_types=1);

namespace App\\Ui;

final class Prefix
{
    public const TEXT = 'x';
}
"""
UPWARD = MATH.replace("final class", "use App\\Ui\\Prefix;\n\nfinal class").replace(
    "return $value * 3;", "return strlen(Prefix::TEXT) * $value * 3;"
)
# Loopback answers inside the unit suite's namespace; any other address is
# unreachable (errno 101) rather than merely slow.
NETWORK_TEST = """\
<?php

declare(strict_types=1);

namespace App\\Tests;

use PHPUnit\\Framework\\TestCase;

final class NetworkTest extends TestCase
{
    public function testLoopbackAnswers(): void
    {
        $server = stream_socket_server('tcp://127.0.0.1:0');
        self::assertNotFalse($server);
        $address = stream_socket_get_name($server, false);
        self::assertNotFalse($address);
        $client = stream_socket_client('tcp://' . $address, timeout: 5);
        self::assertNotFalse($client);
        fclose($client);
        fclose($server);
    }

    public function testOtherAddressesAreUnreachable(): void
    {
        $client = @stream_socket_client('tcp://192.0.2.1:9', $errno, $message, 5);
        self::assertFalse($client, 'connected to 192.0.2.1');
        self::assertSame(101, $errno);
    }
}
"""


def test_imports_between_declared_modules_follow_the_layers(tmp_path: Path) -> None:
    spec = replace(php("shop"), extra=ARCHITECTURE)
    project = create_project(tmp_path / "project", spec)
    assert project.quality("bootstrap").returncode == 0
    project.write("shop/src/Core/Math.php", MATH)
    project.write("shop/src/Ui/Label.php", LABEL)
    project.write("shop/tests/LabelTest.php", LABEL_TEST)
    accepted = project.commit("the interface imports the core")
    assert accepted.returncode == 0, output(accepted)
    project.write("shop/src/Ui/Prefix.php", PREFIX)
    project.write("shop/src/Core/Math.php", UPWARD)
    rejected = project.commit("the core imports the interface")
    assert rejected.returncode != 0
    assert "architecture.forbidden-dependency" in rules_of(rejected), output(rejected)
    assert "shop/src/Core/Math.php" in output(rejected)


def test_unit_tests_reach_loopback_and_nothing_else(shop: Project) -> None:
    shop.write("shop/tests/NetworkTest.php", NETWORK_TEST)
    result = shop.commit("test the network")
    reason = unavailable()
    if reason is None:
        assert result.returncode == 0, output(result)
        assert "unit coverage of shop: line 100.00%" in output(result)
    else:
        assert result.returncode != 0
        assert "tests.network" in rules_of(result), output(result)
        assert reason in output(result)
