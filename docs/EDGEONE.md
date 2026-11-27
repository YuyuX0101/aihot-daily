# EdgeOne Git deployment

**Keep the EdgeOne production project off `main` while HP still publishes to it.** A preview project may track `cursor/integrate-builder-deals-9c12`.

1. On Linux, check out the agreed publish branch. Start with the defaults in `config/aihot.example.env`, including `AIHOT_DRY_RUN=1`, `AIHOT_ALLOW_GIT_PUSH=0`, `AIHOT_ALLOW_PUSH_MAIN=0`, and `AIHOT_FEISHU_ENABLED=0`.
2. Generate from the actual published inputs. Run `python3 -m tools.aihot_pipeline build` from the repository root to render the ingested editions and refresh the daily archive.
3. Review the generated pages and commit locally. When publication is authorized, push the reviewed commit to the agreed branch. EdgeOne's Git integration deploys that branch automatically. No EdgeOne API token is required on the generator.
4. Configure EdgeOne to serve the repository root (`.`) as the static output, with no build command. The generated files already include `/YYYY-MM-DD.html`, `/e/`, `/builder/`, and `/deals/`. The root `edgeone.json` supplies the cache headers.

Absolute summary links default to `https://yuyux0101.github.io/aihot-daily`. After DNS cutover, set `AIHOT_SITE_BASE_URL=https://aihot.travisyy.top` in the Linux generator environment before generating summaries.
