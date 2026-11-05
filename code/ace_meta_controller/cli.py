"""CLI: PYTHONPATH=code python -m ace_meta_controller.cli --root RUN_DIR [--budget 16]."""
import argparse
import json
from .controller import Controller, IntegrityError


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True)
    parser.add_argument('--budget', type=int, default=16)
    parser.add_argument('--stop-after-trials', type=int)
    args = parser.parse_args(argv)
    try:
        result = Controller(args.root, budget=args.budget).run(stop_after_trials=args.stop_after_trials)
        print(json.dumps(result, sort_keys=True, indent=2))
        return 0
    except IntegrityError as exc:
        print(json.dumps({'status': 'HALT_INTEGRITY_ERROR', 'reason': str(exc)}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
