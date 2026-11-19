# Deferred log assertions example

After `aitest init`, copy this directory's `test_workspace/` tree into a disposable workspace. Run `aitest codegen --suite-file test_workspace/suites/demo/log_assertions/suite.yaml --validate-profile`, then repeat without the flag to generate pytest. Use `aitest run --suite-file test_workspace/suites/demo/log_assertions/suite.yaml` with a configured demo service and log platform to run both phases.

The demo Harness expects `AITEST_LOG_DEMO_URL`. Its service contract is a POST to that URL, with an optional `X-Demo-Capture: true` header, and a JSON response with `code`, `score`, and, for capture, `trace_id`. The corresponding log events use source `demo` and type `SCENE_HIT`.

See the workspace reference at `aitest_config/refs/log-assertions.md`.

The `log_multi_request` suite shows separate request bindings and response-derived values in one case. Its mock acceptance contract returns two ordered events per request. It uses the default retain policy.
