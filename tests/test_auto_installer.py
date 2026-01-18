"""Tests for auto-installer functionality."""

import zipfile
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from version_checker.utils.auto_installer import AutoInstaller, auto_install


class TestAutoInstaller:
    """Test cases for AutoInstaller class."""

    def test_init_default(self, temp_dir: Path) -> None:
        """Test AutoInstaller initialization with defaults."""
        file_path = str(temp_dir / "app.exe")
        download_url = "https://example.com/app.zip"

        installer = AutoInstaller(file_path, download_url)

        assert installer.file_path == Path(file_path)
        assert installer.download_url == download_url
        assert installer.downloads_dir == Path.home() / "Downloads"
        assert installer.downloaded_file is None
        assert installer.progress is None
        assert installer.task_id is None
        assert installer.silent is False
        assert installer.progress_callback is None
        assert installer.fresh_install is False

    def test_init_with_options(self, temp_dir: Path) -> None:
        """Test AutoInstaller initialization with custom options."""
        file_path = str(temp_dir / "app.exe")
        download_url = "https://example.com/app.zip"
        mock_progress = MagicMock()
        mock_callback = MagicMock()

        installer = AutoInstaller(
            file_path,
            download_url,
            progress=mock_progress,
            task_id="task1",
            silent=True,
            progress_callback=mock_callback,
            fresh_install=True,
        )

        assert installer.progress == mock_progress
        assert installer.task_id == "task1"
        assert installer.silent is True
        assert installer.progress_callback == mock_callback
        assert installer.fresh_install is True

    @patch("version_checker.utils.auto_installer.console")
    def test_update_status_not_silent(self, mock_console: MagicMock) -> None:
        """Test _update_status when not in silent mode."""
        installer = AutoInstaller("/path/to/app.exe", "https://example.com/app.zip")

        installer._update_status("Test message")

        mock_console.print.assert_called_once_with("Test message")

    def test_update_status_silent(self) -> None:
        """Test _update_status in silent mode."""
        installer = AutoInstaller(
            "/path/to/app.exe", "https://example.com/app.zip", silent=True
        )

        # Should not raise any exceptions
        installer._update_status("Test message")

    @patch("version_checker.utils.auto_installer.console")
    def test_update_status_with_progress(self, mock_console: MagicMock) -> None:
        """Test _update_status with progress tracking."""
        _ = mock_console  # unused but required by patch
        mock_progress = MagicMock()
        installer = AutoInstaller(
            "/path/to/app.exe",
            "https://example.com/app.zip",
            progress=mock_progress,
            task_id="task1",
        )

        installer._update_status("Test message", "Step 1/5")

        mock_progress.update.assert_called_once()

    @patch("version_checker.utils.auto_installer.psutil")
    @patch("version_checker.utils.auto_installer.console")
    def test_kill_process_success(
        self, mock_console: MagicMock, mock_psutil: MagicMock
    ) -> None:
        """Test killing process successfully."""
        _ = mock_console  # unused but required by patch
        # Mock process
        mock_proc = MagicMock()
        mock_proc.info = {"pid": 1234, "name": "OlivedPro.exe"}
        mock_psutil.process_iter.return_value = [mock_proc]

        installer = AutoInstaller("/path/to/app.exe", "https://example.com/app.zip")

        result = installer._kill_process()

        assert result is True
        mock_proc.terminate.assert_called_once()

    @patch("version_checker.utils.auto_installer.psutil")
    def test_kill_process_no_process_running(self, mock_psutil: MagicMock) -> None:
        """Test when no process is running."""
        mock_psutil.process_iter.return_value = []

        installer = AutoInstaller("/path/to/app.exe", "https://example.com/app.zip")

        result = installer._kill_process()

        assert result is True

    @patch("version_checker.utils.auto_installer.psutil")
    @patch("version_checker.utils.auto_installer.console")
    def test_kill_process_force_kill(
        self, mock_console: MagicMock, mock_psutil: MagicMock
    ) -> None:
        """Test force killing process."""
        _ = mock_console  # unused but required by patch
        # Mock process that doesn't terminate
        mock_proc = MagicMock()
        mock_proc.info = {"pid": 1234, "name": "OlivedPro.exe"}

        # First call returns the process, second call also returns it (still running)
        mock_psutil.process_iter.side_effect = [[mock_proc], [mock_proc]]

        installer = AutoInstaller("/path/to/app.exe", "https://example.com/app.zip")

        result = installer._kill_process()

        assert result is True
        mock_proc.terminate.assert_called_once()
        mock_proc.kill.assert_called_once()

    @patch("version_checker.utils.auto_installer.psutil")
    @patch("version_checker.utils.auto_installer.console")
    def test_kill_process_error(
        self, mock_console: MagicMock, mock_psutil: MagicMock
    ) -> None:
        """Test error handling in kill_process."""
        mock_psutil.process_iter.side_effect = Exception("Test error")

        installer = AutoInstaller("/path/to/app.exe", "https://example.com/app.zip")

        result = installer._kill_process()

        assert result is False
        mock_console.print.assert_called()

    @patch("version_checker.utils.auto_installer.requests")
    def test_download_success(self, mock_requests: MagicMock, temp_dir: Path) -> None:
        """Test successful download."""
        # Mock response
        mock_response = MagicMock()
        mock_response.headers = {"content-length": "1000"}
        mock_response.iter_content.return_value = [b"chunk1", b"chunk2"]
        mock_requests.get.return_value = mock_response

        installer = AutoInstaller(
            str(temp_dir / "app.exe"), "https://example.com/app.zip"
        )
        installer.downloads_dir = temp_dir

        result = installer._download()

        assert result is True
        assert installer.downloaded_file is not None
        assert installer.downloaded_file.exists()

    @patch("version_checker.utils.auto_installer.requests")
    def test_download_with_progress(
        self, mock_requests: MagicMock, temp_dir: Path
    ) -> None:
        """Test download with progress tracking."""
        mock_response = MagicMock()
        mock_response.headers = {"content-length": "1000"}
        mock_response.iter_content.return_value = [b"chunk1", b"chunk2"]
        mock_requests.get.return_value = mock_response

        mock_progress = MagicMock()
        installer = AutoInstaller(
            str(temp_dir / "app.exe"),
            "https://example.com/app.zip",
            progress=mock_progress,
        )
        installer.downloads_dir = temp_dir

        result = installer._download()

        assert result is True
        mock_progress.add_task.assert_called_once()

    @patch("version_checker.utils.auto_installer.requests")
    def test_download_with_callback(
        self, mock_requests: MagicMock, temp_dir: Path
    ) -> None:
        """Test download with progress callback."""
        mock_response = MagicMock()
        mock_response.headers = {"content-length": "1000"}
        mock_response.iter_content.return_value = [b"chunk1", b"chunk2"]
        mock_requests.get.return_value = mock_response

        mock_callback = MagicMock()
        installer = AutoInstaller(
            str(temp_dir / "app.exe"),
            "https://example.com/app.zip",
            progress_callback=mock_callback,
            silent=True,
        )
        installer.downloads_dir = temp_dir

        result = installer._download()

        assert result is True
        assert mock_callback.called

    @patch("version_checker.utils.auto_installer.requests")
    @patch("version_checker.utils.auto_installer.console")
    def test_download_request_error(
        self, mock_console: MagicMock, mock_requests: MagicMock, temp_dir: Path
    ) -> None:
        """Test download with request error."""
        # Import the actual exception class
        import requests as real_requests

        mock_requests.get.side_effect = real_requests.exceptions.RequestException(
            "Network error"
        )
        mock_requests.exceptions = real_requests.exceptions

        installer = AutoInstaller(
            str(temp_dir / "app.exe"), "https://example.com/app.zip"
        )
        installer.downloads_dir = temp_dir

        result = installer._download()

        assert result is False
        mock_console.print.assert_called()

    def test_extract_and_overwrite_success(self, temp_dir: Path) -> None:
        """Test successful extraction and installation."""
        # Create a mock zip file with an exe
        zip_path = temp_dir / "app.zip"
        exe_content = b"Mock executable content"

        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("app.exe", exe_content)

        target_path = temp_dir / "installed" / "app.exe"
        installer = AutoInstaller(str(target_path), "https://example.com/app.zip")
        installer.downloaded_file = zip_path
        installer.downloads_dir = temp_dir

        result = installer._extract_and_overwrite()

        assert result is True
        assert target_path.exists()

    def test_extract_and_overwrite_with_backup(self, temp_dir: Path) -> None:
        """Test extraction with backup of existing file."""
        # Create existing exe
        target_path = temp_dir / "app.exe"
        target_path.write_bytes(b"Old version")

        # Create zip with new version
        zip_path = temp_dir / "app.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("app.exe", b"New version")

        installer = AutoInstaller(str(target_path), "https://example.com/app.zip")
        installer.downloaded_file = zip_path
        installer.downloads_dir = temp_dir

        result = installer._extract_and_overwrite()

        assert result is True
        assert target_path.exists()
        backup_path = target_path.with_suffix(".exe.bak")
        assert backup_path.exists()

    def test_extract_and_overwrite_no_exe_found(self, temp_dir: Path) -> None:
        """Test extraction when no exe is found in zip."""
        # Create zip without exe
        zip_path = temp_dir / "app.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("readme.txt", b"No exe here")

        installer = AutoInstaller(
            str(temp_dir / "app.exe"), "https://example.com/app.zip"
        )
        installer.downloaded_file = zip_path
        installer.downloads_dir = temp_dir

        result = installer._extract_and_overwrite()

        assert result is False

    def test_extract_and_overwrite_bad_zip(self, temp_dir: Path) -> None:
        """Test extraction with corrupted zip file."""
        # Create invalid zip
        zip_path = temp_dir / "app.zip"
        zip_path.write_bytes(b"Not a valid zip file")

        installer = AutoInstaller(
            str(temp_dir / "app.exe"), "https://example.com/app.zip"
        )
        installer.downloaded_file = zip_path
        installer.downloads_dir = temp_dir

        result = installer._extract_and_overwrite()

        assert result is False

    def test_extract_and_overwrite_no_downloaded_file(self, temp_dir: Path) -> None:
        """Test extraction when downloaded file doesn't exist."""
        installer = AutoInstaller(
            str(temp_dir / "app.exe"), "https://example.com/app.zip"
        )
        installer.downloaded_file = temp_dir / "nonexistent.zip"
        installer.downloads_dir = temp_dir

        result = installer._extract_and_overwrite()

        assert result is False

    @patch("version_checker.utils.auto_installer.subprocess")
    def test_start_process_windows(
        self, mock_subprocess: MagicMock, temp_dir: Path
    ) -> None:
        """Test starting process on Windows."""
        exe_path = temp_dir / "app.exe"
        exe_path.write_bytes(b"Mock exe")

        with patch("version_checker.utils.auto_installer.sys.platform", "win32"):
            installer = AutoInstaller(str(exe_path), "https://example.com/app.zip")

            result = installer._start_process()

            assert result is True
            mock_subprocess.Popen.assert_called_once()
            call_args: Any = mock_subprocess.Popen.call_args
            # Check that creationflags parameter exists and is set
            assert "creationflags" in call_args[1]
            # The actual value will be the OR'd flags
            assert call_args[1]["creationflags"] is not None

    @patch("version_checker.utils.auto_installer.subprocess")
    def test_start_process_unix(
        self, mock_subprocess: MagicMock, temp_dir: Path
    ) -> None:
        """Test starting process on Unix-like systems."""
        exe_path = temp_dir / "app.exe"
        exe_path.write_bytes(b"Mock exe")

        with patch("version_checker.utils.auto_installer.sys.platform", "linux"):
            installer = AutoInstaller(str(exe_path), "https://example.com/app.zip")

            result = installer._start_process()

            assert result is True
            mock_subprocess.Popen.assert_called_once()
            call_args: Any = mock_subprocess.Popen.call_args
            assert call_args[1]["start_new_session"] is True

    @patch("version_checker.utils.auto_installer.subprocess")
    @patch("version_checker.utils.auto_installer.console")
    def test_start_process_file_not_found(
        self, mock_console: MagicMock, mock_subprocess: MagicMock, temp_dir: Path
    ) -> None:
        """Test starting process when file doesn't exist."""
        _ = mock_subprocess  # unused but required by patch
        installer = AutoInstaller(
            str(temp_dir / "nonexistent.exe"), "https://example.com/app.zip"
        )

        result = installer._start_process()

        assert result is False
        mock_console.print.assert_called()

    @patch("version_checker.utils.auto_installer.subprocess")
    @patch("version_checker.utils.auto_installer.console")
    def test_start_process_error(
        self, mock_console: MagicMock, mock_subprocess: MagicMock, temp_dir: Path
    ) -> None:
        """Test error handling in start_process."""
        exe_path = temp_dir / "app.exe"
        exe_path.write_bytes(b"Mock exe")

        mock_subprocess.Popen.side_effect = Exception("Test error")

        installer = AutoInstaller(str(exe_path), "https://example.com/app.zip")

        result = installer._start_process()

        assert result is False
        mock_console.print.assert_called()

    def test_cleanup_success(self, temp_dir: Path) -> None:
        """Test successful cleanup."""
        zip_path = temp_dir / "app.zip"
        zip_path.write_bytes(b"Mock zip")

        installer = AutoInstaller(
            str(temp_dir / "app.exe"), "https://example.com/app.zip"
        )
        installer.downloaded_file = zip_path

        installer._cleanup()

        assert not zip_path.exists()

    def test_cleanup_no_file(self, temp_dir: Path) -> None:
        """Test cleanup when no file to clean."""
        installer = AutoInstaller(
            str(temp_dir / "app.exe"), "https://example.com/app.zip"
        )
        installer.downloaded_file = None

        # Should not raise exception
        installer._cleanup()

    @patch("version_checker.utils.auto_installer.console")
    def test_cleanup_error(self, mock_console: MagicMock, temp_dir: Path) -> None:
        """Test cleanup error handling."""
        _ = mock_console  # unused but may be called on error
        installer = AutoInstaller(
            str(temp_dir / "app.exe"), "https://example.com/app.zip"
        )
        installer.downloaded_file = temp_dir / "nonexistent.zip"

        # Should handle error gracefully
        installer._cleanup()
        # May or may not print depending on implementation

    def test_install_full_process(self, temp_dir: Path) -> None:
        """Test full installation process."""
        exe_path = temp_dir / "app.exe"
        zip_path = temp_dir / "app.zip"

        # Create zip with exe
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("app.exe", b"New version")

        installer = AutoInstaller(str(exe_path), "https://example.com/app.zip")
        installer.downloads_dir = temp_dir
        installer.fresh_install = True  # Skip kill process

        with patch.object(installer, "_download", return_value=True):
            with patch.object(installer, "_extract_and_overwrite", return_value=True):
                with patch.object(installer, "_start_process", return_value=True):
                    installer.downloaded_file = zip_path

                    result = installer.install()

                    assert result is True

    def test_install_download_fails(self, temp_dir: Path) -> None:
        """Test installation when download fails."""
        installer = AutoInstaller(
            str(temp_dir / "app.exe"), "https://example.com/app.zip"
        )
        installer.fresh_install = True

        with patch.object(installer, "_download", return_value=False):
            result = installer.install()

            assert result is False

    def test_install_extract_fails(self, temp_dir: Path) -> None:
        """Test installation when extraction fails."""
        installer = AutoInstaller(
            str(temp_dir / "app.exe"), "https://example.com/app.zip"
        )
        installer.fresh_install = True

        with patch.object(installer, "_download", return_value=True):
            with patch.object(installer, "_extract_and_overwrite", return_value=False):
                result = installer.install()

                assert result is False

    def test_install_start_process_fails(self, temp_dir: Path) -> None:
        """Test installation when starting process fails."""
        installer = AutoInstaller(
            str(temp_dir / "app.exe"), "https://example.com/app.zip"
        )
        installer.fresh_install = True

        with patch.object(installer, "_download", return_value=True):
            with patch.object(installer, "_extract_and_overwrite", return_value=True):
                with patch.object(installer, "_start_process", return_value=False):
                    result = installer.install()

                    assert result is False

    def test_install_with_kill_process(self, temp_dir: Path) -> None:
        """Test installation with kill process step."""
        installer = AutoInstaller(
            str(temp_dir / "app.exe"), "https://example.com/app.zip"
        )
        installer.fresh_install = False  # Don't skip kill process

        with patch.object(installer, "_kill_process", return_value=True):
            with patch.object(installer, "_download", return_value=True):
                with patch.object(
                    installer, "_extract_and_overwrite", return_value=True
                ):
                    with patch.object(installer, "_start_process", return_value=True):
                        result = installer.install()

                        assert result is True

    def test_install_kill_process_fails(self, temp_dir: Path) -> None:
        """Test installation when kill process fails."""
        installer = AutoInstaller(
            str(temp_dir / "app.exe"), "https://example.com/app.zip"
        )
        installer.fresh_install = False

        with patch.object(installer, "_kill_process", return_value=False):
            result = installer.install()

            assert result is False

    @patch("version_checker.utils.auto_installer.console")
    def test_install_exception(self, mock_console: MagicMock, temp_dir: Path) -> None:
        """Test installation with unexpected exception."""
        installer = AutoInstaller(
            str(temp_dir / "app.exe"), "https://example.com/app.zip"
        )
        installer.fresh_install = True

        with patch.object(installer, "_download", side_effect=Exception("Test error")):
            result = installer.install()

            assert result is False
            mock_console.print.assert_called()


class TestAutoInstallFunction:
    """Test cases for auto_install convenience function."""

    def test_auto_install_success(self, temp_dir: Path) -> None:
        """Test auto_install function success."""
        with patch("version_checker.utils.auto_installer.AutoInstaller") as mock_class:
            mock_installer = MagicMock()
            mock_class.return_value = mock_installer
            mock_installer.install.return_value = True

            result = auto_install(
                str(temp_dir / "app.exe"), "https://example.com/app.zip"
            )

            assert result is True
            mock_class.assert_called_once_with(
                str(temp_dir / "app.exe"), "https://example.com/app.zip"
            )
            mock_installer.install.assert_called_once()

    def test_auto_install_failure(self, temp_dir: Path) -> None:
        """Test auto_install function failure."""
        with patch("version_checker.utils.auto_installer.AutoInstaller") as mock_class:
            mock_installer = MagicMock()
            mock_class.return_value = mock_installer
            mock_installer.install.return_value = False

            result = auto_install(
                str(temp_dir / "app.exe"), "https://example.com/app.zip"
            )

            assert result is False
