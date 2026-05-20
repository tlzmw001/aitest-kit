# PyPI Trusted Publishing 发布指南

本文说明 `aitest-kit` 如何通过 GitHub Actions + PyPI Trusted Publishing 发布，不再在本机或 GitHub Secrets 中保存长期 PyPI token。

## 为什么使用 Trusted Publishing

Trusted Publishing 使用 GitHub Actions 的 OIDC 身份向 PyPI 换取短期发布凭据。优点：

- 不需要本机 `.pypirc`。
- 不需要在 GitHub Secrets 保存 PyPI token。
- 发布动作和 Git tag、workflow run 绑定，可审计。
- 减少长期 token 泄露风险。

## PyPI 侧配置

在 PyPI 项目 `aitest-kit` 页面中添加 Trusted Publisher。

配置项：

| 字段 | 值 |
|---|---|
| Owner / organization | `tlzmw001` |
| Repository name | `aitest-kit` |
| Workflow name | `publish.yml` |
| Environment name | `pypi` |

说明：

- Workflow 文件路径是 `.github/workflows/publish.yml`，PyPI 表单里通常只填文件名 `publish.yml`。
- Environment name 必须和 workflow 中的 `environment.name` 一致，即 `pypi`。
- 配好以后，不需要在 workflow 里写 `username`、`password` 或 API token。

## GitHub 侧配置

仓库已经包含发布 workflow：

```text
.github/workflows/publish.yml
```

该 workflow 只在 tag push 时触发：

```text
v*
```

发布 job 使用：

```yaml
permissions:
  id-token: write
```

并通过：

```yaml
uses: pypa/gh-action-pypi-publish@release/v1
```

发布到正式 PyPI。

## 标准发布流程

1. 更新版本号和 changelog。

   ```text
   pyproject.toml
   CHANGELOG.md
   ```

2. 本地验证。

   ```bash
   python3 -m compileall aitest_kit
   python3 -m pytest tests -q
   python3 -m aitest_kit.cli codegen --all --validate-profile
   python3 -m aitest_kit.cli codegen --all --check
   python3 -m pytest test_workspace/tests/generated --collect-only -q
   ```

3. 构建并检查发布产物。

   ```bash
   rm -rf build dist aitest_kit.egg-info
   python3 -m build
   python3 -m twine check dist/*
   ```

4. 提交并推送 `main`。

   ```bash
   git add pyproject.toml CHANGELOG.md
   git commit -m "release: vX.Y.Z"
   git push origin main
   ```

5. 创建并推送 tag。

   ```bash
   git tag vX.Y.Z
   git push origin vX.Y.Z
   ```

6. 到 GitHub Actions 查看 `Publish` workflow。

7. 发布成功后复验。

   ```bash
   python3 -m venv /private/tmp/aitest_pypi_install_verify
   /private/tmp/aitest_pypi_install_verify/bin/python -m pip install --no-cache-dir aitest-kit==X.Y.Z
   /private/tmp/aitest_pypi_install_verify/bin/aitest --help
   ```

## 注意事项

- PyPI 同一版本号不能覆盖。tag 触发发布后，如果包有问题，必须发新版本。
- 不要在 workflow、README、issue、commit 或 shell 历史中写入 PyPI token。
- 如果 PyPI Trusted Publisher 配置中的 workflow name 或 environment name 与仓库不一致，发布会失败。
- `pip index versions aitest-kit` 可能有短暂缓存延迟；直接安装指定版本更适合作为发布后验证。
