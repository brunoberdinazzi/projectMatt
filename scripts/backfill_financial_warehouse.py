from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.runtime import analysis_workflow_service


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sincroniza snapshots financeiros antigos no warehouse canônico.",
    )
    parser.add_argument(
        "--analysis-id",
        type=int,
        default=None,
        help="Sincroniza uma análise específica.",
    )
    parser.add_argument(
        "--owner-user-id",
        type=int,
        default=None,
        help="Limita a sincronização ao usuário informado.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=200,
        help="Quantidade máxima de análises para backfill em lote.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Regrava snapshots que já existem no warehouse.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.analysis_id is not None:
        payload = analysis_workflow_service.sync_financial_warehouse_snapshot(
            analysis_id=args.analysis_id,
            owner_user_id=args.owner_user_id,
            force=args.force,
        )
    else:
        payload = analysis_workflow_service.backfill_financial_warehouse_snapshots(
            owner_user_id=args.owner_user_id,
            limit=args.limit,
            force=args.force,
        )

    print(json.dumps(payload.model_dump(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
