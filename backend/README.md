# dqn-battery-scheduling-app/backend/README.md

# DQN Battery Scheduling Application - Backend

This project implements a Deep Q-Network (DQN) combined with battery health management and sleep/awake scheduling for Wireless Sensor Networks (WSN). The backend is responsible for running simulations, managing the DQN agent, and providing an API for the frontend application.

## Table of Contents

- [Installation](#installation)
- [Usage](#usage)
- [API Endpoints](#api-endpoints)
- [File Structure](#file-structure)
- [License](#license)

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/dqn-battery-scheduling-app.git
   cd dqn-battery-scheduling-app/backend
   ```

2. Create a virtual environment (optional but recommended):
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```

3. Install the required packages:
   ```
   pip install -r requirements.txt
   ```

## Usage

1. Start the API server:
   ```
   python src/api.py
   ```

2. The server will run on `http://localhost:8000` (or another port if specified).

3. Use the frontend application to interact with the backend and run simulations.

## API Endpoints

- `POST /simulate`: Runs a simulation with the specified parameters.
- `GET /results`: Retrieves the results of the last simulation.
- `GET /compare`: Compares the DQN algorithm against other algorithms and returns the metrics.

## File Structure

- `src/`
  - `dqn_agent.py`: Implementation of the DQN agent.
  - `env_wsn.py`: Definition of the WSN environment and battery model.
  - `compare_algorithms.py`: Logic to compare DQN with other algorithms.
  - `api.py`: API server setup.
  - `utils.py`: Utility functions for data processing and logging.
- `requirements.txt`: Python dependencies for the backend.

## License

This project is licensed under the MIT License. See the LICENSE file for details.