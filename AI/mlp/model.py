import torch
import torch.nn as nn

from mlp.feature_stats import STATS_DIM
from process_landmarks.exercise_config import NUM_EXERCISES


# ---------------------------------------------------------------------------
# Summary Statistics VAE
# ---------------------------------------------------------------------------

class StatsVAE(nn.Module):
    """
    Variational Autoencoder operating on per-rep summary statistics.
    Input: 97 rep stats + 5 exercise one-hot = 102
    Latent: 32 dimensions
    """
    def __init__(self, stats_dim=STATS_DIM, n_exercises=NUM_EXERCISES, latent_dim=32):
        super().__init__()
        input_dim = stats_dim + n_exercises

        # Encoder
        self.encoder = nn.Sequential(
            nn.Linear(input_dim, 256),
            nn.BatchNorm1d(256),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(256, 128),
            nn.BatchNorm1d(128),
            nn.ReLU(),
            nn.Dropout(0.2),
        )
        self.fc_mu = nn.Linear(128, latent_dim)
        self.fc_log_var = nn.Linear(128, latent_dim)

        # Decoder
        self.decoder = nn.Sequential(
            nn.Linear(latent_dim + n_exercises, 128),
            nn.BatchNorm1d(128),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(128, 256),
            nn.BatchNorm1d(256),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(256, stats_dim),
        )

        self.stats_dim = stats_dim
        self.n_exercises = n_exercises
        self.latent_dim = latent_dim

    def encode(self, x):
        h = self.encoder(x)
        return self.fc_mu(h), self.fc_log_var(h)

    def reparameterize(self, mu, log_var):
        std = torch.exp(0.5 * log_var)
        eps = torch.randn_like(std)
        return mu + eps * std

    def decode(self, z, exercise_one_hot):
        z_cond = torch.cat([z, exercise_one_hot], dim=-1)
        return self.decoder(z_cond)

    def forward(self, stats, exercise_one_hot):
        x = torch.cat([stats, exercise_one_hot], dim=-1)
        mu, log_var = self.encode(x)
        z = self.reparameterize(mu, log_var)
        reconstruction = self.decode(z, exercise_one_hot)
        return reconstruction, mu, log_var


# ---------------------------------------------------------------------------
# LSTM VAE (no attention)
# ---------------------------------------------------------------------------

class LSTMVAE(nn.Module):
    """
    LSTM-based VAE for variable-length rep sequences.
    Input: (T, 29) per rep — full embedding per frame.
    """
    def __init__(self, input_dim=29, hidden_dim=128, latent_dim=32,
                 n_layers=2, n_exercises=NUM_EXERCISES):
        super().__init__()
        self.hidden_dim = hidden_dim
        self.n_layers = n_layers
        self.n_exercises = n_exercises
        self.input_dim = input_dim

        # Encoder LSTM
        self.encoder_lstm = nn.LSTM(
            input_size=input_dim, hidden_size=hidden_dim,
            num_layers=n_layers, batch_first=True
        )
        self.fc_mu = nn.Linear(hidden_dim, latent_dim)
        self.fc_log_var = nn.Linear(hidden_dim, latent_dim)

        # Decoder
        self.latent_to_hidden = nn.Linear(latent_dim + n_exercises, hidden_dim)
        self.decoder_lstm = nn.LSTM(
            input_size=input_dim, hidden_size=hidden_dim,
            num_layers=n_layers, batch_first=True
        )
        self.output_layer = nn.Linear(hidden_dim, input_dim)

    def encode(self, x):
        # x: (batch, T, 29)
        _, (h_n, _) = self.encoder_lstm(x)
        # h_n: (n_layers, batch, hidden) — take last layer
        h = h_n[-1]  # (batch, hidden)
        return self.fc_mu(h), self.fc_log_var(h)

    def reparameterize(self, mu, log_var):
        std = torch.exp(0.5 * log_var)
        eps = torch.randn_like(std)
        return mu + eps * std

    def decode(self, z, exercise_one_hot, seq_len):
        # Initialize hidden state from latent + exercise
        z_cond = torch.cat([z, exercise_one_hot], dim=-1)
        h_0 = self.latent_to_hidden(z_cond)  # (batch, hidden)
        h_0 = h_0.unsqueeze(0).repeat(self.n_layers, 1, 1)  # (n_layers, batch, hidden)
        c_0 = torch.zeros_like(h_0)

        # Teacher forcing with zeros as input
        batch_size = z.size(0)
        decoder_input = torch.zeros(batch_size, seq_len, self.input_dim, device=z.device)
        output, _ = self.decoder_lstm(decoder_input, (h_0, c_0))
        reconstruction = self.output_layer(output)  # (batch, T, 29)
        return reconstruction

    def forward(self, x, exercise_one_hot):
        # x: (batch, T, 29)
        mu, log_var = self.encode(x)
        z = self.reparameterize(mu, log_var)
        reconstruction = self.decode(z, exercise_one_hot, x.size(1))
        return reconstruction, mu, log_var


# ---------------------------------------------------------------------------
# LSTM + Attention VAE
# ---------------------------------------------------------------------------

class Attention(nn.Module):
    """Additive attention over LSTM hidden states."""
    def __init__(self, hidden_dim):
        super().__init__()
        self.attn = nn.Sequential(
            nn.Linear(hidden_dim, 64),
            nn.Tanh(),
            nn.Linear(64, 1),
        )

    def forward(self, lstm_outputs):
        # lstm_outputs: (batch, T, hidden_dim)
        scores = self.attn(lstm_outputs)        # (batch, T, 1)
        weights = torch.softmax(scores, dim=1)  # (batch, T, 1)
        context = (lstm_outputs * weights).sum(dim=1)  # (batch, hidden_dim)
        return context, weights.squeeze(-1)     # context, attention_weights


class LSTMAttentionVAE(nn.Module):
    """
    Bidirectional LSTM + Attention VAE for variable-length rep sequences.
    The attention mechanism learns which frames matter most for form assessment.
    """
    def __init__(self, input_dim=29, hidden_dim=128, latent_dim=32,
                 n_layers=2, n_exercises=NUM_EXERCISES):
        super().__init__()
        self.hidden_dim = hidden_dim
        self.n_layers = n_layers
        self.n_exercises = n_exercises
        self.input_dim = input_dim
        bidir_dim = hidden_dim * 2  # bidirectional doubles the output dim

        # Encoder: bidirectional LSTM + attention
        self.encoder_lstm = nn.LSTM(
            input_size=input_dim, hidden_size=hidden_dim,
            num_layers=n_layers, batch_first=True, bidirectional=True
        )
        self.attention = Attention(bidir_dim)
        self.fc_mu = nn.Linear(bidir_dim, latent_dim)
        self.fc_log_var = nn.Linear(bidir_dim, latent_dim)

        # Decoder: unidirectional LSTM
        self.latent_to_hidden = nn.Linear(latent_dim + n_exercises, bidir_dim)
        self.decoder_lstm = nn.LSTM(
            input_size=input_dim, hidden_size=bidir_dim,
            num_layers=n_layers, batch_first=True
        )
        self.output_layer = nn.Linear(bidir_dim, input_dim)

    def encode(self, x):
        # x: (batch, T, 29)
        lstm_out, _ = self.encoder_lstm(x)  # (batch, T, hidden*2)
        context, attn_weights = self.attention(lstm_out)  # (batch, hidden*2)
        return self.fc_mu(context), self.fc_log_var(context), attn_weights

    def reparameterize(self, mu, log_var):
        std = torch.exp(0.5 * log_var)
        eps = torch.randn_like(std)
        return mu + eps * std

    def decode(self, z, exercise_one_hot, seq_len):
        z_cond = torch.cat([z, exercise_one_hot], dim=-1)
        h_0 = self.latent_to_hidden(z_cond)
        h_0 = h_0.unsqueeze(0).repeat(self.n_layers, 1, 1)
        c_0 = torch.zeros_like(h_0)

        batch_size = z.size(0)
        decoder_input = torch.zeros(batch_size, seq_len, self.input_dim, device=z.device)
        output, _ = self.decoder_lstm(decoder_input, (h_0, c_0))
        reconstruction = self.output_layer(output)
        return reconstruction

    def forward(self, x, exercise_one_hot):
        mu, log_var, attn_weights = self.encode(x)
        z = self.reparameterize(mu, log_var)
        reconstruction = self.decode(z, exercise_one_hot, x.size(1))
        return reconstruction, mu, log_var, attn_weights


# ---------------------------------------------------------------------------
# Loss functions
# ---------------------------------------------------------------------------

def vae_loss(reconstruction, target, mu, log_var, beta=0.5):
    """VAE loss: reconstruction MSE + beta * KL divergence."""
    recon_loss = nn.functional.mse_loss(reconstruction, target, reduction='mean')
    kl_loss = -0.5 * torch.mean(1 + log_var - mu.pow(2) - log_var.exp())
    return recon_loss + beta * kl_loss, recon_loss, kl_loss
