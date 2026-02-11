"""Tests for server entry point and async server."""

from unittest.mock import patch


class TestAsyncServer:
    def test_mcp_exists(self):
        from chuk_mcp_geocoder.async_server import mcp

        assert mcp is not None

    def test_geocoder_exists(self):
        from chuk_mcp_geocoder.async_server import geocoder

        assert geocoder is not None

    def test_mcp_has_tools(self):
        from chuk_mcp_geocoder.async_server import mcp

        tools = mcp.get_tools()
        assert len(tools) > 0


class TestServerModule:
    def test_mcp_same_as_async_server(self):
        from chuk_mcp_geocoder.async_server import mcp as async_mcp
        from chuk_mcp_geocoder.server import mcp as server_mcp

        assert async_mcp is server_mcp

    def test_main_exists(self):
        from chuk_mcp_geocoder.server import main

        assert callable(main)

    @patch("chuk_mcp_geocoder.server.mcp")
    def test_main_stdio_mode(self, mock_mcp):
        from chuk_mcp_geocoder.server import main

        with patch("sys.argv", ["chuk-mcp-geocoder", "stdio"]):
            main()
        mock_mcp.run.assert_called_once_with(stdio=True)

    @patch("chuk_mcp_geocoder.server.mcp")
    def test_main_http_mode(self, mock_mcp):
        from chuk_mcp_geocoder.server import main

        with patch("sys.argv", ["chuk-mcp-geocoder", "http", "--port", "9999"]):
            main()
        mock_mcp.run.assert_called_once_with(host="localhost", port=9999, stdio=False)

    @patch("chuk_mcp_geocoder.server.mcp")
    def test_main_auto_detect_stdio_env(self, mock_mcp):
        from chuk_mcp_geocoder.server import main

        with (
            patch("sys.argv", ["chuk-mcp-geocoder"]),
            patch.dict("os.environ", {"MCP_STDIO": "1"}),
        ):
            main()
        mock_mcp.run.assert_called_once_with(stdio=True)

    @patch("chuk_mcp_geocoder.server.mcp")
    def test_main_auto_detect_not_tty(self, mock_mcp):
        from chuk_mcp_geocoder.server import main

        with (
            patch("sys.argv", ["chuk-mcp-geocoder"]),
            patch("sys.stdin") as mock_stdin,
            patch.dict("os.environ", {}, clear=True),
        ):
            mock_stdin.isatty.return_value = False
            main()
        mock_mcp.run.assert_called_once_with(stdio=True)

    @patch("chuk_mcp_geocoder.server.mcp")
    def test_main_default_http(self, mock_mcp):
        from chuk_mcp_geocoder.server import main

        with (
            patch("sys.argv", ["chuk-mcp-geocoder"]),
            patch("sys.stdin") as mock_stdin,
            patch.dict("os.environ", {}, clear=True),
        ):
            mock_stdin.isatty.return_value = True
            main()
        mock_mcp.run.assert_called_once_with(host="localhost", port=8010, stdio=False)
