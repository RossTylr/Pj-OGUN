# Pj-OGUN

**Logistics & Field Operations Simulation Platform**

[![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://pj-ogun.streamlit.app)

Pj-OGUN is a discrete-event simulation platform for modelling field logistics and support operations. Named after the Yoruba orisha of iron, craftsmanship, and labour, it simulates:

- **CASEVAC**: Casualty evacuation from field positions to medical facilities
- **Recovery**: Vehicle breakdown response and repair workflows
- **Resupply**: Equipment and materiel distribution

## Live Demo

**[Launch Pj-OGUN on Streamlit Cloud](https://pj-ogun.streamlit.app)**

No installation required - run simulations directly in your browser.

## Features

- **Interactive Scenario Builder** - Visual node-based canvas for designing logistics networks
- **Scenario Templates** - Pre-built configurations for common exercises:
  - Basic MEDEVAC (4 nodes)
  - Battalion Support (10 nodes)
  - Brigade TIRGOLD (20+ nodes)
- **SimPy Simulation Engine** - Discrete-event simulation with deterministic (seeded) runs
- **Animation Replay** - Playback simulation results with vehicle tracking and event markers
- **KPI Dashboard** - Real-time metrics by subsystem (CASEVAC, Recovery, Resupply)
- **Extended Operations** - Support for 72-hour scenarios with crew fatigue and random breakdowns
- **Vehicle Modelling** - Light/Medium/Heavy vehicle classes with role-specific behaviours
- **Flexible Demand** - Manual event scheduling or rate-based generation

## Quick Start

### Option 1: Streamlit Cloud (Recommended)
Click the badge above or visit the [Live Demo](https://pj-ogun.streamlit.app) link.

### Option 2: Local Installation

```bash
./run.sh
```

This creates an isolated `.venv`, installs dependencies, and launches the UI at http://localhost:8501

### Manual setup (if needed)
```bash
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
Pj-OGUN/
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
├── .streamlit/           # Streamlit Cloud configuration
├── run.sh                # One-command launcher
├── requirements.txt      # Dependencies for cloud deployment
└── pyproject.toml        # Package configuration
```

## Development Phases

- [x] Phase 0: Foundation (schema, project scaffold)
- [x] Phase 1: Simulation engine (vehicle pathfinding)
- [x] Phase 2: KPI framework (CASEVAC, Recovery, Resupply metrics)
- [x] Phase 3: Streamlit MVP UI
- [x] Phase 4: Interactive canvas builder + extended operations (72hr, fatigue, breakdowns)
- [x] Phase 5: Animation replay with playback controls
- [x] Phase 6: Advanced scenarios (multi-echelon templates, UX improvements)
- [ ] Phase 7: Sensitivity analysis & Monte Carlo
- [ ] Phase 8: Documentation & handover

## Tech Stack

- **Python 3.9+**
- **Streamlit** - Web UI framework
- **SimPy** - Discrete-event simulation
- **Pydantic** - Data validation
- **NetworkX** - Graph operations
- **Plotly** - Interactive visualizations
- **streamlit-flow-component** - Node-based canvas

## Deployment

### Streamlit Cloud
The app is configured for Streamlit Cloud deployment:
1. Connect your GitHub repository to [share.streamlit.io](https://share.streamlit.io)
2. Set the main file path to: `src/pj_ogun/ui/app.py`
3. Dependencies are automatically installed from `requirements.txt`

### Docker (Coming Soon)
Docker containerisation planned for Phase 8.

## License

Proprietary
