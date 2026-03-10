import React, { useState } from 'react';
import { BrowserRouter as Router, Routes, Route, useNavigate } from 'react-router-dom';
import SimulationDashboard from './components/SimulationDashboard';
import ComparisonCharts from './components/ComparisonCharts';
import ControlsPanel from './components/ControlsPanel';
import { fetchSimulationResults } from './api/simulation';

const AppContent = () => {

    const navigate = useNavigate();

    const [results, setResults] = useState(null);

    const [parameters, setParameters] = useState({
        seed: 42,
        N: 10,
        episodes: 50,
        max_steps: 100
    });

    const algorithms = ["DQN"];

    const handleParameterChange = (name, value) => {
        setParameters({
            ...parameters,
            [name]: Number(value)
        });
    };

    const startSimulation = async () => {
        try {
            const data = await fetchSimulationResults(parameters);

            console.log("Simulation Result:", data);

            setResults(data);

            // Navigate to dashboard after simulation finishes
            navigate("/dashboard");

        } catch (error) {
            console.error("Simulation failed:", error);
        }
    };

    return (
        <div>

            <h1>DQN Battery Scheduling Simulation</h1>

            <ControlsPanel
                algorithms={algorithms}
                parameters={parameters}
                onStartSimulation={startSimulation}
                onParameterChange={handleParameterChange}
                onAlgorithmChange={() => {}}
            />

            <Routes>

                <Route
                    path="/dashboard"
                    element={<SimulationDashboard results={results} />}
                />

                <Route
                    path="/comparison"
                    element={<ComparisonCharts results={results} />}
                />

                <Route
                    path="/"
                    element={
                        <>
                            <h2>Welcome to the DQN Battery Scheduling App</h2>
                            <p>Select parameters and click Start Simulation.</p>
                        </>
                    }
                />

            </Routes>

        </div>
    );
};

const App = () => {
    return (
        <Router>
            <AppContent />
        </Router>
    );
};

export default App;