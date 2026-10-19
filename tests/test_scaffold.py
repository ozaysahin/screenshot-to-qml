import scaffold


def test_scaffold_creates_modules(tmp_path):
    out = tmp_path / "app"
    assert scaffold.main([str(out), "--name", "Demo App", "--layout", "canvas"]) == 0
    for rel in ("main.py", "qml/App/qmldir", "qml/App/Main.qml", "qml/App/Style/Theme.qml",
                "qml/App/Style/qmldir", "qml/App/Controls/qmldir", "requirements.txt", "README.md"):
        assert (out / rel).exists(), rel
    assert "fitScale" in (out / "qml/App/Main.qml").read_text()
    assert "{{" not in (out / "main.py").read_text()


def test_scaffold_refuses_non_empty(tmp_path):
    (tmp_path / "x").mkdir()
    (tmp_path / "x" / "f").write_text("1")
    assert scaffold.main([str(tmp_path / "x"), "--name", "A"]) == 2
