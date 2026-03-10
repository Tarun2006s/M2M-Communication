# ddqn_agent.py
import random
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from collections import deque, namedtuple

# Replay buffer
Transition = namedtuple('Transition', ('state', 'action', 'reward', 'next_state', 'done'))

class ReplayBuffer:
    def __init__(self, capacity=100000):
        self.buffer = deque(maxlen=capacity)

    def push(self, *args):
        self.buffer.append(Transition(*args))

    def sample(self, batch_size):
        batch = random.sample(self.buffer, batch_size)
        return Transition(*zip(*batch))

    def __len__(self):
        return len(self.buffer)

# Q-network
class QNetwork(nn.Module):
    def __init__(self, input_dim, output_dim, hidden=[512,256]):
        super().__init__()
        layers = []
        last = input_dim
        for h in hidden:
            layers.append(nn.Linear(last, h))
            layers.append(nn.ReLU())
            last = h
        layers.append(nn.Linear(last, output_dim))
        self.net = nn.Sequential(*layers)

    def forward(self, x):
        return self.net(x)

class DDQNAgent:
    def __init__(self, state_dim, action_dim, node_count, lr=1e-4, gamma=0.99,
                 batch_size=64, buffer_size=200000, min_replay_size=500,
                 update_target_every=1000, device=None):
        """
        state_dim: size of observation vector (e.g., env.observation_space.shape[0])
        action_dim: number of discrete actions per node (2)
        node_count: number of nodes
        We'll flatten action space: outputs = node_count * action_dim,
        But to use DDQN nicely, we treat the Q outputs as Q-values for each node-action pair.
        Simpler: we compute Q-values per node independently by reshaping last layer to (node_count, action_dim)
        """
        self.device = device or ('cuda' if torch.cuda.is_available() else 'cpu')
        self.state_dim = state_dim
        self.action_dim = action_dim
        self.node_count = node_count
        # output_dim = node_count * action_dim
        self.output_dim = node_count * action_dim

        self.q_net = QNetwork(state_dim, self.output_dim).to(self.device)
        self.target_net = QNetwork(state_dim, self.output_dim).to(self.device)
        self.target_net.load_state_dict(self.q_net.state_dict())

        self.optimizer = optim.Adam(self.q_net.parameters(), lr=lr)
        self.gamma = gamma
        self.batch_size = batch_size
        self.replay = ReplayBuffer(capacity=buffer_size)
        self.min_replay_size = min_replay_size
        self.update_target_every = update_target_every
        self.learn_steps = 0

        # epsilon schedule
        self.eps_start = 1.0
        self.eps_end = 0.05
        self.eps_decay = 1e5  # steps

    def select_action(self, state, eval_mode=False):
        """
        state: np.array shape (state_dim,)
        returns action array length node_count with values 0..action_dim-1
        """
        eps = self.eps_end if eval_mode else (self.eps_end + (self.eps_start - self.eps_end) *
                                             max(0, (1 - self.learn_steps / self.eps_decay)))
        if random.random() < eps and (not eval_mode):
            # random action for each node
            return np.random.randint(0, self.action_dim, size=self.node_count)
        else:
            s = torch.FloatTensor(state).unsqueeze(0).to(self.device)
            with torch.no_grad():
                qvals = self.q_net(s).cpu().numpy().reshape(self.node_count, self.action_dim)
            # greedy per-node
            actions = qvals.argmax(axis=1)
            return actions

    def store(self, state, action, reward, next_state, done):
        # flatten action into list
        self.replay.push(state.astype(np.float32), action.astype(np.int64),
                         np.float32(reward), next_state.astype(np.float32), bool(done))

    def train_step(self):
        if len(self.replay) < self.min_replay_size:
            return None
        transitions = self.replay.sample(self.batch_size)
        # Use np.array then torch.from_numpy for zero-copy tensor creation where possible.
        state = torch.from_numpy(np.stack(transitions.state)).to(self.device)        # (B, state_dim)
        next_state = torch.from_numpy(np.stack(transitions.next_state)).to(self.device)
        reward = torch.from_numpy(np.array(transitions.reward, dtype=np.float32)).unsqueeze(1).to(self.device)  # (B,1)
        done = torch.from_numpy(np.array(transitions.done, dtype=np.float32)).unsqueeze(1).to(self.device)
        # actions are arrays; convert to tensor (B, node_count)
        actions = torch.from_numpy(np.stack(transitions.action).astype(np.int64)).to(self.device)  # (B, node_count)

        # compute q-values for current states
        q_values = self.q_net(state)  # (B, node_count * action_dim)
        q_values = q_values.view(self.batch_size, self.node_count, self.action_dim)  # (B,N,A)

        # gather q for executed actions per node then average across nodes
        actions_unsq = actions.unsqueeze(-1)  # (B,N,1)
        q_selected = torch.gather(q_values, dim=2, index=actions_unsq).squeeze(-1)  # (B,N)
        q_selected_mean = q_selected.mean(dim=1, keepdim=True)  # (B,1)  # aggregate across nodes

        # Double DQN target:
        # use q_net to select best actions in next_state, and target_net to evaluate them
        with torch.no_grad():
            next_q_vals_online = self.q_net(next_state).view(self.batch_size, self.node_count, self.action_dim)
            next_actions_online = next_q_vals_online.argmax(dim=2)  # (B,N)
            next_q_vals_target = self.target_net(next_state).view(self.batch_size, self.node_count, self.action_dim)
            # gather target q for next_actions_online
            idx = next_actions_online.unsqueeze(-1)
            next_q_selected = torch.gather(next_q_vals_target, dim=2, index=idx).squeeze(-1)  # (B,N)
            next_q_selected_mean = next_q_selected.mean(dim=1, keepdim=True)  # (B,1)
            target = reward + (1.0 - done) * self.gamma * next_q_selected_mean

        # MSE loss
        loss = nn.MSELoss()(q_selected_mean, target)

        self.optimizer.zero_grad()
        loss.backward()
        # gradient clipping
        nn.utils.clip_grad_norm_(self.q_net.parameters(), 10.0)
        self.optimizer.step()

        # update target network periodically
        self.learn_steps += 1
        if self.learn_steps % self.update_target_every == 0:
            self.target_net.load_state_dict(self.q_net.state_dict())

        return loss.item()