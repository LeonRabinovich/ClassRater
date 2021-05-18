from django.shortcuts import render, redirect
from homepage.models import Course, Review
from homepage.forms import FilterForm, ReviewForm
from django.contrib.auth import login, logout, authenticate
from django.contrib import messages
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ObjectDoesNotExist


def app_layout(request):
    return render(request, 'homepage/app_layout.html')


def landing(request):
    last_reviews = Review.landing_page_feed()
    return render(request, 'homepage/landing/landing.html', {'reviews': last_reviews})


def courses(request):
    all_courses = Course.get_courses()
    filters_active = []
    if request.method == "POST":
        form = FilterForm(request.POST)
        if form.is_valid():
            filters = form.cleaned_data.get('filter_by')
            for filter in filters:
                if(filter == 'mand'):
                    all_courses = Course.get_mandatory_courses(all_courses)
                    filters_active.append('mandatory')
                elif(filter == 'elect'):
                    all_courses = Course.get_elective_courses(all_courses)
                    filters_active.append('elective')
                elif(filter == 'load_below'):
                    all_courses = Course.get_filtered_courses_by_load(3.5, all_courses)
                    filters_active.append('course load under 3.5')
                elif(filter == 'rate_over'):
                    all_courses = Course.get_filtered_courses_by_rating(3.5, all_courses)
                    filters_active.append('course rating over 3.5')
    else:
        form = FilterForm()

    context = {'all_courses': all_courses, 'filters': filters_active}
    context['form'] = FilterForm()
    return render(request, 'homepage/courses/courses.html', context)


def reviews(request):
    reviews = Review.main_feed()
    return render(request, 'homepage/reviews/reviews.html', {'reviews': reviews})


def add_review(request, course_id):
    try:
        course = Course.objects.get(pk=course_id)
    except ObjectDoesNotExist:
        return redirect('landing')

    if request.method == "POST":
        form = ReviewForm(request.POST, course=course_id)
        if form.is_valid():
            form.save()
            return redirect('landing')
    else:
        form = ReviewForm(course=course_id)
    return render(request, 'homepage/add_review.html', {'form': form, 'course_name': course.name})


def course(request, id):
    try:
        course = Course.objects.get(pk=id)
        reviews = Review.objects.filter(course=id).order_by('-likes_num')
        return render(request, 'homepage/courses/course.html', {'id': id, 'course': course, 'reviews': reviews})
    except ObjectDoesNotExist:
        return redirect('courses')


def add_review_search(request):
    if request.method == "GET":
        course_name = request.GET.get('course')
        if not course_name:
            course_name = ''
        courses = Course.get_courses_ordered_by_name(course_name)
        return render(request, 'homepage/add_review_search.html', {'course_name': course_name, 'courses': courses})


def sign_in(request):
    sign_in_successful = False

    if request.method == "POST":
        form = AuthenticationForm(request, data=request.POST)

        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)

            if user:
                login(request, user)
                sign_in_successful = True
                messages.info(request, f'You are now logged in as {username}.')
                return redirect('landing')

        if not sign_in_successful:
            messages.error(request, 'Invalid username or password.')
            return redirect('sign_in')

    form = AuthenticationForm()
    return render(request=request, template_name='homepage/users/sign_in.html', context={'sign_in_form': form})


def sign_out(request):
    messages.info(request, f'{request.user.username} successfully logged out')
    logout(request)
    return redirect('landing')
