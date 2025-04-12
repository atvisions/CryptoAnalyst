from django.contrib import admin
from django.utils.html import format_html
from .models import Device, Wallet, PaymentPassword, Chain
from .constants import CHAIN_NAMES

@admin.register(Chain)
class ChainAdmin(admin.ModelAdmin):
    list_display = ('logo_img', 'chain', 'name_display', 'is_active', 'created_at', 'updated_at')
    list_filter = ('chain', 'is_active')
    search_fields = ('chain',)
    list_editable = ('is_active',)
    ordering = ('chain',)
    
    fieldsets = (
        ('基本信息', {
            'fields': ('chain', 'is_active')
        }),
        ('显示信息', {
            'fields': ('logo',)
        }),
        ('时间信息', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    readonly_fields = ('created_at', 'updated_at')

    def logo_img(self, obj):
        if obj.logo_url:
            return format_html('<img src="{}" style="width: 32px; height: 32px; border-radius: 50%;" />', obj.logo_url)
        return '-'
    logo_img.short_description = 'Logo'
    
    def name_display(self, obj):
        return obj.name
    name_display.short_description = '名称'

@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ('device_id', 'created_at', 'updated_at')
    search_fields = ('device_id',)
    readonly_fields = ('created_at', 'updated_at')

@admin.register(PaymentPassword)
class PaymentPasswordAdmin(admin.ModelAdmin):
    list_display = ('device', 'created_at', 'updated_at')
    search_fields = ('device__device_id',)
    readonly_fields = ('created_at', 'updated_at')

@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ('name', 'chain', 'address', 'device', 'is_watch_only', 'created_at')
    list_filter = ('chain', 'is_watch_only', 'created_at')
    search_fields = ('name', 'address', 'device__device_id')
    readonly_fields = ('created_at', 'updated_at')
    ordering = ('-created_at',)
