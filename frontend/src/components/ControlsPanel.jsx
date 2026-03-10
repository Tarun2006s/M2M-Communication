import React, { useState } from 'react';

const ControlsPanel = ({
    onStartSimulation,
    algorithms = [],
    onAlgorithmChange,
    parameters = {},
    onParameterChange
}) => {

    const [selectedAlgorithm, setSelectedAlgorithm] = useState(algorithms?.[0] || "");

    const handleStartClick = () => {
        if (onStartSimulation) {
            onStartSimulation(selectedAlgorithm, parameters);
        }
    };

    const handleAlgorithmChange = (event) => {
        const algorithm = event.target.value;
        setSelectedAlgorithm(algorithm);
        if (onAlgorithmChange) onAlgorithmChange(algorithm);
    };

    const handleParameterChange = (event) => {
        const { name, value } = event.target;
        if (onParameterChange) onParameterChange(name, value);
    };

    return (
        <div className="controls-panel">
            <h2>Simulation Controls</h2>

            <div>
                <label htmlFor="algorithm-select">Select Algorithm:</label>
                <select
                    id="algorithm-select"
                    value={selectedAlgorithm}
                    onChange={handleAlgorithmChange}
                >
                    {algorithms.map((algorithm) => (
                        <option key={algorithm} value={algorithm}>
                            {algorithm}
                        </option>
                    ))}
                </select>
            </div>

            <div>
                <h3>Parameters</h3>
                {Object.keys(parameters).map((param) => (
                    <div key={param}>
                        <label htmlFor={param}>{param}:</label>
                        <input
                            type="number"
                            id={param}
                            name={param}
                            value={parameters[param]}
                            onChange={handleParameterChange}
                        />
                    </div>
                ))}
            </div>

            <button onClick={handleStartClick}>Start Simulation</button>
        </div>
    );
};

export default ControlsPanel;