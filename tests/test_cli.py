from pathlib import Path
from click.testing import CliRunner
import pytest
from pykoplenti.cli import cli, SessionCache
import os
from conftest import only_smoketest


@pytest.fixture
def credentials(tmp_path: Path, smoketest_config: tuple[str, int, str]):
    _, _, password = smoketest_config
    credentials_path = tmp_path / "credentials"
    credentials_path.write_text(f"password={password}")
    return credentials_path


@pytest.fixture
def dummy_credentials(tmp_path: Path):
    credentials_path = tmp_path / "credentials"
    credentials_path.write_text("password=dummy")
    return credentials_path


@pytest.fixture
def session_cache(smoketest_config: tuple[str, int, str]):
    host, _, _ = smoketest_config
    session_cache = SessionCache(host, "user")
    session_cache.remove()
    yield session_cache
    session_cache.remove()


class TestInvalidGlobalOptions:
    """Test invalid global options."""

    def test_crendentials_and_password(self, dummy_credentials: Path):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "--credentials",
                str(dummy_credentials),
                "--password",
                "topsecret",
                "all-processdata",
            ],
        )
        assert result.exit_code == 2
        assert "password cannot be used with credentials" in result.output

    @pytest.mark.filterwarnings(
        "ignore:--password-file is deprecated. Use --credentials instead."
    )
    def test_crendentials_and_password_file(self, dummy_credentials: Path):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "--credentials",
                str(dummy_credentials),
                "--password-file",
                str(dummy_credentials),
                "all-processdata",
            ],
        )

        assert result.exit_code == 2
        assert "password-file cannot be used with credentials" in result.output

    def test_crendentials_and_service_code(
        self, dummy_credentials: Path, tmp_path: Path
    ):
        # As --password-file has a default value, this ensures
        # that no default password-file exists.
        os.chdir(tmp_path)

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "--credentials",
                str(dummy_credentials),
                "--service-code",
                "topsecret",
                "all-processdata",
            ],
        )
        assert result.exit_code == 2
        assert "service_code cannot be used with credentials" in result.output


@only_smoketest
def test_read_process_data(
    credentials: Path,
    session_cache: SessionCache,
    smoketest_config: tuple[str, int, str],
):
    # As --password-file has a default value, this ensures
    # that no default password-file exists.
    os.chdir(credentials.parent)

    host, port, _ = smoketest_config

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "--host",
            host,
            "--port",
            str(port),
            "--credentials",
            str(credentials),
            "all-processdata",
        ],
    )
    assert result.exit_code == 0
    # check any data which is most likely present on most inverter
    assert "devices:local/Inverter:State" in result.stdout.splitlines()
    assert session_cache.read_session_id() is not None


@only_smoketest
def test_read_settings_data(
    credentials: Path,
    session_cache: SessionCache,
    smoketest_config: tuple[str, int, str],
):
    # As --password-file has a default value, this ensures
    # that no default password-file exists.
    os.chdir(credentials.parent)

    host, port, _ = smoketest_config

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "--host",
            host,
            "--port",
            str(port),
            "--credentials",
            str(credentials),
            "all-settings",
        ],
    )
    assert result.exit_code == 0
    # check any data which is most likely present on most inverter
    assert "devices:local/Branding:ProductName1" in result.stdout.splitlines()
    assert session_cache.read_session_id() is not None
