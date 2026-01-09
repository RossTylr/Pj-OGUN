# Pj-OGUN

**Logistics & Field Operations Simulation Platform**

Pj-OGUN is a discrete-event simulation platform for modelling field logistics and support operations. Named after the Yoruba orisha of iron, craftsmanship, and labour, it simulates:

- **CASEVAC**: Casualty evacuation from field positions to medical facilities
- **Recovery**: Vehicle breakdown response and repair workflows
- **Resupply**: Equipment and materiel distribution

## Features

- **Interactive Scenario Builder** - Visual node-based canvas for designing logistics networks
- **SimPy Simulation Engine** - Discrete-event simulation with deterministic (seeded) runs
- **Animation Replay** - Playback simulation results with vehicle tracking and event markers
- **KPI Dashboard** - Real-time metrics by subsystem (CASEVAC, Recovery, Resupply)
- **Extended Operations** - Support for 72-hour scenarios with crew fatigue and random breakdowns
- **Vehicle Modelling** - Light/Medium/Heavy vehicle classes with role-specific behaviours
- **Flexible Demand** - Manual event scheduling or rate-based generation

## Quick Start

```bash
cd pj-ogun
./run.sh
```

This creates an isolated `.venv`, installs dependencies, and launches the UI at http://localhost:8501

### Manual setup (if needed)
```bash
cd pj-ogun
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
python -m streamlit run src/pj_ogun/ui/app.py
```

### CLI commands
```bash
source .venv/bin/activate
ogun validate scenarios/example_medevac.json
ogun run scenarios/example_medevac.json --output results/
```

## Project Structure

```
pj-ogun/
├── src/pj_ogun/
│   ├── models/           # Pydantic schema definitions
│   ├── simulation/       # SimPy engine and processes
│   ├── analysis/         # KPI extraction and reporting
│   └── ui/
│       ├── app.py        # Main Streamlit application
│       ├── components/   # UI components (canvas, replay, builders)
│       └── state/        # Session state management
├── tests/                # Test suite
├── scenarios/            # Example scenario JSON files
├── run.sh                # One-command launcher
└── requirements.txt      # Dependencies for cloud deployment
```

## Development Phases

- [x] Phase 0: Foundation (schema, project scaffold)
- [x] Phase 1: Simulation engine (vehicle pathfinding)
- [x] Phase 2: KPI framework (CASEVAC, Recovery, Resupply metrics)
- [x] Phase 3: Streamlit MVP UI
- [x] Phase 4: Interactive canvas builder + extended operations (72hr, fatigue, breakdowns)
- [x] Phase 5: Animation replay with playback controls
- [ ] Phase 6: Polish & handover

## Tech Stack

- **Python 3.9+**
- **Streamlit** - Web UI framework
- **SimPy** - Discrete-event simulation
- **Pydantic** - Data validation
- **NetworkX** - Graph operations
- **Plotly** - Interactive visualizations
- **streamlit-flow-component** - Node-based canvas

## License

Proprietary
