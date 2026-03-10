# dqn-battery-scheduling-app

This project implements a Deep Q-Network (DQN) combined with battery health management and sleep/awake scheduling for Wireless Sensor Networks (WSNs). The goal is to optimize energy consumption while maintaining network performance. The project includes both backend and frontend components, allowing for simulations and comparisons of the DQN-based algorithm against other scheduling algorithms.

## Project Structure

```
dqn-battery-scheduling-app
├── backend
│   ├── src
│   │   ├── dqn_agent.py          # Implementation of the DQN agent
│   │   ├── env_wsn.py            # Definition of the WSN environment
│   │   ├── compare_algorithms.py  # Logic to compare DQN with other algorithms
│   │   ├── api.py                 # API server setup for simulations
│   │   └── utils.py               # Utility functions for data processing
│   ├── requirements.txt           # Python dependencies for the backend
│   └── README.md                  # Documentation for the backend
├── frontend
│   ├── public
│   │   └── index.html             # Main HTML file for the frontend
│   ├── src
│   │   ├── App.jsx                # Main component of the React application
│   │   ├── index.js               # Entry point for the React application
│   │   ├── components
│   │   │   ├── SimulationDashboard.jsx  # Displays simulation results
│   │   │   ├── ComparisonCharts.jsx     # Visualizes algorithm comparisons
│   │   │   └── ControlsPanel.jsx        # Provides simulation controls
│   │   └── api
│   │       └── simulation.js           # Functions to interact with the backend API
│   ├── package.json                   # Configuration file for npm
│   └── README.md                      # Documentation for the frontend
└── README.md                          # Overview of the entire project
```

## Getting Started

### Prerequisites

- Python 3.7 or higher
- Node.js and npm

### Backend Setup

1. Navigate to the `backend` directory:
   ```
   cd backend
   ```

2. Install the required Python packages:
   ```
   pip install -r requirements.txt
   ```

3. Run the API server:
   ```
   python src/api.py
   ```

### Frontend Setup

1. Navigate to the `frontend` directory:
   ```
   cd frontend
   ```

2. Install the required npm packages:
   ```
   npm install
   ```

3. Start the React application:
   ```
   npm start
   ```

### Running Simulations

- Use the frontend interface to select algorithms, adjust parameters, and start simulations. The results will be displayed on the dashboard, and comparisons will be visualized in charts.

## Contributing

Contributions are welcome! Please open an issue or submit a pull request for any enhancements or bug fixes.

## License

This project is licensed under the MIT License. See the LICENSE file for details.