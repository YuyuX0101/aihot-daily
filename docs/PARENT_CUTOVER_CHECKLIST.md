# Parent 单点切流清单（本 Agent 不执行）

1. [ ] `check-no-side-effects.sh` 在 parent 机通过  
2. [ ] 与日更雷达 / HP 运维对齐唯一执行端  
3. [ ] 放置 `feishu-webhook.json`（不进 git）  
4. [ ] 配置 git 推送身份；先推非 main 预发分支验证 Pages  
5. [ ] 将 `AIHOT_DRY_RUN=0` 且仅一端启用 `AIHOT_ENABLE_SCHEDULE=1`  
6. [ ] 显式 `AIHOT_ALLOW_GIT_PUSH=1`（若推 main 另需 `AIHOT_ALLOW_PUSH_MAIN=1`）  
7. [ ] 显式 `AIHOT_FEISHU_ENABLED=1`  
8. [ ] 观察 ≥1 个业务日；确认无双发后再 disable HP 任务  
9. [ ] 回滚预案：立刻 `AIHOT_ENABLE_SCHEDULE=0` 并恢复 HP  
