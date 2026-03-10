# train_ddqn.py
import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

import numpy as np
import torch
from env_wsn import WSNEnv
from ddqn_agent import DDQNAgent
import time
import matplotlib.pyplot as plt

def run_training(seed=0, N=10, episodes=5000, max_steps=500, eval_every=100, save_dir="results"):
    env = WSNEnv(N=N, max_steps=max_steps, seed=seed)
    state_dim = env.observation_space.shape[0]
    action_dim = 2
    agent = DDQNAgent(state_dim, action_dim, node_count=N, lr=1e-4,
                      gamma=0.99, batch_size=64, buffer_size=200000,
                      min_replay_size=1000, update_target_every=1000)

    os.makedirs(save_dir, exist_ok=True)
    rewards_history = []
    losses = []
    best_eval = -1e9

    start_time = time.time()

    for ep in range(1, episodes+1):
        state = env.reset()
        ep_reward = 0.0
        done = False

        while not done:
            action = agent.select_action(state)
            next_state, reward, done, info = env.step(action)

            agent.store(state, action, reward, next_state, done)
            loss = agent.train_step()

            if loss is not None:
                losses.append(loss)

            state = next_state
            ep_reward += reward

        rewards_history.append(ep_reward)

        # ---- Evaluation inside training ----
        if ep % eval_every == 0:
            results = evaluate_policy(agent, env, episodes=1)
            avg_lifetime = results["lifetime"][0]

            print(f"Ep {ep} | Lifetime: {avg_lifetime:.2f}")

            if avg_lifetime > best_eval:
                best_eval = avg_lifetime
                torch.save(agent.q_net.state_dict(),
                           os.path.join(save_dir, f"best_ddqn_ep{ep}.pth"))

    duration = time.time() - start_time
    print("Training done, time:", duration)

    # ---- FINAL EVALUATION ----
    results = evaluate_policy(agent, env, episodes=1)

    # 🔥 Plot required research graphs
    plot_required_graphs(results, losses, method_name="DDQN")

    # ---- Plot reward curve ----
    plt.figure()
    plt.plot(rewards_history)
    plt.title("Episode Rewards")
    plt.xlabel("Episode")
    plt.ylabel("Reward")
    plt.savefig(os.path.join(save_dir, "rewards.png"))
    plt.close()

    # ---- Plot loss curve ----
    plt.figure()
    plt.plot(losses)
    plt.title("Training Loss")
    plt.xlabel("Training Steps")
    plt.ylabel("Loss")
    plt.savefig(os.path.join(save_dir, "loss.png"))
    plt.close()


def evaluate_policy(agent, env, episodes=1, render=False):
    lifetime = []
    energy_curve = []
    alive_curve = []

    for ep in range(episodes):
        state = env.reset()
        done = False

        step_energy = []
        step_alive = []
        steps_alive = 0

        while not done:
            action = agent.select_action(state, eval_mode=True)
            state, reward, done, info = env.step(action)

            if render:
                env.render()

            step_energy.append(info['total_energy'])

            alive_nodes = env.N - info['dead_nodes']
            step_alive.append(alive_nodes)

            if info['dead_nodes'] == 0:
                steps_alive += 1

        lifetime.append(steps_alive)
        energy_curve.append(step_energy)
        alive_curve.append(step_alive)

    return {
        "lifetime": lifetime,
        "energy": energy_curve,
        "alive": alive_curve
    }


def plot_required_graphs(results, mse_per_round, method_name="DDQN"):
    energy = np.array(results["energy"][0])
    alive = np.array(results["alive"][0])
    rounds = np.arange(len(energy))

    # 1️⃣ Total Energy Consumption vs Rounds
    plt.figure()
    plt.plot(rounds, energy)
    plt.title(f"Total Energy Consumption (J) vs Rounds ({method_name})")
    plt.xlabel("Rounds")
    plt.ylabel("Total Energy (J)")
    plt.grid()
    plt.show()

    # 2️⃣ Alive Nodes vs Rounds
    plt.figure()
    plt.plot(rounds, alive)
    plt.title(f"Alive Nodes vs Rounds ({method_name})")
    plt.xlabel("Rounds")
    plt.ylabel("Number of Alive Nodes")
    plt.grid()
    plt.show()

    # 3️⃣ Accumulated MSE vs Rounds
    cumulative_mse = np.cumsum(mse_per_round)

    plt.figure()
    plt.plot(np.arange(len(cumulative_mse)), cumulative_mse)
    plt.title(f"Accumulated MSE vs Rounds ({method_name})")
    plt.xlabel("Training Steps")
    plt.ylabel("Accumulated MSE")
    plt.grid()
    plt.show()

    print(f"Network Lifetime ({method_name}): {results['lifetime'][0]} steps")


if __name__ == "__main__":
    run_training(seed=42, N=550, episodes=500, max_steps=1000, eval_every=50)