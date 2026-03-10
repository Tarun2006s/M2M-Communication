import React from "react";
import { Line } from "react-chartjs-2";

const ComparisonCharts = ({ results }) => {

  if (!results || !results.rewards) {
    return <p>Run simulation to see results.</p>;
  }

  const labels = results.rewards.map((_, i) => i + 1);
  const datasets = [
    {
      label: "Reward per Episode",
      data: results.rewards,
      borderColor: "rgba(75,192,192,1)",
      backgroundColor: "rgba(75,192,192,0.2)",
      fill: true
    }
  ];

  // append battery/soh history if present (assumed same length as rewards for final episode)
  if (results.battery_history && results.battery_history.length) {
    datasets.push({
      label: "Avg Battery SoC",
      data: results.battery_history,
      borderColor: "rgba(255,99,132,1)",
      backgroundColor: "rgba(255,99,132,0.2)",
      fill: false,
      yAxisID: 'y1'
    });
  }
  if (results.soh_history && results.soh_history.length) {
    datasets.push({
      label: "Avg Battery SoH",
      data: results.soh_history,
      borderColor: "rgba(54,162,235,1)",
      backgroundColor: "rgba(54,162,235,0.2)",
      fill: false,
      yAxisID: 'y1'
    });
  }

  const chartData = { labels, datasets };

  const options = {
    responsive: true,
    plugins: {
      title: { display: true, text: 'Simulation Metrics' }
    },
    scales: {
      y: {
        type: 'linear',
        display: true,
        position: 'left',
        beginAtZero: true,
        title: { display: true, text: 'Reward' }
      },
      y1: {
        type: 'linear',
        display: true,
        position: 'right',
        beginAtZero: true,
        suggestedMax: 1,
        grid: { drawOnChartArea: false },
        title: { display: true, text: 'Battery (SoC/SoH)' }
      }
    }
  };

  return (
    <div>
      <h2>Simulation Results</h2>
      <Line redraw data={chartData} options={options} />
    </div>
  );
};

export default ComparisonCharts;