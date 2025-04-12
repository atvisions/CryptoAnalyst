from django.apps import AppConfig

class SolanaConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'chains.solana'
    verbose_name = 'Solana Chain'
