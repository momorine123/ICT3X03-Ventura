from django.shortcuts import render, redirect, reverse
from django.contrib import messages
from django.http import HttpResponse, request, JsonResponse
from django.template import loader
from django.shortcuts import render
from datetime import date
from base.models import HotelRoom, HotelRoomImages, UserToken
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from .decorators import check_recaptcha
from django.conf import settings
from dotenv import load_dotenv
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
import json

from .forms import (
                    UserForm,
                    UserProfileForm, 
                    ContactForm, 
                    TwoStepForm,
                    AuthForm
)

from .mixins import( 
                    FormErrors,
                    RedirectParams,
                    TokenGenerator, 
                    CreateEmail, 
                    ActivateTwoStep
)


load_dotenv()

'''
Index Views of Ventura
'''
def index(request):
    today = date.today()
    today = today.strftime("%m/%d/%Y")

    context = {'date_placeholder': today}
    verified = request.session.get('verified', None)
    if verified:
        context["verified"] = True
    else:
        context["verified"] = False

    return render(request, 'home.html', context)


'''
Login Views of Ventura
'''
def about(request):
    return render(request, 'about.html')



'''
Contact us Views of Ventura
'''
@check_recaptcha
def contact(request):
    form = ContactForm()
    alert = False
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid() and request.recaptcha_is_valid:
            messages.success(request, 'Your message has been sent!')
            form.save()
        
    context = {'form': form, 'secret_key': settings.RECAPTCHA_PUBLIC_KEY, 'alert': alert}
    return render(request, 'contact.html', context)



'''
Login Views of Ventura
'''
@check_recaptcha
def loginPage(request):
    a_form = AuthForm()
    results = "error"
    message = "Something went wrong. Please check and try again"

    if request.user.is_authenticated:
        return redirect('webindex')
    
    if request.method == 'POST':
        a_form = AuthForm(data=request.POST)
        if a_form.is_valid() and request.recaptcha_is_valid:
            username = a_form.cleaned_data.get('username')
            password = a_form.cleaned_data.get('password')
            user = authenticate(request, username=username, password=password)
            if user is not None :

                # check if user 2FA is active
                if user.users.two_step_active:
                    # create new token
                    token = TokenGenerator()
                    make_token = token.make_token(user)
                    url_safe = urlsafe_base64_encode(force_bytes(user.pk))
                    
                    # create and send sms code
                    sms_code = ActivateTwoStep(user=user, token=make_token)
                    message = "We sent you an SMS!"
                    results = "success"
                    return redirect(f'verify/{url_safe}/{make_token}')
                else:
                    login(request, user)
                    return redirect('webindex')
            else:
                messages.error(request, 'Username OR password is incorrect')
                results = "error"
    context = {'secret_key': settings.RECAPTCHA_PUBLIC_KEY, 'a_form': a_form}
    return render(request, 'login.html', context)


'''
Registration Page of Ventura
'''
def registerPage(request):
    if request.user.is_authenticated:
        return redirect('webindex')
    
    u_form = UserForm()
    p_form = UserProfileForm()
    results = "error"
    message = "Something went wrong. Please check and try again"

    if request.method == 'POST':
        u_form = UserForm(request.POST)
        p_form = UserProfileForm(request.POST)

        if u_form.is_valid() and p_form.is_valid():
            user = u_form.save()
            
            #commit is false is used as userprofile.user can not be null
            up = p_form.save(commit=False)
            up.user = user
            up.save()

            # Mark User profile as inactive until verified
            user.is_active = False
            user.email = user.username
            user.save()

            # create new token
            token = TokenGenerator()
            make_token = token.make_token(user)
            url_safe = urlsafe_base64_encode(force_bytes(user.pk)) 

            # create and send sms code
            sms_code = ActivateTwoStep(user=user, token=make_token)

            # results
            results = "success"
            message = "We sent you an SMS!"
            context = {'results': results, 'message': message, 'url_safe': url_safe, 'make_token': make_token}
            return redirect(f'verify/{url_safe}/{make_token}')
        else:
            message = FormErrors(u_form, p_form)
            context = {'results': results, 'message': message}
        
    
    context = {'u_form': u_form, 'p_form': p_form}

    return render(request, 'register.html', context)

def account(request):
    return render(request, 'account.html')

'''
List of rooms views in Ventura
'''
def room(request):
    room_list = HotelRoomImages.objects.all().select_related('room')
    context = {'room_list': room_list}
    return render(request, 'room.html', context)


'''
Logout views of Ventura
'''
def logoutUser(request):
    logout(request)
    return redirect('webindex')


'''
Payment views of Ventura
'''
@login_required(login_url='weblogin')
def booking(request, room_id):
    
    gst_calc = 0.07 
    context = {}
    return render(request, 'payment.html', context)


'''
Function view to handle verification tokens
'''
def verification(request, uidb64, token):

	try:
		uid = force_str(urlsafe_base64_decode(uidb64))
		user = User.objects.get(pk=uid)
		ut = UserToken.objects.get(user = user, token = token, is_active = True)
		email_token = ut.is_email
		password_token = ut.is_password

	except(TypeError, ValueError, OverflowError, User.DoesNotExist, UserToken.DoesNotExist):

		#user our RedirectParams function to redirect & append 'token_error' parameter to fire an error message
		return RedirectParams(url = 'login', params = {"token_error": "true"})

	#if User & UserToken exist...
	if user and ut:

		# if the token type is_email
		if email_token:

			#deactivate the token now that it has been used
			ut.is_active = False
			ut.save()

			up = user.users
			up.verified = True
			up.save()
						
			#login the user
			login(request, user)

			#user our RedirectParams function to redirect & append 'verified' parameter to fire a success message
			return RedirectParams(url = 'webindex', params = {"verified": "true"})

		#else the token is for 2 step verification
		else:
			ts_form = TwoStepForm()
			result = "error"
			message = "Something went wrong. Please check and try again"

			if request.method == "POST":
				ts_form = TwoStepForm(data = request.POST)

				if ts_form.is_valid():
					
					two_step_code = ts_form.cleaned_data.get('two_step_code')

					if two_step_code == ut.two_step_code:
						
						user.is_active = True
						user.save()

						login(request, user)

						#deactivate the token now that it has been used
						ut.is_active = False
						ut.save()
						message = "Success! You are now signed in"
						result = "perfect"
						return redirect('/', kwargs={'verified': True})
					else:
						messages.error(request, 'Invalid code')								
				
				
			context = {'ts_form':ts_form, "uidb64":uidb64, "token":token}
			
			return render(request, 'two_step_verification.html', context)
