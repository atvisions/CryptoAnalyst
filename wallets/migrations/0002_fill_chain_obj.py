from django.db import migrations

def fill_chain_obj(apps, schema_editor):
    """将现有钱包的chain字段值复制到chain_obj字段"""
    Wallet = apps.get_model('wallets', 'Wallet')
    Chain = apps.get_model('wallets', 'Chain')
    
    # 获取所有钱包
    wallets = Wallet.objects.all()
    
    # 遍历钱包，设置chain_obj字段
    for wallet in wallets:
        # 获取或创建Chain对象
        chain_obj, created = Chain.objects.get_or_create(
            chain=wallet.chain,
            defaults={'is_active': True}
        )
        
        # 设置wallet的chain_obj字段
        wallet.chain_obj = chain_obj
        wallet.save()

class Migration(migrations.Migration):

    dependencies = [
        ('wallets', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(fill_chain_obj),
    ]
