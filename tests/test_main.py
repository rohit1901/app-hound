# TODO: Write tests for main module
# import pytest
# from unittest import mock
# from pathlib import Path
# import sys

# import app_hound.main as main


# @pytest.fixture
# def app_config():
#     return [
#         {"name": "App1", "installation_path": None, "additional_locations": ["loc1"]},
#         {
#             "name": "App2",
#             "installation_path": "installer.sh",
#             "additional_locations": [],
#         },
#     ]


# @mock.patch("main.argparse.ArgumentParser.parse_args")
# def test_parse_arguments_defaults(mock_parse_args):
#     mock_parse_args.return_value = mock.Mock(input="abc", output="xyz")
#     args = main.parse_arguments()
#     assert hasattr(args, "input")
#     assert hasattr(args, "output")


# def test_ensure_directories_exist(tmp_path):
#     # Directory should not exist initially
#     dir_path = tmp_path / "new_audit"
#     main.ensure_directories_exist(dir_path)
#     assert dir_path.exists()
#     assert dir_path.is_dir()


# def test_validate_config_path(tmp_path):
#     config = tmp_path / "apps_config.json"
#     config.touch()
#     # Should not raise
#     main.validate_config_path(config)
#     # Should exit if missing
#     missing = tmp_path / "nope.json"
#     with pytest.raises(SystemExit):
#         main.validate_config_path(missing)


# @mock.patch("main.run_installer")
# @mock.patch("main.gather_app_entries")
# def test_process_app_entries_with_installer(mock_gather, mock_run_inst, app_config):
#     # App with installer
#     app = app_config[1]
#     mock_gather.return_value = ["entry"]
#     result = main.process_app_entries(app)
#     mock_run_inst.assert_called_once_with(app["installation_path"])
#     mock_gather.assert_called_once_with(app["name"], app["additional_locations"])
#     assert result == ["entry"]


# @mock.patch("main.run_installer")
# @mock.patch("main.gather_app_entries")
# def test_process_app_entries_without_installer(mock_gather, mock_run_inst, app_config):
#     # App without installer
#     app = app_config[0]
#     mock_gather.return_value = ["something"]
#     result = main.process_app_entries(app)
#     mock_run_inst.assert_not_called()
#     mock_gather.assert_called_once_with(app["name"], app["additional_locations"])
#     assert result == ["something"]


# def test_collect_audit_results(monkeypatch, app_config):
#     # Patch process_app_entries to return static items
#     monkeypatch.setattr(main, "process_app_entries", lambda app: [app["name"]])
#     results = main.collect_audit_results(app_config)
#     assert "App1" in results and "App2" in results


# def test_write_audit_csv(tmp_path):
#     results = [["app", "base", "folder", "file"]]
#     output_file = tmp_path / "report.csv"
#     main.write_audit_csv(results, output_file)
#     data = output_file.read_text().splitlines()
#     assert data[0] == "App Name,Base Path,Folder,File name"
#     assert "app,base,folder,file" in data[1]


# @mock.patch("main.write_audit_csv")
# @mock.patch("main.collect_audit_results")
# @mock.patch("main.load_apps_from_json")
# @mock.patch("main.validate_config_path")
# @mock.patch("main.ensure_directories_exist")
# @mock.patch("main.parse_arguments")
# def test_main_flow(
#     mock_parse, mock_ensure, mock_validate, mock_load, mock_collect, mock_write
# ):
#     # Test that all steps are called as expected
#     mock_parse.return_value = mock.Mock(input=".", output="audit.csv")
#     mock_load.return_value = []
#     mock_collect.return_value = []
#     main.main()
#     mock_ensure.assert_called()
#     mock_validate.assert_called()
#     mock_load.assert_called()
#     mock_collect.assert_called()
#     mock_write.assert_called()
