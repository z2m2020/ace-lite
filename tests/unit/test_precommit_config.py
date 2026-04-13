def test_precommit_config_registers_commit_time_validation_hook() -> None:
    from pathlib import Path

    import yaml

    repo_root = Path(__file__).resolve().parents[2]
    config_path = repo_root / ".pre-commit-config.yaml"
    payload = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    repos = payload.get("repos")
    assert isinstance(repos, list)

    hooks = []
    for repo in repos:
        if isinstance(repo, dict):
            repo_hooks = repo.get("hooks")
            if isinstance(repo_hooks, list):
                hooks.extend(item for item in repo_hooks if isinstance(item, dict))

    hook = next(item for item in hooks if item.get("id") == "ace-lite-precommit-validation")
    assert hook["entry"] == "python scripts/run_precommit_validation.py --staged"
    assert hook["pass_filenames"] is False
    assert hook["stages"] == ["pre-commit"]
