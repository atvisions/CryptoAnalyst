from django.apps import AppConfig

class EVMConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'chains.evm'
    verbose_name = 'EVM Chain'
