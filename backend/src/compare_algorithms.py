import numpy as np
import torch
from dqn_agent import DDQNAgent
from env_wsn import WSNEnv

def run_comparison(num_nodes=10, episodes=500, max_steps=1000):
    env = WSNEnv(N=num_nodes, max_steps=max_steps)
    state_dim = env.observation_space.shape[0]
    action_dim = 2

    # Initialize DQN agent
    dqn_agent = DDQNAgent(state_dim, action_dim, node_count=num_nodes)

    # Placeholder for other algorithms (e.g., random, heuristic)
    algorithms = {
        "DQN": dqn_agent,
        "Random": RandomAlgorithm(env),
        "Heuristic": HeuristicAlgorithm(env)
    }

    results = {name: [] for name in algorithms.keys()}

    for name, algorithm in algorithms.items():
        for episode in range(episodes):
            state = env.reset()
            total_reward = 0
            done = False

            while not done:
                action = algorithm.select_action(state)
                next_state, reward, done, _ = env.step(action)
                total_reward += reward

                if name == "DQN":
                    dqn_agent.store(state, action, reward, next_state, done)
                    dqn_agent.train_step()

                state = next_state

            results[name].append(total_reward)

    return results

class RandomAlgorithm:
    def __init__(self, env):
        self.env = env

    def select_action(self, state):
        return np.random.randint(0, 2, size=self.env.N)

class HeuristicAlgorithm:
    def __init__(self, env):
        self.env = env

    def select_action(self, state):
        # Implement a simple heuristic for action selection
        return (self.env.soc > 0.5).astype(int)

if __name__ == "__main__":
    comparison_results = run_comparison()
    print(comparison_results)