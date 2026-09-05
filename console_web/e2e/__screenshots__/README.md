# Reviewed visual baselines

Playwright resolves snapshots with `{arg}-{platform}{ext}`. Keep Darwin and Linux
baselines separate; do not copy a macOS rendering to a Linux filename or increase
the tolerance to compensate for a missing baseline.

Linux baseline provenance:

- GitHub Actions [run 33508507756](https://github.com/tlzmw001/aitest-kit/actions/runs/33508507756),
  commit `a70855ef9d67965191b0bc7bbd81058258306515`.
- `console-playwright-diagnostics` artifact, Chromium on the Ubuntu runner.
- Each saved baseline has the same SHA-256 as its corresponding `*-actual.png`.
- Both images were visually reviewed before importing. The 1440×900 approval
  workbench is complete; the 34×38 close-button crop has the expected compact hover.

| Linux file | SHA-256 |
| --- | --- |
| agent-approval-workbench-linux.png | 0c41c952827c7213d486ad0d82735c1824c32f043188c9a377fbc2b3eafbbae5 |
| editor-tab-close-hover-linux.png | 3dc25eb59ef21558e16ef8440c5cc3e9d2f583499c424b4adf0796bdc7dc0a28 |

This import does not establish that newer code passes Linux visual regression.
Run current tests on GitHub after pushing. For intentional visual changes, inspect
the diagnostic expected/actual/diff artifacts, regenerate in the matching OS and
browser environment, and review the resulting PNGs before committing. Never update
baselines automatically on CI failures. See [Playwright guidance](https://playwright.dev/docs/test-snapshots).
