# ab_service_smoke suite profile

Suite-specific codegen profile generated from the existing reviewed case/profile assets.

```yaml
profile_scope: case_suite
parent_module: ab_service
suite: ab_service_smoke
case_flows:
  TC-ABS-012:
    steps:
    - call: ab.isolated_experiment_persists_auto
      save_as: result
    - assert: assert result['create_status'] == 200
    - assert: assert result['read_status'] == 200
    - assert: assert result['name'] == 'exp_abs_persist'
  TC-ABS-018:
    steps:
    - call: ab.isolated_whitelist_persists_auto
      save_as: result
    - assert: assert result['write_status'] == 200
    - assert: assert result['read_status'] == 200
    - assert: 'assert result[''body''] == {''exp_game'': ''game_on''}'
  TC-ABS-026:
    steps:
    - call: ab.missing_experiments_file_is_created_auto
      save_as: result
    - assert: assert result['status'] == 200
    - assert: assert result['body'] == []
    - assert: assert result['exists']
  TC-ABS-027:
    steps:
    - call: ab.malformed_whitelist_falls_back_empty_auto
      save_as: result
    - assert: assert result['status'] == 200
    - assert: assert result['body'] == {}
    - assert: assert '白名单文件读取失败' in result['logs']
  TC-ABS-028:
    steps:
    - call: ab.bad_hash_range_still_evaluates_auto
      save_as: result
    - assert: assert result['status'] == 200
    - assert: assert result['strategy_id'] == 's_bad'
  TC-ABS-029:
    steps:
    - call: ab.bad_params_fall_back_empty_auto
      save_as: result
    - assert: assert result['status'] == 200
    - assert: assert result['params'] == {}
  TC-ABS-033:
    steps:
    - call: ab.import_works_from_other_cwd_auto
      save_as: result
    - assert: assert result['returncode'] == 0, result['stderr']
    - assert: assert 'ok ab_experiment_sdk.service' in result['stdout']
  TC-ABS-034:
    steps:
    - call: ab.import_has_no_default_file_side_effect_auto
      save_as: result
    - assert: assert result['returncode'] == 0, result['stderr']
    - assert: assert 'exists False' in result['stdout']
  TC-ABS-035:
    steps:
    - call: ab.remote_sdk_evaluate_whitelist_auto
      save_as: result
    - assert: assert result['request_id'] == 'req_abs_035'
    - assert: assert result['strategy_id'] == 'game_on'
    - assert: assert result['hit_reason'] == 'whitelist'
  TC-ABS-036:
    steps:
    - call: ab.remote_sdk_set_user_whitelist_auto
      save_as: result
    - assert: assert result['strategy_id'] == 'cal_on'
    - assert: assert result['hit_reason'] == 'whitelist'
  TC-ABS-037:
    steps:
    - call: ab.remote_sdk_clear_user_whitelist_auto
      save_as: result
    - assert: assert 'u2' not in result['whitelist']
  TC-ABS-038:
    steps:
    - call: ab.remote_sdk_replace_whitelist_auto
      save_as: result
    - assert: 'assert result[''whitelist''] == {''u3'': {''exp_game'': ''game_on''}}'
  TC-ABS-039:
    steps:
    - call: ab.remote_sdk_clear_all_whitelist_auto
      save_as: result
    - assert: assert result['whitelist'] == {}
  TC-ABS-040:
    steps:
    - call: ab.remote_sdk_raises_on_http_error
      save_as: result
    - assert: assert result['raised'] is True
    - assert: assert result['status_code'] == 500
  TC-ABS-001:
    steps:
    - call: ab.get
      args:
      - /health
      save_as: resp
    - assert: assert resp.status_code == 200
    - assert: 'assert resp.json() == {''status'': ''ok''}'
  TC-ABS-002:
    steps:
    - call: ab.post
      args:
      - /api/v1/ab/evaluate
      - user_id: u_abs_hash_0
        request_id: req_abs_002
        context: {}
        experiment_names:
        - exp_ab_basic
      save_as: resp
    - assert: assert resp.status_code == 200
    - assign: assign
      expr: resp.json()['assignments']
    - assert: assert assign['exp_ab_basic']['strategy_id'] == 's_a'
    - assert: assert assign['exp_ab_basic']['hit_reason'] == 'hash'
  TC-ABS-003:
    steps:
    - call: ab.post
      args:
      - /api/v1/ab/evaluate
      - user_id: u_abs_white
        request_id: req_abs_003
        context: {}
        experiment_names:
        - exp_ab_basic
      save_as: resp
    - assert: assert resp.status_code == 200
    - assign: assign
      expr: resp.json()['assignments']
    - assert: assert assign['exp_ab_basic']['strategy_id'] == 's_b'
    - assert: assert assign['exp_ab_basic']['hit_reason'] == 'whitelist'
  TC-ABS-004:
    steps:
    - call: ab.post
      args:
      - /api/v1/ab/evaluate
      - user_id: u_abs_hash_0
        request_id: req_abs_004
        context: {}
        experiment_names: null
      save_as: resp
    - assert: assert resp.status_code == 200
    - assign: assign
      expr: resp.json()['assignments']
    - assert: assert {'exp_ab_basic', 'exp_ab_extra'} <= set(assign.keys())
  TC-ABS-005:
    steps:
    - call: ab.post
      args:
      - /api/v1/ab/evaluate
      - user_id: u_abs_hash_0
        request_id: req_abs_005
        context: {}
        experiment_names: []
      save_as: resp
    - assert: assert resp.status_code == 200
    - assert: assert resp.json()['assignments'] == {}
  TC-ABS-006:
    steps:
    - call: ab.post
      args:
      - /api/v1/ab/evaluate
      - user_id: u_abs_hash_0
        request_id: req_abs_006
        context: {}
        experiment_names:
        - exp_ab_basic
      save_as: resp
    - assert: assert resp.status_code == 200
    - assert: assert set(resp.json()['assignments'].keys()) <= {'exp_ab_basic'}
  TC-ABS-007:
    steps:
    - call: ab.get
      args:
      - /api/v1/ab/experiments
      save_as: resp
    - assert: assert resp.status_code == 200
    - assert: assert {'exp_game', 'exp_cal'} <= {item['name'] for item in resp.json()}
  TC-ABS-008:
    steps:
    - call: ab.get
      args:
      - /api/v1/ab/experiments/exp_game
      save_as: resp
    - assert: assert resp.status_code == 200
    - assert: assert resp.json()['name'] == 'exp_game'
  TC-ABS-009:
    steps:
    - assign: payload
      expr: '{''name'': ''exp_abs_create'', ''strategies'': [{''id'': ''s1'', ''hash_range'': [0, 100], ''params'': {''k'':
        ''v''}}]}'
    - call: ab.snapshot_experiment
      args:
      - exp_abs_create
    - call: ab.post
      args:
      - /api/v1/ab/experiments
      - expr: payload
      save_as: resp
    - assert: assert resp.status_code == 200
    - assert: assert resp.json()['name'] == 'exp_abs_create'
    - call: ab.get
      args:
      - /api/v1/ab/experiments/exp_abs_create
      save_as: resp
    - assert: assert resp.status_code == 200
    - assert: assert resp.json()['name'] == 'exp_abs_create'
  TC-ABS-010:
    steps:
    - call: ab.upsert_experiment
      args:
      - name: exp_abs_update
        strategies:
        - id: s_old
          hash_range:
          - 0
          - 100
          params: {}
    - assign: payload
      expr: '{''name'': ''exp_abs_update'', ''strategies'': [{''id'': ''s_new'', ''hash_range'': [0, 100], ''params'': {}}]}'
    - call: ab.put
      args:
      - /api/v1/ab/experiments/exp_abs_update
      - expr: payload
      save_as: resp
    - assert: assert resp.status_code == 200
    - call: ab.get
      args:
      - /api/v1/ab/experiments/exp_abs_update
      save_as: resp
    - assert: assert [item['id'] for item in resp.json()['strategies']] == ['s_new']
  TC-ABS-011:
    steps:
    - call: ab.upsert_experiment
      args:
      - name: exp_abs_delete
        strategies:
        - id: s1
          hash_range:
          - 0
          - 100
          params: {}
    - call: ab.delete
      args:
      - /api/v1/ab/experiments/exp_abs_delete
      save_as: resp
    - assert: assert resp.status_code == 200
    - assert: 'assert resp.json() == {''deleted'': True}'
    - call: ab.get
      args:
      - /api/v1/ab/experiments/exp_abs_delete
      save_as: resp
    - assert: assert resp.status_code == 404
    - assert: assert resp.json()['detail'] == 'experiment not found'
  TC-ABS-013:
    steps:
    - call: ab.get
      args:
      - /api/v1/ab/whitelist
      save_as: resp
    - assert: assert resp.status_code == 200
    - assert: assert 'u_white' in resp.json()
  TC-ABS-014:
    steps:
    - call: ab.snapshot_whitelist
    - call: ab.put
      args:
      - /api/v1/ab/whitelist/u_abs_user
      - strategy_map:
          exp_ab_basic: s_a
      save_as: resp
    - assert: assert resp.status_code == 200
    - call: ab.get
      args:
      - /api/v1/ab/whitelist/u_abs_user
      save_as: resp
    - assert: assert resp.status_code == 200
    - assert: 'assert resp.json() == {''exp_ab_basic'': ''s_a''}'
  TC-ABS-015:
    steps:
    - call: ab.snapshot_whitelist
    - call: ab.put
      args:
      - /api/v1/ab/whitelist
      - u_abs_1:
          exp_ab_basic: s_a
        u_abs_2:
          exp_ab_basic: s_b
      save_as: resp
    - assert: assert resp.status_code == 200
    - call: ab.get
      args:
      - /api/v1/ab/whitelist
      save_as: resp
    - assert: assert resp.status_code == 200
    - assert: 'assert resp.json() == {''u_abs_1'': {''exp_ab_basic'': ''s_a''}, ''u_abs_2'': {''exp_ab_basic'': ''s_b''}}'
  TC-ABS-016:
    steps:
    - call: ab.delete
      args:
      - /api/v1/ab/whitelist/user_b
      save_as: resp
    - assert: assert resp.status_code == 200
    - assert: 'assert resp.json() == {''cleared'': True}'
    - call: ab.get
      args:
      - /api/v1/ab/whitelist/user_b
      save_as: resp
    - assert: assert resp.status_code == 404
  TC-ABS-017:
    steps:
    - call: ab.delete
      args:
      - /api/v1/ab/whitelist
      save_as: resp
    - assert: assert resp.status_code == 200
    - assert: 'assert resp.json() == {''cleared'': True}'
    - call: ab.get
      args:
      - /api/v1/ab/whitelist
      save_as: resp
    - assert: assert resp.status_code == 200
    - assert: assert resp.json() == {}
  TC-ABS-019:
    steps:
    - assign: payload
      expr: '{''name'': ''exp_abs_dup'', ''strategies'': [{''id'': ''s1'', ''hash_range'': [0, 100], ''params'': {}}]}'
    - call: ab.snapshot_experiment
      args:
      - exp_abs_dup
    - call: ab.post
      args:
      - /api/v1/ab/experiments
      - expr: payload
      save_as: first
    - assert: assert first.status_code == 200
    - call: ab.post
      args:
      - /api/v1/ab/experiments
      - expr: payload
      save_as: second
    - assert: assert second.status_code == 409
    - assert: 'assert second.json()[''detail''] == ''experiment already exists: exp_abs_dup'''
  TC-ABS-020:
    steps:
    - call: ab.put
      args:
      - /api/v1/ab/experiments/exp_abs_path
      - name: exp_abs_body
        strategies: []
      save_as: resp
    - assert: assert resp.status_code == 400
    - assert: assert resp.json()['detail'] == 'path name and payload name mismatch'
  TC-ABS-021:
    steps:
    - call: ab.get
      args:
      - /api/v1/ab/whitelist/u_abs_not_exists
      save_as: resp
    - assert: assert resp.status_code == 404
    - assert: assert resp.json()['detail'] == 'user whitelist not found'
  TC-ABS-022:
    steps:
    - call: ab.delete
      args:
      - /api/v1/ab/whitelist/u_abs_not_exists
      save_as: resp
    - assert: assert resp.status_code == 200
    - assert: 'assert resp.json() == {''cleared'': True}'
  TC-ABS-023:
    steps:
    - call: ab.post
      args:
      - /api/v1/ab/evaluate
      - user_id: u_abs_overlap_243
        request_id: req_abs_023
        experiment_names:
        - exp_abs_overlap
      save_as: resp
    - assert: assert resp.status_code == 200
    - assert: assert resp.json()['assignments']['exp_abs_overlap']['strategy_id'] == 's_first'
  TC-ABS-024:
    steps:
    - call: ab.post
      args:
      - /api/v1/ab/evaluate
      - user_id: u_abs_hash_0
        request_id: req_abs_024
        experiment_names:
        - exp_abs_empty
      save_as: resp
    - assert: assert resp.status_code == 200
    - assert: assert resp.json()['assignments'] == {}
  TC-ABS-025:
    steps:
    - call: ab.post
      args:
      - /api/v1/ab/evaluate
      - user_id: u_abs_hash_0
        request_id: req_abs_025
        experiment_names:
        - not_exists_exp
      save_as: resp
    - assert: assert resp.status_code == 200
    - assert: assert resp.json()['assignments'] == {}
  TC-ABS-030:
    steps:
    - call: ab.post
      args:
      - /api/v1/ab/evaluate
      - request_id: req_abs_030
        experiment_names:
        - exp_ab_basic
      save_as: resp
    - assert: assert resp.status_code == 422
    - assert: assert ['body', 'user_id'] in [item['loc'] for item in resp.json()['detail']]
  TC-ABS-031:
    steps:
    - call: ab.post
      args:
      - /api/v1/ab/experiments
      - name: exp_abs_bad_schema
        strategies: bad
      save_as: resp
    - assert: assert resp.status_code == 422
  TC-ABS-032:
    steps:
    - call: ab.put
      args:
      - /api/v1/ab/whitelist/u_abs_bad_schema
      - strategy_map: bad
      save_as: resp
    - assert: assert resp.status_code == 422
```
