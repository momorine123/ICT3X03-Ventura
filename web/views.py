from django.shortcuts import render
from django.http import HttpResponse, request
from django.template import loader
from django.shortcuts import render


# Create your views here.
def index(request):
    return render(request, 'home.html')


def about(request):
    return render(request, 'about.html')


def contact(request):
    return render(request, 'contact.html')