"""Pj-OGUN Command Line Interface.

Usage:
    ogun validate <scenario.json>     Validate scenario file
    ogun run <scenario.json>          Run simulation
    ogun schema                       Output JSON schema
"""

import argparse
import json
import sys
from pathlib import Path


def cmd_validate(args: argparse.Namespace) -> int:
    """Validate a scenario JSON file."""
    from pj_ogun.models.scenario import load_scenario
    from pydantic import ValidationError
    
    path = Path(args.scenario)
    print(f"Validating: {path}")
    
    if not path.exists():
        print(f"ERROR: File not found: {path}", file=sys.stderr)
        return 1
    
    try:
        scenario = load_scenario(str(path))
        print(f"✓ Valid scenario: {scenario.name}")
        print()
        print(scenario.summary())
        return 0
    
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON at line {e.lineno}: {e.msg}", file=sys.stderr)
        return 1
    
    except ValidationError as e:
        print(f"ERROR: Schema validation failed:", file=sys.stderr)
        for error in e.errors():
            loc = " -> ".join(str(x) for x in error["loc"])
            print(f"  {loc}: {error['msg']}", file=sys.stderr)
        return 1
    
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}", file=sys.stderr)
        return 1


def cmd_run(args: argparse.Namespace) -> int:
    """Run a simulation and output results."""
    from pj_ogun.models.scenario import load_scenario
    from pj_ogun.simulation.engine import SimulationEngine
    from pj_ogun.analysis.kpis import compute_medevac_kpis, compute_all_kpis

    path = Path(args.scenario)
    print(f"Loading: {path}")

    try:
        scenario = load_scenario(str(path))
        print(f"Scenario: {scenario.name}")
        print(f"Duration: {scenario.config.duration_hours} hours")
        print(f"Seed: {scenario.config.random_seed}")
        print()

        # Run simulation
        print("Running simulation...")
        engine = SimulationEngine(scenario)
        event_log = engine.run()

        print(f"Simulation complete: {len(event_log)} events logged")
        print()

        # Compute KPIs
        kpis = compute_medevac_kpis(event_log)
        print(kpis.summary())

        # Output results if directory specified
        if args.output:
            output_dir = Path(args.output)
            output_dir.mkdir(parents=True, exist_ok=True)

            # Save event log CSV
            events_path = output_dir / "events.csv"
            event_log.to_dataframe().to_csv(events_path, index=False)
            print(f"\nEvents saved to: {events_path}")

            # Save casualties CSV
            cas_path = output_dir / "casualties.csv"
            event_log.casualties_to_dataframe().to_csv(cas_path, index=False)
            print(f"Casualties saved to: {cas_path}")

            # Save KPIs JSON
            kpis_path = output_dir / "kpis.json"
            all_kpis = compute_all_kpis(event_log)
            with open(kpis_path, "w") as f:
                json.dump(all_kpis, f, indent=2)
            print(f"KPIs saved to: {kpis_path}")

        return 0

    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}", file=sys.stderr)
        return 1


def cmd_schema(args: argparse.Namespace) -> int:
    """Output JSON schema for scenario files."""
    from pj_ogun.models.scenario import Scenario
    
    schema = Scenario.model_json_schema()
    
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(schema, f, indent=2)
        print(f"Schema written to: {output_path}")
    else:
        print(json.dumps(schema, indent=2))
    
    return 0


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        prog="ogun",
        description="Pj-OGUN: British Army CS/CSS Logistics Simulation",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # validate command
    p_validate = subparsers.add_parser(
        "validate",
        help="Validate a scenario JSON file",
    )
    p_validate.add_argument("scenario", help="Path to scenario JSON file")
    p_validate.set_defaults(func=cmd_validate)
    
    # run command
    p_run = subparsers.add_parser(
        "run",
        help="Run simulation",
    )
    p_run.add_argument("scenario", help="Path to scenario JSON file")
    p_run.add_argument(
        "--output", "-o",
        help="Output directory for results",
    )
    p_run.set_defaults(func=cmd_run)
    
    # schema command
    p_schema = subparsers.add_parser(
        "schema",
        help="Output JSON schema",
    )
    p_schema.add_argument(
        "--output", "-o",
        help="Output file (default: stdout)",
    )
    p_schema.set_defaults(func=cmd_schema)
    
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
