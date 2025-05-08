from django.shortcuts import render

# Create your views here.

def home(request):
    return render(request, 'website/home.html')

def privacy_policy(request):
    return render(request, 'website/privacy-policy.html')
