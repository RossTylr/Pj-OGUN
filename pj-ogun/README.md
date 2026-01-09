# Pj-OGUN

**British Army CS/CSS Logistics Simulation**

Pj-OGUN is a discrete-event simulation platform for modelling Combat Service Support (CS/CSS) logistics operations. Named after the Yoruba orisha of iron, war, and labour, it simulates:

- **MEDEVAC**: Casualty evacuation from combat positions to medical facilities
- **Recovery**: Vehicle breakdown response and repair workflows  
- **Resupply**: Ammunition and materiel distribution

## Features

- Point-and-click scenario builder (Streamlit UI)
- SimPy-based discrete-event simulation engine
- Deterministic (seeded) runs for reproducible training scenarios
- KPI dashboards by subsystem
- Support for 72-hour extended operations
- Light/Medium/Heavy vehicle class modelling
- Manual and rate-based demand generation

## Quick Start

```bash
# Install dependencies
pip install -e .

# Validate a scenario
ogun validate scenarios/example_medevac.json

# Run simulation
ogun run scenarios/example_medevac.json --output results/

# Launch UI
streamlit run src/pj_ogun/ui/app.py
```

## Project Structure

```
pj-ogun/
├── src/pj_ogun/
│   ├── models/        # Pydantic schema definitions
│   ├── simulation/    # SimPy engine and processes
│   ├── analysis/      # KPI extraction and reporting
│   └── ui/            # Streamlit application
├── tests/             # Test suite
├── scenarios/         # Example scenario JSON files
└── docs/              # Documentation
```

## Development Phases

- [x] Phase 0: Foundation (schema, project scaffold)
- [ ] Phase 1: Simulation engine (ambulance pathfinder)
- [ ] Phase 2: KPI framework
- [ ] Phase 3: Streamlit MVP UI
- [ ] Phase 4: Extended duration (72hr, fatigue, maintenance)
- [ ] Phase 5: Demand modelling enhancement
- [ ] Phase 6: Polish & handover

## License

Crown Copyright - Ministry of Defence
